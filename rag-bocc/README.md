# Corpus RAG – Banco de Occidente (sitio público)

Extraído el 2026-10-01 (lote 1: 308 URLs; lote 2: rastreo de personas + empresas + inversionistas, 2022-2026, sin licitaciones). **1175 documentos; 958 indexables por defecto.** Fase 1 aplicada: clasificación, vigencia, idioma, duplicados y auditoría.

## Estructura

- `documentos/<segmento>/<área>/NNN_nombre.md`: un archivo por URL con frontmatter YAML y el contenido en Markdown (los PDF llevan `<!-- página N -->`).
- `corpus.jsonl`: los mismos documentos, uno por línea (campo `texto`), con todos los metadatos.
- `indice.json`: metadatos sin texto.
- `auditoria/`: `reporte.md`, `auditoria.csv` (una fila por documento), `casi-duplicados.csv`, `muestra-revision.md` (lista para revisión humana).
- `omitidos-lote2.json`, `enlaces-pendientes.json|txt`: lo que no entró y por qué.

## Campos de metadatos (frontmatter y `corpus.jsonl`)

| Campo | Valores / significado |
|---|---|
| `segmento` | personas · empresas · inversionistas |
| `tipo_doc` | producto_pagina, guia_de_uso, tarifas_tasas, terminos_condiciones, contrato_formato, reglamento_politica, estado_financiero, informacion_relevante, asamblea_accionistas, calificacion, emision_valores, informe_gestion_sostenibilidad, instructivo_canales, estudio_economico, tributario, legal_normativa, seguro_brochure_clausulado, faq_ayuda, educacion_financiera, institucional, empleo_cultura, externo_sin_contenido, otro |
| `area` | tarjetas_credito, cuentas, creditos_*, seguros, leasing_empresas, factoring, inversion, comercio_exterior_tesoreria, pagos_recaudos_canales, estados_financieros_inversionistas, gobierno_corporativo, sostenibilidad, cumplimiento_riesgos, datos_personales, estudios_economicos, tributario, educacion_financiera, institucional, transversal_formatos_politicas, externo, otros |
| `idioma` | es · en · mixto · indeterminado (heurística de palabras frecuentes) |
| `estado_vigencia` | `vigente` (página actual o sin fecha de caducidad detectada), `vencido` (el documento declara una vigencia ya terminada), `historico` (informe de un periodo/año anterior a 2026), `periodo_reciente` (informe 2026), `por_verificar` (tarifas, T&C, formatos o guías sin fecha de vigencia detectable) |
| `anio_documento`, `periodo_fin`, `vigente_desde`, `vigente_hasta` | extraídos del nombre, del texto o de frases de vigencia («Vigencia del 01 al 30 de septiembre de 2026»); pueden ser `null` |
| `clasificacion_acceso` | `publico` (todo el corpus actual es público) |
| `indexar` / `motivo_no_indexar` | `false` para duplicados exactos, casi-duplicados ≥ 0,95, sin contenido útil e inglés |
| `flags` | alertas de calidad (ver `auditoria/reporte.md`) |
| `hash_contenido`, `duplicado_de`, `casi_duplicado_de`, `similitud` | control de duplicados |
| `titulo_original` | solo si el título se corrigió por no coincidir con la página |
| `etiquetas_origen` | etiquetas del JSON original (lote 1) o asignadas por regla de ruta (lote 2) |

> Todas las clasificaciones, la vigencia y el idioma son **heurísticas** (reglas sobre URL, título y texto), no verdad validada: úselas como filtros iniciales y corrija con la revisión humana.

## Resumen

| segmento | docs | indexables |
|---|---|---|
| personas | 670 | 545 |
| inversionistas | 254 | 174 |
| empresas | 251 | 239 |

| tipo_doc | docs |
|---|---|
| producto_pagina | 293 |
| contrato_formato | 87 |
| estado_financiero | 83 |
| estudio_economico | 73 |
| reglamento_politica | 72 |
| instructivo_canales | 63 |
| informacion_relevante | 63 |
| informe_gestion_sostenibilidad | 62 |
| otro | 56 |
| terminos_condiciones | 49 |
| asamblea_accionistas | 46 |
| guia_de_uso | 36 |
| seguro_brochure_clausulado | 34 |
| tributario | 27 |
| legal_normativa | 24 |
| educacion_financiera | 21 |
| tarifas_tasas | 16 |
| institucional | 15 |
| emision_valores | 15 |
| calificacion | 13 |
| externo_sin_contenido | 12 |
| faq_ayuda | 10 |
| empleo_cultura | 5 |

| estado_vigencia | docs |
|---|---|
| vigente | 689 |
| historico | 241 |
| por_verificar | 227 |
| periodo_reciente | 15 |
| vencido | 3 |

## Notas de calidad

- PDF: `pdftotext -layout`; los de pocas palabras por página se pasaron por OCR en español. Excel/Word: texto de celdas/párrafos; hojas muy grandes truncadas a 4.000 filas.
- Excluidos a propósito: licitaciones, documentos con contenido anterior a 2022 en inversionistas/sostenibilidad, una lista de NIT y nombres y el listado masivo de corresponsales.
- Tarifas y tasas **caducan cada mes** (p. ej. «Vigencia del 01 al 30 de septiembre de 2026»): no usarlas como fuente de verdad; consultar fuente estructurada.
- La revisión humana de la muestra (`auditoria/muestra-revision.md`) está **pendiente**.
