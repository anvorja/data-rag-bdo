# Estado del corpus antes del embedding: metadatos, fechas y enlaces a documentos oficiales

Actualizado 2026-10-02. Resume qué está resuelto en el corpus (fase 1) y qué falta antes de entregar respuestas con enlaces (fase 3b).

## Qué se ordena antes y qué se prueba después
- **Antes del embedding (fase 1, hecho):** extracción, limpieza, clasificación (`tipo_doc`, `area`, `segmento`, `idioma`), fechas, estado de vigencia,
  deduplicación (exacta y casi duplicada), bandera `indexar` y auditoría. El resultado son 1.175 documentos, 958 indexables.
- **Las pruebas de embeddings no reorganizan los datos.** Comparan cómo recupera cada modelo sobre los *mismos* fragmentos;
  lo que cambia entre pruebas es el modelo, no el corpus. Si el corpus cambia, hay que recalcular los vectores y volver a medir.

## Enlace al documento oficial
- Cada documento indexable tiene `url` (958 de 958). Para un PDF es la URL del propio archivo (p. ej. los T&C de la campaña
  «Soy independiente, abro mi cuenta corriente y no estoy solo» es el documento 033, con su URL `…/documents/33634/0/Terminos+y+Condiciones+SOY+INDEPENDIENTE…pdf`);
  para una página, la URL de la página. Todos son de acceso público (`clasificacion_acceso = publico`).
- Cada fragmento conserva el `doc` del que sale, y de ahí se obtiene la URL, la página del PDF (cuando la hay) y el título.
  **Por ahora la URL no viaja dentro del índice de fragmentos: se une por `doc` al responder.** Es trivial, pero hay que hacerlo explícito en la fase 3b.
- Por eso el escenario «te respondo y además te paso el PDF oficial» es **posible con lo que hay**: la respuesta cita el documento fuente con su URL.
  Lo que **no existe todavía** es una tabla de relaciones «página ↔ documentos que ofrece» (la página de la campaña ↔ su PDF de T&C).
  Parte de esa información está dentro del texto: 146 documentos conservan enlaces Markdown a PDFs u otros documentos; el resto no.

## Cobertura de fechas y vigencia (958 documentos indexables)
| Campo | Con valor |
|---|---|
| `anio_documento` | 457 |
| `periodo_fin` (estados financieros: 39 de 39) | 44 |
| `vigente_desde` | 27 |
| `vigente_hasta` | 3 |
| Estado: vigente / histórico / por verificar / periodo reciente / vencido | 620 / 166 / 164 / 5 / 3 |

Las etiquetas de fecha **sí existen, pero son heurísticas** (se infieren del título, el texto y el nombre del archivo) y están incompletas:
164 documentos quedan «por verificar» (entre ellos el T&C de la campaña de ejemplo: año 2026, sin fechas de vigencia). El filtro de vigencia del recuperador
usa estas etiquetas, así que un error aquí se propaga a las respuestas sobre tasas, campañas y plazos.

## Límites conocidos (no ocultar)
- La clasificación y las fechas no están validadas por el dueño de cada contenido; la muestra de auditoría (142 documentos) no ha sido revisada por una persona.
- Hay contenido defectuoso en el sitio mismo (textos de plantilla del CMS, documentos internos publicados por error, cifras contradictorias entre páginas); ver `rag-bocc/auditoria/reporte.md`.
- Los resúmenes («resume el estado financiero de tal fecha») son una función de generación (fase 3b): la fecha pedida se resuelve con `periodo_fin`, y el enlace oficial con `url`.
  La fidelidad de esos resúmenes aún no se mide.

## Decisiones pendientes para cerrar esto
1. Contrato de respuesta de 3b: cada respuesta debe devolver citas con `titulo`, `url` y `pagina`, y la URL debe provenir del corpus, nunca generarse.
2. Construir la tabla de relaciones página → documentos a partir de los enlaces del sitio (rastreo ya hecho; falta extraerlos y validarlos).
3. Resolver las 164 vigencias «por verificar» con los dueños del contenido, empezando por campañas, tasas y T&C.

## Reglas de vigencia confirmadas con los expertos del banco (2026-10-02)
1. **Sin vencimiento:** formularios, cuentas, sostenibilidad, contratos, guías de uso y demás contenido sin fecha de fin se consideran vigentes mientras no se reemplacen.
2. **Tarifas** (`tarifas-persona-bdo`, `tarifas-empresariales-bdo`): vencen el **31 de diciembre de 2026**; el 1 de enero de 2027 se cargan PDFs nuevos.
3. **Tasas** (`tasas-personas-bdo`, `tasas-empresariales-bdo`): **mensuales**. Un ingeniero del RAG sube el PDF nuevo cada mes. La web ya publica octubre; nuestra captura del 1 de octubre tiene septiembre, así que hay que recapturarlas.
4. **Campañas con fecha de fin pasada** (p. ej. docs 182, 247, 731) quedan `vencido`; el ingeniero del RAG las actualiza con las campañas siguientes.
5. **Si la tasa o tarifa del periodo no está cargada** (se publican el día 1 de cada mes), el último documento sigue valiendo hasta que cambie, pero el asistente informa la fecha hasta la que llegaba y avisa que debe estar atento a la actualización. Ver `DECISIONES.md`.
6. **Las URL son «vivas»** (el contenido cambia en la misma dirección). Exigencia de los directores: **versionamiento**. Al recapturar, si el contenido cambió, la versión anterior se conserva como histórica con su fecha de fin y nunca se sobrescribe.

Decisiones documento por documento: `rag-bocc/vigencia/decisiones.jsonl` (validado por el responsable del proyecto con los expertos). Propuestas automáticas: `rag-bocc/vigencia/propuesta.jsonl`.
