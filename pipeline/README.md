# Pipeline

Orden de ejecución (desde la raíz del repositorio; `RAG_BASE` es opcional):

| Paso | Script | Qué hace |
|---|---|---|
| 0 | `crawl/*.js` | Se ejecutan **en una pestaña del navegador** abierta en bancodeoccidente.com.co (Playwright). El sitio devuelve 403 a curl y Chrome headless; `fetch()` desde la pestaña sí funciona. Descarga HTML (extractor → texto Markdown) y documentos en lote (base64 → `_raw/dl/NNNN.dat`). |
| 1 | `01_build_lote1.py` | Lote 1: 308 URLs semilla → `rag-bocc/` |
| 2 | `02_build_lote2.py` | Lote 2: páginas nuevas + 776 documentos descargados (extracción en paralelo, OCR, dedupe) |
| 3 | `03_pdfstats.py` | Páginas e imágenes por PDF (`pdfinfo`, `pdfimages`) |
| 4 | `04_enriquecer.py` | Clasificación (`tipo_doc`, `area`, `segmento`), idioma, vigencia, casi-duplicados, alertas |
| 5 | `05_escribir_y_auditar.py` | Reescribe `documentos/<segmento>/<área>/`, `indice.json`, `corpus.jsonl` y `auditoria/` |
| 6 | `16_vigencia_propuesta.py` | Propone vigencias leyendo fechas del texto (`vigencia/propuesta.jsonl`); las decisiones humanas van en `vigencia/decisiones.jsonl` y las aplica el paso 5 |
| 7 | `17_recaptura.py` | Recaptura de documentos «vivos» (tarifas y tasas) **con versionamiento**: la versión anterior queda `historico`, la nueva enlaza con `version_de`. Luego ejecutar el paso 5 |
| 8 | `18_organizar_embeddings.py` | Migra los embeddings al formato por subcarpetas con hashes (una sola vez) |
| 9 | `19_relaciones.py` | Tabla página → documentos (`rag-bocc/relaciones.jsonl`) desde los enlaces del texto y el grafo del rastreo |
| 10 | `fase3b/contrato.py` | Contrato de la fase 3b: citas con URL del corpus, avisos de vigencia y verificaciones deterministas de la respuesta (`--autoprueba`). Ver `docs/CONTRATO-3B.md` |
| 11 | `24_suficiencia.py` | Verificador de suficiencia (abstención): puntaje de rerank-3 y, con `--llm`, un LLM juez (DeepSeek/OpenAI). Ver `docs/CONTRATO-3B.md` |
| 12 | `fase3b/enmascarar.py`, `25_enmascaramiento.py` | Capa de enmascaramiento de datos personales (cédulas, cuentas, tarjetas, claves, teléfonos, correos, direcciones, nombres con pista) y su medición con datos inventados |
| 13 | `26_fuera_de_tema.py` | Mide si la compuerta de suficiencia frena el uso del asistente para temas ajenos al banco (código, ciencia, tareas, inyección) |
| 14 | `fase3b/asistente.py`, `fase3b/recuperar.py`, `27_ciclo_completo.py` | Un turno completo del asistente (enmascarar → recuperar → compuerta → generar → verificar → citas y avisos) y su evaluación de punta a punta sobre `dev` (reanudable) |
| 15 | `fase3b/limites.py` | Controles anti-abuso y de costo: longitud máxima, mensajes por minuto y por sesión, alerta por abstenciones seguidas (`--autoprueba`) |
| – | `validate.py` | Validaciones de CI |

Requisitos del sistema: `poppler-utils` (`pdftotext`, `pdfinfo`, `pdfimages`, `pdftoppm`), `tesseract-ocr` + datos `spa`, Python 3.12, `lxml`.

Los originales (`_raw/`) **no se versionan**: guardarlos aparte y conservar un manifiesto con sus hashes para poder reproducir.
