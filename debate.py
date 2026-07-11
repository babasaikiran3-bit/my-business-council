#!/usr/bin/env python3
"""Debate del LLM Council sobre un repo.

Lanza los 4 miembros del consejo como agentes con ojos y manos (Read/Grep/Glob/
Bash) dentro del repo indicado. Cada uno lo explora por su cuenta, da su postura
sobre el tema, luego se rankean a ciegas y el chairman sintetiza.

Uso:
    uv run python debate.py /ruta/al/repo "¿La arquitectura escala o hay que refactorizar?"
    uv run python debate.py /ruta/al/repo            # tema por defecto: critica general
"""

import os
import sys
import time
import asyncio

from backend.council import run_full_council


def build_query(repo_path: str, tema: str) -> str:
    return f"""Sos miembro de un consejo tecnico que debate sobre un repositorio de codigo.

El repositorio esta en tu directorio de trabajo actual: {repo_path}
Tenes herramientas para explorarlo (listar archivos, leer, grep). USALAS antes de opinar:
empeza mapeando la estructura y leyendo los archivos clave (README, config, entrypoints,
los modulos centrales). No inventes: fundamenta cada afirmacion en lo que viste.

Tema del debate:
{tema}

Entrega una postura clara y argumentada (no un resumen neutro): tomá posicion, citá
archivos/lineas concretas como evidencia, y señalá riesgos y trade-offs. Se conciso pero
especifico. Esta es tu intervencion individual; despues veras la de los demas."""


async def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    repo_path = os.path.abspath(os.path.expanduser(sys.argv[1]))
    if not os.path.isdir(repo_path):
        print(f"No existe el directorio: {repo_path}")
        sys.exit(1)

    tema = sys.argv[2] if len(sys.argv) > 2 else (
        "Critiquen el diseño general del repo: arquitectura, calidad, riesgos y "
        "qué cambiarían. ¿Vale la pena como está o necesita refactor?")

    query = build_query(repo_path, tema)

    print(f"=== DEBATE DEL CONSEJO ===")
    print(f"Repo: {repo_path}")
    print(f"Tema: {tema}\n")
    print("Lanzando 4 agentes (claude / codex / gemini / deepseek) sobre el repo...\n")

    t = time.time()
    s1, s2, s3, meta = await run_full_council(query, cwd=repo_path)

    print("\n" + "=" * 70)
    print("ETAPA 1 — POSTURAS INDIVIDUALES")
    print("=" * 70)
    for r in s1:
        print(f"\n### {r['model'].upper()}\n{r['response']}\n")

    print("=" * 70)
    print("RANKING AGREGADO (mejor a peor, segun los pares)")
    print("=" * 70)
    for a in meta.get("aggregate_rankings", []):
        print(f"  {a['model']:10s}  rank medio {a['average_rank']}  ({a['rankings_count']} votos)")

    print("\n" + "=" * 70)
    print(f"ETAPA 3 — SINTESIS DEL CHAIRMAN ({s3['model']})")
    print("=" * 70)
    print(s3["response"])

    print(f"\n--- Debate completado en {time.time() - t:.0f}s ---")


if __name__ == "__main__":
    asyncio.run(main())
