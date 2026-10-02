# Evaluación de recuperación — Fase 3a

Resultados de los experimentos sobre el golden set v0 (plata). **Se decide con `dev`; `test` se corrió una sola vez (informativo).**

| Archivo | Contenido |
|---|---|
| `resultados-dev-bm25.json` | BM25 con tres fragmentaciones (fija, estructural, estructural + contexto) |
| `resultados-<split>-denso-hibrido.json` | BM25, denso, híbrido (RRF) y filtro de vigencia |
| `resultados-<split>-denso-hibrido-{mmarco,bge}.json` | + reranker |
| `abstencion-dev.json` | señales de abstención por umbral |
| `fallos-dev.json` | dónde aparece el primer fragmento relevante y qué preguntas fallan |
| `configuracion-elegida.json` | configuración recomendada |

Reproducir: `.venv/bin/python pipeline/fase3a/embed.py intfloat/multilingual-e5-small estructural 0|1` y luego `pipeline/09…12`. La guía v2 (sección 3.5-3.6) interpreta los resultados y sus límites.
