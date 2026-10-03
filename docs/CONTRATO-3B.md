# Contrato de la fase 3b: del fragmento recuperado a la respuesta al cliente

Estado: **propuesta para validar** (2026-10-03). Define qué entra y qué sale del asistente, y qué verifica el código **después** de que el modelo escribe.
No depende de qué LLM se elija (DeepSeek u OpenAI): lo que no se puede dejar al modelo se hace en código y se prueba.
Código: `pipeline/fase3b/contrato.py` (`python pipeline/fase3b/contrato.py --autoprueba`). Reglas de negocio de origen: `docs/DECISIONES.md`.

## Principio
El modelo **redacta**; el código **decide y verifica**. El modelo solo elige números de fragmento. Nunca produce URL, fechas de vigencia, títulos ni avisos: los pone el código desde el corpus.
Así una respuesta no puede citar una página que no existe ni inventar una vigencia.

## Flujo de un turno
1. **Inicio de chat (una sola vez):** aviso de que habla con un asistente virtual, no con una persona, y consentimiento para tratar sus datos (decisión de cumplimiento).
2. **Enmascaramiento:** se quitan nombres, cédulas y números de cuenta del texto **antes** de enviarlo a cualquier proveedor. Obligatorio. *Pendiente de construir y medir* (ver «Pendientes»).
3. **Clasificación de intención** (reglas + modelo pequeño o el mismo LLM):
   - queja, fraude o reclamación → acción `escalar` sin buscar nada: se remite al WhatsApp del banco;
   - datos personales de una cuenta concreta, saldos, movimientos → `escalar` (el asistente no accede a cuentas);
   - fuera del alcance del banco → `abstenerse`;
   - pregunta ambigua → `aclarar` (una pregunta corta);
   - el resto → `responder`, si el paso 5 lo permite.
4. **Recuperación** (lo medido en la fase 3a): BM25 + denso (RRF) → política **blanda** de vigencia (`vigencia.doc_ok_blanda`) → reranker top-20 (en desarrollo y pruebas: Voyage rerank-3) → entre 3 y 5 fragmentos.
5. **Suficiencia:** el umbral de recuperación **no basta** para abstenerse (AUROC 0,83). Un verificador (LLM con instrucción de «¿estos fragmentos contienen la respuesta?») decide `responder` o `abstenerse`. Se mide con las preguntas `sin_respuesta` y `fuera_alcance` del golden.
6. **Generación:** el LLM recibe los fragmentos numerados `[1]…[n]` con su texto y responde en JSON (esquema abajo).
7. **Verificación determinista** (`contrato.verificar`). Si falla algún control, se reintenta una vez con el error como instrucción; si vuelve a fallar, se cambia a `abstenerse` y se registra el caso.
8. **Armado final:** el código añade las citas (URL, título, página) y los avisos de vigencia; el cliente ve el texto, las fuentes y los avisos.

## Esquema de salida del modelo
```json
{ "accion": "responder | abstenerse | escalar | aclarar",
  "respuesta": "texto en español para el cliente, con marcas [1], [2] donde use un fragmento",
  "citas_usadas": [1, 2] }
```
Y lo que construye el código para cada cita (`contrato.construir_citas`):
```json
{ "n": 1, "doc_id": "147", "url": "https://…", "titulo": "titulo_publico del corpus", "pagina": 3, "encabezado": "Tarifas",
  "fragmento": "147#4", "estado_vigencia": "vigente", "vigente_hasta": "2026-12-31", "aviso": "Vigente hasta el 31 de diciembre de 2026." }
```

## Reglas de cita
- Toda respuesta `responder` cita al menos un fragmento y solo fragmentos que se le presentaron.
- La URL sale de `corpus.jsonl` por `doc_id`. Para PDF, la URL del documento más el número de página del fragmento.
- Si un documento tiene versión vigente y otra `historico` (campo `version_de`), se cita la vigente, salvo que la pregunta pida el pasado.
- Si dos fuentes se contradicen, **manda el PDF oficial** sobre la página web, y el caso se registra para el ingeniero del RAG.
- 13 documentos viven en dominios de terceros (aliados, entes oficiales): se citan con su URL, y la respuesta debe presentarlos como fuente externa. Las 26 URL de `portalpublico.bancodeoccidente.com.co` son del banco.
- El corpus puede contener errores de origen (p. ej. doc 751, título «Apple Pay» sobre texto de Google Pay); mientras el banco no los corrija, quedan en `rag-bocc/auditoria/reporte.md`.

