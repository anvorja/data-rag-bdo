# Auditoría automática del corpus (Fase 1) — 2026-10-01

Documentos: **1178** · con texto propio: **1045** · duplicados exactos: 118 · casi-duplicados (Jaccard ≥ 0,8): 36 · sin texto: 15

## Distribución

| segmento | docs |
|---|---|
| personas | 671 |
| inversionistas | 254 |
| empresas | 253 |

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
| tarifas_tasas | 19 |
| institucional | 15 |
| emision_valores | 15 |
| calificacion | 13 |
| externo_sin_contenido | 12 |
| faq_ayuda | 10 |
| empleo_cultura | 5 |

| área | docs |
|---|---|
| estados_financieros_inversionistas | 175 |
| seguros | 96 |
| pagos_recaudos_canales | 95 |
| sostenibilidad | 92 |
| tarjetas_credito | 88 |
| cuentas | 86 |
| estudios_economicos | 79 |
| gobierno_corporativo | 72 |
| otros | 53 |
| creditos_vivienda | 39 |
| transversal_formatos_politicas | 39 |
| tributario | 33 |
| comercio_exterior_tesoreria | 31 |
| inversion | 26 |
| externo | 25 |
| creditos_consumo | 23 |
| institucional | 22 |
| leasing_empresas | 21 |
| educacion_financiera | 21 |
| cumplimiento_riesgos | 19 |
| creditos_vehiculo | 17 |
| tarjeta_debito_digital | 10 |
| datos_personales | 8 |
| factoring | 8 |

| idioma | docs |
|---|---|
| es | 1085 |
| en | 73 |
| indeterminado | 16 |
| mixto | 4 |

| estado_vigencia | docs |
|---|---|
| vigente | 824 |
| historico | 248 |
| por_verificar | 62 |
| vencido | 25 |
| periodo_reciente | 15 |
| vigente_hasta_reemplazo | 2 |
| sujeta_a_existencias | 2 |

## Alertas

| alerta | docs | qué significa / acción |
|---|---|---|
| plantilla_cms_limpiada | 274 |  |
| candidato_vlm | 154 | PDF con ≥3 imágenes grandes y poco texto por página → candidatos a descripción con VLM / OCR reforzado (sección 3 de la guía v2) |
| duplicado_exacto | 118 | mismo texto que otro documento; se conserva solo el primero |
| ingles | 73 | documento en inglés; excluir del índice por defecto del asesor en español (o enlazar con su equivalente) |
| tablas_numericas | 49 | muchas líneas con columnas numéricas (estados financieros): validar tablas con un parser de layout |
| poco_texto_por_pagina | 44 | < 300 caracteres por página → probable escaneado o capturas; revisar OCR |
| sin_fecha | 44 | tarifa/T&C/guía/informe sin año detectable → no se puede gobernar su vigencia |
| casi_duplicado | 36 | versión casi idéntica de otro documento (Jaccard ≥ 0,8); decidir cuál se indexa |
| ocr | 34 | texto obtenido por OCR (puede tener errores en cifras y nombres) |
| titulo_dudoso | 23 | el título HTML no coincide con la ruta (p. ej. título copiado de otra página) |
| tablas_markdown | 19 | página con tablas serializadas a Markdown |
| sin_texto | 15 | sin contenido extraíble (redes, cotizadores JS…) |
| muy_largo | 5 | > 1,5 M de caracteres; requiere chunking jerárquico por capítulo |
| mojibake | 5 | caracteres rotos (codificación) → revisar |
| version_nueva | 4 |  |
| vigencia_vencida | 3 | el propio documento declara una vigencia ya terminada |
| muy_corto | 2 | < 200 caracteres |

**Indexables por defecto: 961 de 1178** (excluidos: duplicados, casi-duplicados ≥ 0,95, sin contenido útil, inglés). Motivos: duplicado_exacto=118, ingles=73, sin_contenido_util=17, casi_duplicado=12, contenido_sensible=1.

## Hallazgos con impacto en el diseño

- **Vigencia vencida:** id 037 «TÉRMINOS Y CONDICIONES CAMPAÑA CONECTA AVAL   NACIONAL VF» declara vigencia hasta 2026-08-04 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 050 «Terminos y condiciones campana de gamificacion (1)» declara vigencia hasta 2024-12-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 099 «Términos y Condiciones   Embajadores Unicef 2026» declara vigencia hasta 2026-10-01 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 100 «Términos y Condiciones   Activa tu TC Unicef y conviértete en embajador 2026» declara vigencia hasta 2026-09-01 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 145 «tasas personas 2025 9» declara vigencia hasta 2025-12-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 182 «TyC Primas Junio (2)» declara vigencia hasta 2026-06-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 183 «TyC   Campaña Intereses no reclamados CDT Junio 2025» declara vigencia hasta 2025-06-17 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 247 «TyC Impulsa tu KUBO Rentable VF» declara vigencia hasta 2026-06-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 729 «tyc tasa 0 exito» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 730 «tyc alfa septiembre» declara vigencia hasta 2026-09-27 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 731 «tyc tasa 0 dafiti» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 733 «tyc arturo calle 1» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 734 «tyc tasa 0 exito a junio» declara vigencia hasta 2026-06-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 735 «tyc ollas y sartenes» declara vigencia hasta 2026-06-15 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 737 «tyc tasa 0 despegar» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 738 «tyc price travel septiembre» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 880 «tasas personas 2025» declara vigencia hasta 2025-05-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 926 «Términos y Condiciones de la campaña Credencial LATAM» declara vigencia hasta 2025-12-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 940 «Términos y condiciones Campaña» declara vigencia hasta 2026-09-30 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 943 «TÉRMINOS Y CONDICIONES DE LA CAMPAÑA “TERCERA CAMPAÑA SOMBRILLA – DUPLICA» declara vigencia hasta 2025-10-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 944 «Términos y Condiciones campaña cuenta de ahorros jóvenes – 16 de» declara vigencia hasta 2026-03-16 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 945 «TÉRMINOS Y CONDICIONES DE LA CAMPAÑA “Banca Diplomática» declara vigencia hasta 2025-10-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 946 «TÉRMINOS Y CONDICIONES DE LA CAMPAÑA “ABRE TU CUENTA NÓMINA Y» declara vigencia hasta 2025-12-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 956 «TÉRMINOS Y CONDICIONES DE LA CAMPAÑA» declara vigencia hasta 2025-07-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Vigencia vencida:** id 1115 «tyc campana q3» declara vigencia hasta 2025-10-31 (hoy 2026-10-01). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.
- **Sin fecha detectable:** 44 documentos de tarifas/T&C/guías/informes (lista en `auditoria.csv`, filtrar alerta `sin_fecha`).

## Archivos

- `auditoria.csv`: una fila por documento con métricas y alertas.
- `casi-duplicados.csv`: pares con similitud.
- `muestra-revision.md`: lista para la revisión humana del ~10 %.
