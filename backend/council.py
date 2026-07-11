"""Orquestación del LLM Council de 3 etapas (batch y streaming)."""

from typing import List, Dict, Any, Tuple, Optional, Callable

from .providers import query_models_parallel, query_model
from .config import TITLE_MODEL
from .council_config import load_config
from .streaming import run_agent_stream
import asyncio


def _members_chairman(members: Optional[List[str]], chairman: Optional[str]) -> Tuple[List[str], str]:
    if members and chairman:
        return members, chairman
    cfg = load_config()
    return members or cfg["members"], chairman or cfg["chairman"]


# Historial = lista de turnos previos [{"q": pregunta_usuario, "a": respuesta_chairman}, ...]
History = Optional[List[Dict[str, str]]]


def _format_history(history: History) -> str:
    """Bloque de contexto con los turnos previos (vacío si no hay)."""
    if not history:
        return ""
    blocks = []
    for i, turn in enumerate(history, start=1):
        blocks.append(f"[Turn {i}]\nUser: {turn.get('q', '')}\n"
                      f"Council's answer: {turn.get('a', '')}")
    return ("Previous turns in this conversation (for context):\n\n"
            + "\n\n".join(blocks) + "\n\n---\n\n")


def _format_research(brief: Optional[str]) -> str:
    """Bloque de contexto con el brief de investigación (vacío si no hay)."""
    if not brief or not brief.strip():
        return ""
    return ("Research brief — CURRENT information gathered from the web by the council's "
            "research officer (your training data is months old; trust this for time-sensitive "
            "facts):\n\n" + brief.strip() + "\n\n---\n\n")


def _build_context_prompt(history: History, brief: Optional[str], user_query: str) -> str:
    """Antepone historial + brief de investigación a la pregunta actual."""
    prefix = _format_history(history) + _format_research(brief)
    if not prefix:
        return user_query
    return f"{prefix}Current question: {user_query}"


# --- Stage 0: investigación (busca info actual antes de deliberar) -----------

def _research_prompt(user_query: str) -> str:
    return f"""You are the Research Officer of an LLM Council. BEFORE the council deliberates, your job is to gather CURRENT, up-to-date information from the internet relevant to the user's question. Your training data has a cutoff months in the past, so you MUST search the web for anything time-sensitive (versions, prices, news, recent events, current best practices, library/API/tool changes).

User's question:
{user_query}

Instructions:
- USE your web search tool. Do REAL searches; do not rely on memory for current facts.
- Produce a concise RESEARCH BRIEF: the key up-to-date facts, figures, dates and caveats, each with its source URL.
- Do NOT answer or opine on the question itself — only provide the factual, current context the council needs.
- If the question genuinely needs no external/current info (e.g. it is about local code or pure reasoning), reply with a single line saying so.
Return only the brief."""


async def stage0_research(user_query: str, researcher: str) -> Dict[str, Any]:
    """Stage 0 (batch): el investigador busca info actual y devuelve un brief."""
    response = await query_model(researcher, [{"role": "user", "content": _research_prompt(user_query)}])
    brief = response.get("content", "") if response else ""
    return {"model": researcher, "brief": brief}


# --- Stage 1 ----------------------------------------------------------------

async def stage1_collect_responses(user_query: str, cwd: str = None,
                                   members: Optional[List[str]] = None,
                                   history: History = None,
                                   research_brief: Optional[str] = None) -> List[Dict[str, Any]]:
    """Stage 1 (batch): respuestas individuales de cada miembro."""
    members, _ = _members_chairman(members, "x")
    messages = [{"role": "user", "content": _build_context_prompt(history, research_brief, user_query)}]
    responses = await query_models_parallel(members, messages, cwd=cwd)
    results = []
    for model, response in responses.items():
        if response is not None:
            results.append({"model": model, "response": response.get("content", "")})
    return results


# --- Stage 2 ----------------------------------------------------------------