## Avisos de vigencia (los pone el código, `vigencia.aviso`)
| Estado | Qué ve el cliente |
|---|---|
| `vigente` con fecha de fin | «Vigente hasta el …» |
| `vencido` | «Esta información ya no está vigente: … terminó el …». Se responde igual, con la advertencia delante |
| `historico` | solo se muestra si pregunta por el pasado; aviso de versión anterior y la fecha a la que corresponde |
| `vigente_hasta_reemplazo` (tasas) | «Estas tasas se publican cada mes y las últimas cargadas cubren hasta …» |
| `sujeta_a_existencias` | «Esta campaña termina cuando se agote el cupo…» |
Una respuesta histórica debe **decir la fecha** a la que corresponde el dato (decisión de las directivas).

## Controles deterministas (`contrato.verificar`)
| Código | Qué detecta |
|---|---|
| `accion_invalida` | acción fuera de las cuatro permitidas |
| `sin_citas` | `responder` sin ningún fragmento citado |
| `cita_inexistente` | cita a un número que no estaba en el contexto |
| `cifra_no_respaldada` | una cifra de la respuesta que no aparece en los fragmentos citados ni en la pregunta (1.500.000 y 1500000 cuentan igual) |
| `url_ajena` | una URL en el texto que no es de las citas ni el WhatsApp del banco |
| `version_antigua` | cita un documento histórico cuando existe versión vigente y la pregunta no es temporal |
| `escalamiento_sin_whatsapp` | `escalar` sin el enlace de WhatsApp |
| `citas_sin_responder` | `abstenerse`/`aclarar` con citas |
La comprobación de cifras es una **heurística de dígitos**: atrapa valores inventados, pero no que una cifra real se use en el contexto equivocado. Eso lo mide la evaluación con jueces (abajo).

## Escalamiento
Quejas, fraude y reclamaciones **no se tratan en el asistente**: se remite al WhatsApp **+57 318 671 4836** (`https://api.whatsapp.com/send?phone=573186714836`), sin más trámite.
**Por confirmar con el banco** que ese número sea el de quejas/fraude/reclamaciones (el corpus tiene otros dos de servicios concretos que no deben usarse para eso).

## Existencia de las URL
- **Siempre (en cada respuesta):** la URL citada debe estar en `corpus.jsonl` (garantizado por construcción: el modelo no escribe URL y `url_ajena` bloquea las que intente colar).
- **Periódica (fuera del chat):** comprobar que las URL del corpus responden. El sitio usa CloudFront y devuelve 403 a clientes sin navegador, así que la comprobación se hace con el mismo método de recaptura (Playwright), mensualmente, junto con la actualización de tasas. Una URL caída genera alerta para el ingeniero del RAG; la respuesta sigue citando el documento (el contenido citado es el que tenemos guardado).

## Cómo se evalúa la fase 3b
El golden (290 preguntas, plata) ya trae `accion_esperada`, `debe_abstenerse`, `fuentes` y `respuesta_referencia`. Métricas propuestas, con el mismo cuidado de la fase 3a (desarrollo vs. prueba congelada, un solo uso de la prueba):
- **Acción correcta** (responder / abstenerse / escalar / aclarar) contra `accion_esperada`.
- **Fundamentación:** fracción de afirmaciones respaldadas por los fragmentos citados (juez LLM, con muestra revisada a mano).
- **Cita correcta:** la cita incluye una fuente esperada (equivalente a cita@k de la 3a, pero sobre lo que ve el cliente).
- **Aviso correcto:** si la fuente es `vencido`/`historico`/`sujeta_a_existencias`, el aviso aparece; si es vigente, no hay avisos falsos.
- **Tasa de bloqueo del verificador** (cuántas respuestas el código rechaza): indicador de calidad del modelo y del prompt.
- Con y sin enmascaramiento de datos personales, para medir lo que cuesta en calidad.

## Pendientes y decisiones abiertas
| Tema | Estado |
|---|---|
| LLM (DeepSeek u OpenAI) | sin decidir; el contrato no depende de ello. Probar ambos con el golden de desarrollo |
| Capa de enmascaramiento de nombres, cédulas y cuentas | por construir; medir falsos negativos |
| Verificador de suficiencia | por construir y medir con `sin_respuesta` y `fuera_alcance` |
| WhatsApp de quejas | por confirmar con el banco |
| Documentos internos | solo público hasta que haya autenticación; diseño de colección aparte pendiente de seguridad |
| Preguntas multi-turno (seguimiento) | el contrato cubre un turno; falta definir reescritura de la pregunta con el historial |
| Formato visual de citas y avisos en el canal | depende del canal (web, WhatsApp); fuera del contrato |
