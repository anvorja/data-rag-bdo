# RAG Banco de Occidente — corpus, evaluación y pipeline

Insumos para un asesor virtual bancario (RAG) con la documentación **pública** de bancodeoccidente.com.co (personas, empresas, inversionistas, 2022-2026).

| Carpeta | Contenido |
|---|---|
| `rag-bocc/` | Corpus en Markdown (`documentos/<segmento>/<área>/`), `indice.json`, `auditoria/` y su propio README con el esquema de metadatos |
| `api/` | API del panel de pruebas con usuario real (FastAPI): chat, búsqueda en las fuentes, visor de documentos y valoraciones (ver `api/README.md`) |
| `pipeline/` | Scripts reproducibles: construcción del corpus, auditoría y validación (`validate.py`); fragmentos JS de rastreo en `pipeline/crawl/` |
| `docs/GITFLOW.md` | Modelo de ramas, PR (squash), protecciones y CI |
| `.github/` | Workflow de CI, rulesets de ramas, plantilla de PR |
| `RAG en producción … (v2).md` | Guía de buenas prácticas, auditoría de cobertura y hoja de ruta |
| `enlaces-*.txt|json` | Lista de URLs semilla y su clasificación original |

## Estado

- Fase 0-1 (corpus, rastreo, auditoría automática): hecha (2026-10-01). Pendiente la revisión humana de la muestra.
- Fase 3a (recuperación, sin LLM): configuración recomendada = fragmentación estructural + contexto, híbrido BM25+denso (RRF), filtro de vigencia y reranker (`rag-bocc/evaluacion/fase3a/`). Pendiente 3b (generación, requiere proveedor) y parsing de tablas.
- Fase 3b (asistente completo): contrato, enmascaramiento, compuerta de suficiencia, generación con DeepSeek y verificación en código, medido sobre `dev` (`docs/CONTRATO-3B.md`). API para la prueba con usuario real en `api/` (2026-11-20). Tasas y tarifas al día con la recaptura del 2026-11-20 (noviembre).
- Fase 2 (golden set v0): 290 pares plata con partición de prueba congelada (`rag-bocc/golden/`). Pendiente la validación por expertos para obtener el oro.

## Uso

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python pipeline/validate.py            # coherencia del corpus, tamaños, secretos
```

El corpus completo se regenera con los scripts `pipeline/01…05` a partir de los originales (`_raw/`, no versionados; ver `pipeline/README.md`).

## Reglas

- Solo documentación pública; sin datos de clientes. Se detectaron y no se alteraron 4 direcciones de correo personales de terceros en notas de estados financieros (procesos judiciales): conviene **enmascararlas al indexar** (ver guía, sección de datos personales).
- Sin secretos ni variables de entorno en el código o los datos (`.env.example` solo documenta nombres).
- Tasas y tarifas caducan cada mes: no usar los PDF como fuente de verdad numérica.