async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    members: Optional[List[str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Stage 2: cada modelo rankea las respuestas anonimizadas."""
    members, _ = _members_chairman(members, "x")
    labels = [chr(65 + i) for i in range(len(stage1_results))]
    label_to_model = {
        f"Response {label}": result["model"]
        for label, result in zip(labels, stage1_results)
    }
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different models (anonimized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]
    responses = await query_models_parallel(members, messages)

    results = []
    for model, response in responses.items():
        if response is not None:
            full_text = response.get("content", "")
            results.append({
                "model": model,
                "ranking": full_text,
                "parsed_ranking": parse_ranking_from_text(full_text),
            })
    return results, label_to_model


# --- Stage 3 ----------------------------------------------------------------

async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    chairman: Optional[str] = None,
    history: History = None,
    research_brief: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage 3: el chairman sintetiza la respuesta final (siempre read-only)."""
    _, chairman = _members_chairman(["x"], chairman)

    stage1_text = "\n\n".join([
        f"Model: {r['model']}\nResponse: {r['response']}" for r in stage1_results])
    stage2_text = "\n\n".join([
        f"Model: {r['model']}\nRanking: {r['ranking']}" for r in stage2_results])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI models have provided responses to a user's question, and then ranked each other's responses.

{_format_history(history)}{_format_research(research_brief)}Original Question: {user_query}

STAGE 1 - Individual Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their insights
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]
    response = await query_model(chairman, messages)
    if response is None:
        return {"model": chairman, "response": "Error: no se pudo generar la síntesis final."}
    return {"model": chairman, "response": response.get("content", "")}


def _research_brief_text(research: Optional[Dict[str, Any]]) -> Optional[str]:
    """Extrae el texto del brief de un dict stage0 (o None)."""
    return research.get("brief") if research else None


# --- Documentar el consenso en el repo (acción explícita, post-deliberación) -

def _extract_consensus_file(text: str) -> Optional[str]:
    """Extrae la ruta declarada por el chairman (línea `CONSENSUS_FILE: ...`)."""
    import re
    m = re.search(r'CONSENSUS_FILE:\s*(\S+)', text)
    return m.group(1) if m else None


async def generate_consensus_doc(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]],
    stage3_result: Dict[str, Any],
    chairman: Optional[str] = None,
) -> Dict[str, Any]:
    """El chairman GENERA (no escribe) el documento de consenso ya alcanzado.

    Corre read-only, sin tocar el disco: devuelve el markdown como texto para
    previsualizar. La escritura del archivo la hace el backend tras la aprobación.
    Devuelve {model, path, content}.
    """
    _, chairman = _members_chairman(["x"], chairman)

    stage1_text = "\n\n".join([
        f"Model: {r['model']}\nResponse: {r['response']}" for r in stage1_results])
    stage2_text = "\n\n".join([
        f"Model: {r['model']}\nRanking: {r['ranking']}" for r in stage2_results])
    consensus = stage3_result.get("response", "")

    prompt = f"""You are the Chairman of an LLM Council. The council has ALREADY deliberated and reached a final consensus answer. Your only job now is to WRITE OUT that consensus as a markdown document — do NOT re-open the debate or change the conclusion.

Original Question:
{user_query}

The council's CONSENSUS answer (this is what you must document):
{consensus}

Supporting material — Stage 1 individual responses:
{stage1_text}

Supporting material — Stage 2 peer rankings:
{stage2_text}

INSTRUCTIONS:
- Do NOT use any tools and do NOT write any files. Simply OUTPUT the document as text.
- The document must include: the original question, the consensus answer, key points of agreement, any notable dissent, and concrete recommended next steps / action items.
- Your response MUST be EXACTLY in this shape:
  - The FIRST line is: `CONSENSUS_FILE: docs/council/<short-kebab-case-slug>.md`
  - Then a blank line.
  - Then the full markdown document (starting with a `# Title` heading).
- Output nothing else before the CONSENSUS_FILE line.
"""

    messages = [{"role": "user", "content": prompt}]
    response = await query_model(chairman, messages)  # read-only, sin cwd ni allow_write
    if response is None:
        return {"model": chairman, "path": None, "content": None}

    text = response.get("content", "") or ""
    path = _extract_consensus_file(text)
    content = _strip_consensus_header(text)
    return {"model": chairman, "path": path, "content": content}


def _strip_consensus_header(text: str) -> str:
    """Quita la línea `CONSENSUS_FILE: ...` inicial y devuelve solo el cuerpo markdown."""
    import re
    lines = text.splitlines()
    out, removed = [], False
    for ln in lines:
        if not removed and re.match(r'\s*CONSENSUS_FILE:\s*\S+', ln):
            removed = True
            continue
        out.append(ln)
    return "\n".join(out).strip()


# --- Parsing y agregación (sin cambios) -------------------------------------

def parse_ranking_from_text(ranking_text: str) -> List[str]:
    import re
    if "FINAL RANKING:" in ranking_text:
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            numbered = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered:
                return [re.search(r'Response [A-Z]', m).group() for m in numbered]
            return re.findall(r'Response [A-Z]', ranking_section)
    return re.findall(r'Response [A-Z]', ranking_text)


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_model: Dict[str, str],
) -> List[Dict[str, Any]]:
    from collections import defaultdict
    model_positions = defaultdict(list)
    for ranking in stage2_results:
        parsed = parse_ranking_from_text(ranking["ranking"])
        for position, label in enumerate(parsed, start=1):
            if label in label_to_model:
                model_positions[label_to_model[label]].append(position)
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            aggregate.append({
                "model": model,
                "average_rank": round(sum(positions) / len(positions), 2),
                "rankings_count": len(positions),
            })
    aggregate.sort(key=lambda x: x["average_rank"])
    return aggregate


