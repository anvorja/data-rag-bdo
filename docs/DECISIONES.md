# Decisiones de diseño y reglas de negocio (confirmadas con expertos y directivas del banco)

Registro fechado. Lo que no está confirmado figura como **pendiente**. Última actualización: 2026-10-02.

## Vigencia y versionamiento
- Tarifas vencen el 31-dic-2026; tasas son mensuales y **se publican el día 1** de cada mes. Un ingeniero del RAG sube los PDF nuevos.
- **Entre el día 1 y la publicación, la tasa del mes anterior sigue valiendo** hasta que cambie. Implicación: para tasas, el estado no es «vencido» al terminar el mes sino
  «vigente hasta reemplazo»; el asistente debe decir con qué fecha quedó el último documento y avisar que se actualiza mensualmente.
- **Información histórica:** si el cliente pregunta por una tasa de un mes pasado o una campaña terminada, el asistente **responde con el dato histórico indicando expresamente la fecha** a la que corresponde.
- **Versionamiento obligatorio** (exigido por los directores): al recapturar una URL «viva», la versión anterior se conserva como histórica con su fecha de fin; nunca se sobrescribe.
- Campañas con fecha de fin cumplida quedan `vencido`; el ingeniero del RAG las actualiza con las siguientes.

## Estados de vigencia (tras validar los 164 «por verificar», 2026-10-02)
| Estado | Significado | Comportamiento del asistente |
|---|---|---|
| `vigente` | Vigente, con fecha de fin o sin vencimiento | Responde normalmente |
| `vigente_hasta_reemplazo` | Tasas del último mes publicado (docs 097 y 230) | Responde, indicando hasta qué fecha llegaba y que se actualiza cada mes |
| `sujeta_a_existencias` | Campaña sin fecha de fin que termina al agotarse el cupo (docs 927 y 947) | No la presenta como activa sin avisar: depende de disponibilidad y de lo que comunique el banco |
| `vencido` | Fecha de fin cumplida | Solo se recupera si se pregunta por ese periodo; responde con la fecha |
| `historico` | Versión anterior reemplazada (p. ej. tarifas antiguas, tasas de meses pasados) | Igual que `vencido` |
Resultado: 135 vigentes, 24 vencidos, 3 históricos (884, 892, 1066) y 2 sujetos a existencias entre los 164; más 097/230 como «vigente hasta reemplazo». Ya no queda ningún documento «por verificar».
`rag-bocc/vigencia/decisiones.jsonl` se aplica con `pipeline/05_escribir_y_auditar.py` (manda la última decisión por id) y los documentos validados llevan `vigencia_validada: true`.
El doc 806 (carta de Comware con la cédula de una persona) quedó **fuera del índice** (`motivo_no_indexar: contenido_sensible`). Indexables: 957.

## Recaptura del 2026-10-02 (versionamiento aplicado)
Se recapturaron las 4 URL vivas con `pipeline/17_recaptura.py` (en el navegador, con `fetch()`; los PDF quedan en `_raw/recaptura/`). Todas habían cambiado:
| URL | Versión anterior (histórica) | Versión nueva | Vigencia nueva |
|---|---|---|---|
| tarifas-persona-bdo | 227 | 1176 | 1-oct-2026 → 31-dic-2026 |
| tarifas-empresariales-bdo | 228 | 1177 | 1-oct-2026 → 31-dic-2026 |
| tasas-personas-bdo | 097 | 229 | 1-oct-2026 → 31-oct-2026 |
| tasas-empresariales-bdo | 230 | 1178 | 1-oct-2026 → 31-oct-2026 |
Ejemplos de cambio: tasa de compras empresarial 2,15 % (septiembre) → 2,11 % (octubre); «Retiro corresponsal bancario» $3.000 → $3.200 + IVA (tarifa vigente desde el 1-oct-26).
Las versiones nuevas llevan `version_de: <id anterior>`; las antiguas siguen en el corpus como `historico` (para preguntas sobre meses pasados). Las tasas de octubre quedan `vigente_hasta_reemplazo` hasta que se cargue noviembre.
Ya no hay riesgo de que el asistente responda con las tasas de septiembre como si fueran las actuales.

## Autoridad de las fuentes
- Si dos fuentes se contradicen, **manda el PDF oficial** sobre la página web. Cada inconsistencia genera una **alerta al ingeniero del RAG**.
- Responsable por tipo de contenido (campañas, tasas, contratos, seguros, sostenibilidad): las directivas confirman que se requiere un contacto por área. **Pendiente:** nombres/contactos.

## Escalamiento
- Quejas, fraude y reclamaciones **no se tratan en el asistente**: se remite al cliente al **WhatsApp** del banco, sin más trámite.
- El número principal aparece en el corpus 193 veces: **+57 318 671 4836** (`https://api.whatsapp.com/send?phone=573186714836`). Hay otros dos números de WhatsApp de servicios concretos
  (asistencia de viaje de tarjetas: 316 434 8887; línea de crédito hipotecario: 312 510 4844) que **no** se usan para quejas. **Por confirmar** que el principal sea el de quejas/fraude/reclamaciones.

## Datos personales y proveedores (respuestas de cumplimiento/directivas)
- **Se permite** enviar lo que escribe el cliente a servidores fuera de Colombia (OpenAI, DeepSeek).
- **Obligatorio quitar** nombres, cédulas y números de cuenta antes de enviar el texto al LLM (capa de enmascaramiento previa) y **pedir autorización del cliente** (consentimiento al iniciar el chat).
- **Aviso:** informar que el cliente habla con un **asistente virtual y no con una persona**, **una vez al inicio de cada chat** (no en cada respuesta). Sin frase legal fija por respuesta.
- Almacén de vectores: **PostgreSQL con pgvector** (decidido; 1.024 dimensiones caben: límite del índice `vector` 2.000, `halfvec` para más). LLM: **DeepSeek u OpenAI** (sin decidir).

## Documentos internos (decisión de diseño propuesta, pendiente de validar con seguridad)
- Delegada al proyecto. Propuesta: los documentos internos **no se mezclan** con el corpus público. Van en una colección aparte con `clasificacion_acceso` ≠ `publico` y un filtro por perfil
  **aplicado antes de la búsqueda** (no después de generar la respuesta). Hoy los 958 documentos indexables son `publico`. Mientras no exista autenticación de usuario, solo se indexa lo público.

## Pendientes de respuesta
- Contactos por área (campañas, tasas, contratos, seguros, sostenibilidad): confirmada la necesidad; faltan los nombres.
- Contenido publicado por error: no hace falta avisar a nadie en concreto; queda como hallazgo documentado en `rag-bocc/auditoria/reporte.md`.
