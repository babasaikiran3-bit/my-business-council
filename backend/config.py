"""Configuration for the Parenting Roundtable."""

import os
from dotenv import load_dotenv

load_dotenv()

# OpenRouter API key
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Stage 0 researcher - runs web search to build the shared evidence base.
# Perplexity Sonar (e.g. "perplexity/sonar-pro") is an alternative searcher.
SEARCH_MODEL = "openai/gpt-5.1"

# Council members - list of OpenRouter model identifiers (gpt-5.1 is now the searcher)
COUNCIL_MODELS = [
    "google/gemini-3-pro-preview",
    "anthropic/claude-sonnet-4.5",
    "x-ai/grok-4",
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = "google/gemini-3-pro-preview"

# OpenRouter API endpoint
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# Data directory for conversation storage
DATA_DIR = "data/conversations"

# Trusted medical/scientific domains the Stage 0 searcher is restricted to.
# Korean authorities come FIRST (primary market) and take precedence on conflict;
# international authorities are the backup. Subdomains are matched automatically
# (see _hostname_in_allowlist), so e.g. health.kdca.go.kr is covered by kdca.go.kr.
TRUSTED_DOMAINS = [
    # --- Korean authorities (primary) ---
    "kdca.go.kr",           # 질병관리청 (Korea Disease Control & Prevention Agency)
    "mfds.go.kr",           # 식품의약품안전처 (Ministry of Food and Drug Safety)
    "mohw.go.kr",           # 보건복지부 (Ministry of Health and Welfare)
    "pediatric.or.kr",      # 대한소아청소년과학회 (Korean Pediatric Society)
    "amc.seoul.kr",         # 서울아산병원 (Asan Medical Center)
    "snuh.org",             # 서울대학교병원 (Seoul National University Hospital)
    "samsunghospital.com",  # 삼성서울병원 (Samsung Medical Center)
    "iseverance.com",       # 세브란스병원 (Severance Hospital)
    # --- International authorities (backup) ---
    "healthychildren.org",
    "aap.org",
    "who.int",
    "cdc.gov",
    "nhs.uk",
    "cochranelibrary.com",
    "ncbi.nlm.nih.gov",
    "pubmed.ncbi.nlm.nih.gov",
    "mayoclinic.org",
    "nih.gov",
    "aafp.org",
]

# Stage 0 system prompt: neutral, advice-free evidence digest from trusted sources.
SEARCH_SYSTEM_PROMPT = "You are a medical research assistant for Korean parents. Using ONLY authoritative medical/scientific sources, produce a neutral evidence digest for a pediatric question. PRIORITISE Korean authorities (질병관리청/KDCA, 대한소아청소년과학회, 식약처/MFDS, major Korean university hospitals) and search with Korean-language terms where helpful; use international sources (WHO/AAP/CDC/NHS) only as backup. When Korean and international guidance differ (e.g. 표준예방접종일정/vaccination schedule, fever thresholds, drug brand names), treat the KOREAN guidance as primary and note the difference. Write the digest in KOREAN (한국어). State key facts, current official guidance, age-specific thresholds (e.g. fever thresholds by age), and any emergency warning signs ('red flags'). Cite the sources you used. Give NO advice, recommendations, reassurance, or diagnosis — only report what the evidence says. If evidence is thin or sources disagree, say so explicitly. Be concise and factual."

# Stage 1 system prompt: each council member reasons ONLY from the provided evidence base.
STAGE1_SYSTEM_PROMPT = "You are a careful, evidence-based pediatric advisor on a panel. Answer the parent's question using ONLY the evidence base provided to you (a neutral digest plus a list of real sources). Cite those sources; do NOT invent or recall other links — if the provided evidence does not cover something, say so plainly. Be age-aware (newborn 0-3mo, infant 3-12mo, toddler 1-3yr, older child): thresholds and risks differ sharply by age. LEAD with any red-flag or emergency signs that warrant urgent or ER care. Be calm and non-catastrophizing; do not fear-monger for benign situations. Admit uncertainty honestly. Respond in natural, warm Korean (한국어, 존댓말). End with a one-line Korean disclaimer that this is general information, not a diagnosis."

# Stage 3 chairman instruction (static portion; dynamic context is f-stringed in council.py).
STAGE3_CHAIRMAN_PROMPT = """You are the Chairman of a pediatric advisory panel for Korean parents. A neutral evidence base was gathered from trusted medical sources, then several evidence-based advisors answered the parent's question and ranked each other's answers. Synthesize ONE final answer for the parent. Write the ENTIRE answer in natural, warm Korean (한국어, 존댓말).

Requirements:
- SAFETY-FIRST: if the evidence indicates an emergency for this child's age/situation (e.g. 생후 3개월 미만 아기의 발열 38°C 이상 → 즉시 응급실 평가 필요), LEAD the answer with a Markdown blockquote line that starts exactly "> 응급:".
- BENIGN CASES: if the situation is NOT urgent, say so plainly and reassuringly. Do NOT use the "> 응급:" blockquote or urgent framing for non-urgent situations — reserve it strictly for genuine red flags so it stays meaningful.
- DECISIVE: give ONE clear recommendation plus concrete next steps — not a menu of options.
- CAREFUL: state explicit thresholds for 집에서 경과관찰 (watch-and-wait) vs. 병원 진료 (call-the-doctor) vs. 응급실 (go-to-ER).
- SOURCES: refer to sources by their name/title in your prose (e.g. "질병관리청" 또는 "대한소아청소년과학회 지침"). Do NOT paste raw URLs and do NOT write your own list of links — the app automatically displays the verified, clickable list of sources beneath your answer.
- Include exactly one short confidence line. The app appends a standard Korean disclaimer automatically, so do NOT write your own disclaimer.
- Warm, skimmable tone."""