# --- Títulos ----------------------------------------------------------------

async def generate_conversation_title(user_query: str) -> str:
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""
    messages = [{"role": "user", "content": title_prompt}]
    response = await query_model(TITLE_MODEL, messages, timeout=60.0)
    if response is None:
        return "New Conversation"
    title = (response.get("content", "New Conversation") or "New Conversation").strip().strip('"\'')
    return title[:47] + "..." if len(title) > 50 else title


# --- Orquestación -----------------------------------------------------------

async def run_full_council(
    user_query: str, cwd: str = None,
    members: Optional[List[str]] = None, chairman: Optional[str] = None,
    history: History = None, research: bool = True, researcher: Optional[str] = None,
) -> Tuple[List, List, Dict, Dict]:
    """Flujo completo en modo batch (usado por debate.py y el endpoint no-streaming)."""
    members, chairman = _members_chairman(members, chairman)

    # Stage 0 — investigación (info actual de la web), opcional
    research_result = None
    if research:
        research_result = await stage0_research(user_query, researcher or chairman)
    brief = _research_brief_text(research_result)

    stage1_results = await stage1_collect_responses(
        user_query, cwd=cwd, members=members, history=history, research_brief=brief)
    if not stage1_results:
        return [], [], {"model": "error", "response": "Todos los modelos fallaron."}, {}

    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, members=members)
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    stage3_result = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results, chairman=chairman, history=history,
        research_brief=brief)

    metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
    if research_result:
        metadata["research"] = research_result
    return stage1_results, stage2_results, stage3_result, metadata


async def run_full_council_streaming(
    user_query: str, emit: Callable[[Dict[str, Any]], None],
    cwd: str = None, members: Optional[List[str]] = None, chairman: Optional[str] = None,
    history: History = None, research: bool = True, researcher: Optional[str] = None,
) -> Tuple[List, List, Dict, Dict]:
    """Flujo completo emitiendo eventos canónicos. Stage 1 con streaming fino por agente."""
    members, chairman = _members_chairman(members, chairman)

    # Stage 0 — investigación en vivo (busca info actual antes de deliberar)
    brief = None
    research_result = None
    if research:
        researcher_id = researcher or chairman
        emit({"type": "stage", "stage": 0, "status": "start"})
        brief = await run_agent_stream(researcher_id, _research_prompt(user_query), emit, cwd=None)
        research_result = {"model": researcher_id, "brief": brief or ""}
        emit({"type": "research", "model": researcher_id, "brief": brief or ""})
        emit({"type": "stage", "stage": 0, "status": "done"})

    stage1_prompt = _build_context_prompt(history, brief, user_query)

    # Stage 1 — exploración en vivo
    emit({"type": "stage", "stage": 1, "status": "start"})
    tasks = [run_agent_stream(m, stage1_prompt, emit, cwd=cwd) for m in members]
    contents = await asyncio.gather(*tasks)
    stage1_results = []
    for model, content in zip(members, contents):
        if content:
            stage1_results.append({"model": model, "response": content})
            emit({"type": "result", "model": model, "stage": 1, "text": content})
    emit({"type": "stage", "stage": 1, "status": "done"})

    if not stage1_results:
        result = {"model": "error", "response": "Todos los modelos fallaron."}
        emit({"type": "final", "model": "error", "text": result["response"]})
        return [], [], result, {}

    # Stage 2 — ranking ciego entre pares
    emit({"type": "stage", "stage": 2, "status": "start"})
    stage2_results, label_to_model = await stage2_collect_rankings(user_query, stage1_results, members=members)
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
    emit({"type": "ranking", "aggregate": aggregate_rankings})
    emit({"type": "stage", "stage": 2, "status": "done"})

    # Stage 3 — síntesis del chairman (read-only; la escritura es una acción aparte)
    emit({"type": "stage", "stage": 3, "status": "start"})
    stage3_result = await stage3_synthesize_final(
        user_query, stage1_results, stage2_results, chairman=chairman, history=history,
        research_brief=brief)
    emit({"type": "final", "model": stage3_result["model"], "text": stage3_result["response"]})
    emit({"type": "stage", "stage": 3, "status": "done"})

    metadata = {"label_to_model": label_to_model, "aggregate_rankings": aggregate_rankings}
    if research_result:
        metadata["research"] = research_result
    return stage1_results, stage2_results, stage3_result, metadata
