# Contrato de la fase 3b: del fragmento recuperado a la respuesta al cliente

Estado: **propuesta para validar** (2026-10-03). Define qué entra y qué sale del asistente, y qué verifica el código **después** de que el modelo escribe.
No depende de qué LLM se elija (DeepSeek u OpenAI): lo que no se puede dejar al modelo se hace en código y se prueba.
Código: `pipeline/fase3b/contrato.py` (`python pipeline/fase3b/contrato.py --autoprueba`). Reglas de negocio de origen: `docs/DECISIONES.md`.

## Principio
El modelo **redacta**; el código **decide y verifica**. El modelo solo elige números de fragmento. Nunca produce URL, fechas de vigencia, títulos ni avisos: los pone el código desde el corpus.
Así una respuesta no puede citar una página que no existe ni inventar una vigencia.

## Flujo de un turno
1. **Inicio de chat (una sola vez):** aviso de que habla con un asistente virtual, no con una persona, y consentimiento para tratar sus datos (decisión de cumplimiento).
2. **Enmascaramiento:** se quitan nombres, cédulas y números de cuenta del texto **antes** de enviarlo a cualquier proveedor. Obligatorio. Construido con reglas y medido (ver «Enmascaramiento de datos personales»); los nombres sin pista en la frase siguen sin cubrirse.
3. **Clasificación de intención** (reglas + modelo pequeño o el mismo LLM):
   - queja, fraude o reclamación → acción `escalar` sin buscar nada: se remite al WhatsApp del banco;
   - datos personales de una cuenta concreta, saldos, movimientos → `escalar` (el asistente no accede a cuentas);
   - fuera del alcance del banco → `abstenerse`;
   - pregunta ambigua → `aclarar` (una pregunta corta);
   - el resto → `responder`, si el paso 5 lo permite.
4. **Recuperación** (lo medido en la fase 3a): BM25 + denso (RRF) → política **blanda** de vigencia (`vigencia.doc_ok_blanda`) → reranker top-20 (en desarrollo y pruebas: Voyage rerank-3) → entre 3 y 5 fragmentos.
5. **Suficiencia:** el umbral de recuperación de la fase 3a **no basta** para abstenerse (AUROC 0,83). Dos verificadores en `pipeline/fase3b/suficiencia.py`: el **puntaje del reranker Voyage rerank-3** (sin LLM, ya medido: ver «Verificador de suficiencia») y un **LLM juez** (DeepSeek, medido; OpenAI, armado). Combinados (abstenerse solo si ambos lo piden) dan el mejor resultado medido.
6. **Generación:** el LLM recibe los fragmentos numerados `[1]…[n]` con su texto y responde en JSON (esquema abajo).
7. **Verificación determinista** (`contrato.verificar`). Si falla algún control, se reintenta una vez con el error como instrucción; si vuelve a fallar, se cambia a `abstenerse` y se registra el caso.
8. **Armado final:** el código añade las citas (URL, título, página) y los avisos de vigencia; el cliente ve el texto, las fuentes y los avisos.

## Verificador de suficiencia (medido con Voyage, 2026-10-03)
Voyage no ofrece un LLM de chat (solo embeddings y rerankers), así que «el verificador con Voyage» usa el **puntaje de relevancia de rerank-3** del mejor fragmento: `por_rerank(puntajes, umbral)`.
Se calculó sobre el híbrido + política blanda de vigencia, top-20 (`python pipeline/24_suficiencia.py`; 360 consultas, ~3,0 M de tokens, 31 s). Muestra de `dev`: **27 preguntas sin respuesta** (incluye fuera de alcance, datos personales y adversariales) y **333 respondibles** (con variantes coloquiales). Salida: `rag-bocc/evaluacion/fase3b/suficiencia-dev.json`.
| Señal | AUROC | Umbral | Abstención correcta | Rechazo falso |
|---|---|---|---|---|
| Línea base 3a (coseno e5) | 0,83 | – | – | – |
| rerank-3, mejor fragmento | **0,976** | 0,7617 (rechazo falso ≤ 10 %) | 96,3 % (26 de 27) | 9,9 % |
| rerank-3, media de los 3 mejores | 0,966 | 0,668 (rechazo falso ≤ 10 %) | 81,5 % | 9,9 % |
Por tipo, con el umbral 0,7617: fuera de alcance 4/4, datos personales 4/4, adversariales 6/6, `sin_respuesta` 12/13.
**Lectura honesta:**
- Mejora mucho la línea base, pero un **rechazo falso del ~10 %** significa que 1 de cada 10 preguntas respondibles se contestaría «no tengo esa información»; es un costo real para el cliente. Con el umbral balanceado (0,7539) baja a 8,1 %.
- La muestra de preguntas sin respuesta es **pequeña (27)**: el margen de error es grande, y el umbral se eligió **sobre los mismos datos** que se miden (cifras optimistas). No se ha usado el conjunto de prueba.
- El umbral vale para **rerank-3 con este corpus y este chunking**; si cambia el reranker (o se pasa a `bge`), el corpus o el prefijo de contexto, hay que recalibrar con `24_suficiencia.py`.
- El golden es «plata» (sin validación experta): conviene que expertos revisen las 27 preguntas sin respuesta.
- El rerank-3 no distingue «el tema está pero falta el dato» de «hay respuesta» tan bien como lo haría un lector; por eso se midió también el LLM juez: la combinación baja el rechazo falso a la mitad (ver abajo).

### LLM juez con DeepSeek (medido el 2026-10-03, modo thinking desactivado)
`suficiencia.por_llm(pregunta, fragmentos, proveedor)` recibe los 4 mejores fragmentos tras el reranker y pide un JSON `{"suficiente": bool, "motivo": str}`; ante una respuesta ilegible se abstiene (en las 4 corridas hubo 0 ilegibles).
- **Modelos probados:** `deepseek-flash` y `deepseek-v4-pro` (nombres de la documentación oficial; el nombre anterior `deepseek-v4-flash` aún se acepta, pero ese modelo fue retirado).
- **Modo «thinking» desactivado en ambos.** En la API de DeepSeek viene **activado por defecto** (esfuerzo `high`) y con él se ignora `temperature`. El código lo apaga siempre con `extra_body={"thinking": {"type": "disabled"}}` y falla si la respuesta trae `reasoning_content` (documentación: api-docs.deepseek.com/guides/thinking_mode). Humo previo: ~1–1,5 s por llamada.
- **Dos versiones del prompt:** `p1` (inicial) y `p2` (añade que los fragmentos que permiten *corregir una premisa falsa* cuentan como suficientes). Con `p1`, 8 de las 16 respondibles rechazadas eran de premisa falsa (el juez decía «los fragmentos indican que no cobra cuota» y se abstenía, cuando justo eso permite corregir al cliente). `p2` se ajustó mirando `dev`, así que sus cifras son algo optimistas.
- Reproducir: `python pipeline/24_suficiencia.py --llm deepseek --modelo deepseek-flash --prompt p2` (los resultados se acumulan en `suficiencia-dev.json`; las respuestas del juez se guardan en `_raw/suficiencia/`).

Misma muestra de `dev` (27 sin respuesta, 333 respondibles); **abstención correcta** / **rechazo falso**; tokens y tiempo de una corrida de 360 consultas:
| Verificador | Prompt p1 | Prompt p2 | Tokens · tiempo |
|---|---|---|---|
| rerank-3 solo (umbral 0,7617) | 96,3 % / 9,9 % | – | (ya calculado con el reranker) |
| deepseek-flash solo | 96,3 % / 10,8 % | 88,9 % / 4,2 % | ≈0,69 M · 90 s |
| deepseek-v4-pro solo | 96,3 % / 9,0 % | 92,6 % / 6,6 % | ≈0,69 M · 151–163 s |
| rerank-3 **y** flash piden abstenerse | **96,3 % / 4,8 %** | 88,9 % / 1,8 % | |
| rerank-3 **y** v4-pro piden abstenerse | 96,3 % / 4,5 % | 92,6 % / 3,6 % | |
| rerank-3 **o** flash piden abstenerse | 96,3 % / 15,9 % | 96,3 % / 12,3 % | |
Lectura:
- **Combinar baja el rechazo falso a la mitad sin perder abstención** (con `p1`: de ~10 % a ~4,5–4,8 % manteniendo 26 de 27). Ninguno de los dos verificadores solo lo logra: uno corrige los errores del otro.
- **`p2` intercambia un error por otro:** rechaza menos respondibles, pero deja pasar 2–3 de las 27 sin respuesta más. Cuál conviene depende de qué cueste más: contestar sin respaldo (lo atrapan después las verificaciones de cita y cifras) o decir «no sé» sin necesidad.
- **`deepseek-v4-pro` no es mejor que `deepseek-flash`** en lo que mide este conjunto: las diferencias (≤ 2–3 preguntas) están dentro del ruido (1 pregunta respondible ≈ 0,3 puntos; 1 sin respuesta ≈ 3,7 puntos) y tarda ~1,7 veces más. Con los mismos tokens, `flash` es la opción razonable para esta tarea; el precio por token no se verificó.
- **La pregunta que se escapa siempre** es «¿Cuál es el cupo máximo de la tarjeta Visa Infinite?»: el tema está en la documentación pero el dato no, y ninguno de los tres lo detecta. Es el tipo de caso difícil que solo un lector (o la verificación de cifras tras generar) atrapa.
- Recomendación provisoria: **rerank-3 + `deepseek-flash` (thinking desactivado) y abstenerse solo si ambos lo piden**, con `p1` o `p2` según el costo que el banco asigne a cada error. Falta confirmarla en una muestra mayor y revisada por expertos.
**Dónde está la clave:** `.env` de la raíz (ignorado por git), línea `DEEPSEEK_API_KEY=<clave>`; para OpenAI, `OPENAI_API_KEY` y `OPENAI_MODEL_JUEZ=<modelo de chat>`. Luego `set -a; . ./.env; set +a`. Nunca en el código ni en el chat.
Los casos del golden son preguntas sintéticas sin datos personales; en producción el texto del cliente pasa por la capa de enmascaramiento antes de llegar a cualquier LLM.

## Enmascaramiento de datos personales (medido el 2026-10-03)
`pipeline/fase3b/enmascarar.py`: `enmascarar(texto)` (con `ner=False` solo reglas) → texto con marcas `[DOCUMENTO]`, `[CUENTA]`, `[TARJETA]`, `[CLAVE]`, `[TELEFONO]`, `[CORREO]`, `[DIRECCION]`, `[NOMBRE]`, `[NUMERO_PERSONAL]` y un resumen de **tipos y cuentas** (nunca el valor, para poder registrar sin guardar datos personales). Datos con formato: reglas, sin dependencias. **Nombres sueltos: reconocedor de entidades spaCy `es_core_news_md`** (`requirements-ml.txt`), con filtros contra falsos positivos: solo nombres propios con mayúscula inicial (también en tandas EN MAYÚSCULAS), nunca abreviaturas (`M.V.`, `E.A.`) ni nada que aparezca en títulos, encabezados o frases en mayúscula del corpus (productos, entidades, personas públicas). Sin spaCy instalado, funciona solo con reglas. No toca los números públicos del banco (NIT, WhatsApp) ni montos ni años.
Medición (`python pipeline/25_enmascaramiento.py`) con **datos inventados** escritos por el proyecto (`rag-bocc/evaluacion/fase3b/pii-sintetico.jsonl`: 62 mensajes) y con las 593 preguntas del golden:
| Qué se mide | Resultado |
|---|---|
| Datos con formato claro (cédula, NIT, cuenta, tarjeta con Luhn, clave/PIN/CVV/OTP, celular, fijo, correo, dirección, nombre con pista como «me llamo…», «a nombre de…», «señor…») | **36 de 36 enmascarados** |
| **Nombres propios sueltos nuevos** (18 frases con nombres que NO se usaron para ajustar los filtros) | **15 de 18 con NER** (solo reglas: 1 de 18). Los 15 detectados incluyen todos los escritos con mayúscula inicial, uno solo en mayúsculas y nombres de pila solos («Luisa», «Samuel»); **los 3 que se escapan están escritos en minúscula** («pedro gomez») |
| Casos sin pista en la frase (nombre suelto de la primera tanda, cifras separadas por espacios, número escrito con letras, usuario/clave alfanumérica, fecha de nacimiento, últimos 4 dígitos) | 7 de 13: se cubren los nombres; quedan sin cubrir las cifras con espacios, el número con letras, el usuario/clave, los últimos 4 dígitos y la fecha de nacimiento |
| Falsos positivos en 20 mensajes benignos (montos, tasas, años, NIT del banco, preguntas generales) | 0 de 20 |
| Falsos positivos en las 593 preguntas del golden, **con NER** | 2, y las dos son preguntas del golden con cédula real, así que **enmascarar es lo correcto** |
**Lectura honesta:**
- El 100 % en datos con formato **no es una garantía**: los casos los escribió el mismo equipo que las reglas y son pocos. Hay que probar con mensajes reales anonimizados del banco antes de confiar en la cifra.
- **Nombres en minúscula** («pedro gomez», «juan carlos rojas») **no se detectan**: el NER de spaCy depende de la mayúscula inicial. Es el hueco que sigue abierto frente a lo que exige cumplimiento, y en un chat el cliente escribe muchas veces así. Opciones: un modelo de entidades más robusto a minúsculas, pasar el texto por un normalizador de mayúsculas, o que un LLM local revise el texto (más lento); cada una se mide con este mismo conjunto.
- **El NER es un modelo mediano en CPU** (spaCy `md`): añade ~decenas de ms por mensaje (no se midió con rigor) y puede equivocarse con nombres poco frecuentes.
- La medición de nombres con 18 frases es **pequeña**: 15 de 18 tiene un margen amplio. Se necesita una prueba con mensajes reales anonimizados del banco.
- Los números que el cliente escribe **con letras o con espacios** ('1 0 9 8…') y las fechas de nacimiento tampoco se cubren.
- Un error del propio ejercicio, ya corregido: «cuenta activa 2025 2026» se tomaba por número de cuenta; ahora los pares de años se ignoran.
- El enmascaramiento va **antes de cualquier proveedor**, incluidos Voyage (reranker/embeddings de la consulta) y DeepSeek. La respuesta al cliente no necesita los valores originales.

## Uso del asistente para temas ajenos al banco (código, ciencia, tareas, inyección de instrucciones)
**En qué etapa se frena:** en la fase 3b, en **cuatro capas**, de la más barata a la más tardía. La primera es la importante: si la pregunta se frena antes de generar, el LLM redactor **nunca se llama** (no gasta ni puede ser engañado).
1. **Compuerta previa a la generación** (pasos 3 y 5 del flujo): el clasificador de intención y el verificador de suficiencia (rerank-3 + juez). Una pregunta de código o de anatomía no tiene fragmentos relevantes en el corpus del banco, así que el puntaje cae y el asistente responde `abstenerse` con un mensaje fijo («solo puedo ayudarte con productos y servicios del Banco de Occidente»).
2. **Instrucciones al redactor** (paso 6): solo puede usar los fragmentos entregados, responde en el JSON del contrato y no escribe código ni atiende otros temas. El texto del cliente va como mensaje de usuario, **nunca dentro de las instrucciones del sistema**.
3. **Verificación posterior** (`contrato.verificar`): bloquea respuestas con código (`contenido_fuera_de_alcance`), cifras no respaldadas, URL ajenas y citas inexistentes. Si el redactor «cedió» ante una instrucción, esto lo atrapa.
4. **Control operativo** (`pipeline/fase3b/limites.py`, hecho y probado con `--autoprueba`; se aplica **antes** de enmascarar y de llamar a cualquier proveedor): longitud máxima del mensaje (**600 caracteres**: ~4× el p99 de las preguntas del golden, que son sintéticas y cortas; **valor a calibrar con tráfico real**), **10 mensajes por minuto**, **60 por sesión**, y alerta cuando una sesión acumula **4 abstenciones seguidas** (señal de abuso o de tema ajeno insistente; una respuesta normal reinicia la cuenta). El tope de tokens de salida del generador es de 700. Los contadores no guardan el texto del cliente. Hoy viven en memoria del proceso: **en producción deben ir a un almacén compartido** (Redis o la propia PostgreSQL). Los cuatro valores son una propuesta sin respaldo de datos reales; se ajustan con el tráfico del piloto.
**Qué se midió** (`python pipeline/26_fuera_de_tema.py --llm deepseek-flash`; 33 sondas escritas por el proyecto en `fuera-de-tema.jsonl`; compuerta = rerank-3 por debajo de 0,7617 **y** juez deepseek-flash con thinking desactivado dicen «no hay respuesta»):
| Tipo de sonda | Frenadas |
|---|---|
| Código (Python, Java, SQL, JavaScript, bash, regex) | 7 de 7 |
| Ciencia, cultura general, recetas, deporte | 7 de 7 |
| Tareas ajenas (traducir, poemas, resúmenes, matemáticas) | 6 de 6 |
| **Mezcla banca + código** («script en Python que calcule el interés de un CDT…») | 4 de 4 |
| Inyección de instrucciones («ignora tus instrucciones…», «eres DAN…») | 5 de 5 |
| Competencia, cripto, bolsa | 3 de 4 |
La que pasó: «¿Qué tasa de CDT paga Bancolombia?». El corpus habla de CDT, el puntaje (0,77) quedó apenas sobre el umbral y el juez lo dejó pasar. El riesgo no es que el asistente dé la tasa de otro banco (no la tiene), sino que **responda con la tasa del Banco de Occidente como si fuera la de Bancolombia**. **Mitigación aplicada (2026-10-03, `contrato.verificar`, código `entidad_sin_respaldo`):** no se bloquea por nombre de entidad, porque el corpus legítimamente las menciona (28 documentos nombran a Bancolombia, 15 a Davivienda, 34 al Banco de Bogotá…, por cajeros, ACH y convenios) y 2 preguntas del golden preguntan, con razón, por cajeros de Bancolombia. La regla es: si la pregunta nombra otra entidad, la respuesta debe (a) citar un fragmento que la mencione, o (b) aclarar que solo informa del Banco de Occidente. Si no cumple, se reintenta con esa instrucción y, de fallar, el código antepone «Solo puedo informarte sobre productos y servicios del Banco de Occidente; no tengo información de {entidad}.». La lista de entidades (20 nombres) está en `contrato.ENTIDADES`: es fija y hay que mantenerla (nuevos bancos y fintech). Probado con 3 casos sintéticos en la autoprueba; la medición con el ciclo completo viene en el paso del generador.
**Límites de esta medición:** 33 sondas escritas por nosotros; un usuario real insiste, reformula y mezcla. No cubre conversaciones de varios turnos (un tema ajeno puede entrar poco a poco): **cada turno debe pasar su propia compuerta** con la pregunta ya reformulada, no solo el primero. Conviene repetir la prueba con intentos reales de abuso (equipo de seguridad o *red team*) antes del piloto.

## Ciclo completo sobre `dev` (primera medición, 2026-10-03)
Código: `pipeline/fase3b/asistente.py` (un turno: enmascarar → escalamiento por reglas → recuperar → compuerta rerank-3 **y** juez → generar con `deepseek-flash`, thinking desactivado, JSON → verificar en código con un reintento → citas y avisos puestos por el código) y `pipeline/27_ciclo_completo.py` (evaluación; **solo `dev`, no se tocó `test`**). Juez de corrección: `deepseek-v4-pro` (thinking desactivado) contra la respuesta de referencia y los fragmentos citados. Salida: `rag-bocc/evaluacion/fase3b/ciclo-completo-dev.json`.
**Estado de la corrida:** las **197 preguntas** principales de `dev` se evaluaron completas. De las **168 variantes coloquiales** solo 14 terminaron: la cuenta de DeepSeek se quedó sin saldo (error 402 *Insufficient Balance*) a mitad de las variantes. La evaluación es **reanudable** (`python pipeline/27_ciclo_completo.py` repite solo lo que falló), así que lo de las variantes queda pendiente de recargar saldo. Las cifras de abajo son de las 197 preguntas principales.
| Métrica (197 preguntas, `dev`) | Resultado |
|---|---|
| Acción correcta (responder / abstenerse-escalar / aclarar) | **94,4 %** (186 de 197) |
| Cuando debía responder: responde | 95,8 % |
| …y la cita incluye el documento esperado (o una versión equivalente) | 96,2 % |
| …y la respuesta es **correcta** según el juez (referencia) | **89,9 %** (98,1 % si se cuenta «parcial») |
| …y contiene afirmaciones **sin respaldo** en los fragmentos citados (juez) | **4,4 %** |
| Cuando debía abstenerse: se abstiene o escala | 96 % (24 de 25) |
| Cuando debía aclarar | 1 de 3 |
| Verificador en código | 4 reintentos de 211 respuestas (`cifra_no_respaldada` 2, `citas_sin_responder` 2); 0 bloqueos finales |
| Respuestas con aviso de vigencia | 21 de 175 |
| Costo y tiempo por caso (mediana) | ≈2.000 tokens del generador; 1,2 s con rerank en caché (en vivo se suma la llamada a Voyage, ~0,1 s, y la codificación de la consulta en CPU) |
**Qué falla y por qué** (los fallos de acción, cita y corrección se revisaron uno a uno):
- **4 de las 7 preguntas de premisa falsa se pierden en la compuerta** («¿Por qué el crédito rotativo cobra una cuota de manejo tan alta?»): el juez con el prompt `p1` dice «los fragmentos dicen que no cobra» y se abstiene. Es el defecto ya conocido de `p1`; el prompt `p2` lo corrige a costa de dejar pasar algo más de preguntas sin respuesta (ver tabla de la compuerta). **Pendiente medir `p2` en el ciclo completo** (`--prompt-juez p2`), donde el verificador posterior puede compensar ese riesgo.
- **Preguntas ambiguas:** solo 1 de 3 pide aclaración. «¿Qué tasa tienen?» la frena la compuerta con una abstención en vez de preguntar «¿de qué producto?». Falta una rama de aclaración antes de la compuerta (el juez podría devolver `ambigua`); muestra de 3, no concluyente.
- **La pregunta que se escapa siempre** (cupo máximo de la Visa Infinite) sigue respondiéndose (con una cifra de otra fuente).
- **6 respuestas citan documentos distintos del esperado**, casi todas en preguntas amplias («¿qué ofrece el banco al segmento de Gobierno?») donde hay varias fuentes razonables: es una medida estricta que subestima.
- **Errores de tablas** (el 4,4 % «sin respaldo» y varios «no/parcial» de `numerica_tabla`): el asistente toma la fila equivocada de una tabla (límite USD 400 cuando el de Master Card Pyme es USD 300) o suma datos de dos filas. El verificador de cifras no lo ve porque la cifra sí existe en los fragmentos; es el problema de tablas del chunking (pendiente: mini-benchmark de parsing de tablas) y de elegir la fila correcta.
- **Mezcla de versiones y fechas** («¿hasta cuándo fue vigente la campaña…?» da las dos vigencias; «¿aún puedo aprovechar el descuento…?» no afirma con claridad que ya terminó). El aviso formal lo agrega el código, pero el texto del modelo puede contradecirlo.
- **La tasa «vigente hoy» de Cuenta Activa** el golden la etiqueta `escalar`; el asistente responde con el aviso de vigencia (el comportamiento que decidió el banco). La etiqueta del golden está desactualizada frente a la política blanda.
**Cautelas:** el juez es un LLM, no una persona (se confirmó a mano que sus motivos son coherentes en los casos revisados, pero no se midió su acuerdo con expertos); el golden es «plata» sin validación experta; 197 preguntas dan un margen de ±2 a ±4 puntos; el prompt de la compuerta y las reglas se afinaron mirando `dev`; `test` queda para una sola corrida con la configuración final.

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
| `entidad_sin_respaldo` | la pregunta nombra otra entidad (Bancolombia, Davivienda, Nequi…) y ningún fragmento citado la menciona ni la respuesta aclara que solo informa del Banco de Occidente |
| `contenido_fuera_de_alcance` | la respuesta trae código (bloques ``` o instrucciones de programación): el asistente de un banco no escribe código |
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
| Capa de enmascaramiento | hecha (reglas + NER spaCy) y medida: datos con formato 36/36, nombres sueltos nuevos 15/18. Abierto: nombres en minúscula, cifras con espacios o con letras, y una prueba con mensajes reales anonimizados |
| Controles operativos anti-abuso | hechos y probados (`limites.py`); valores por calibrar con tráfico real y estado a mover a un almacén compartido |
| Variantes coloquiales del ciclo completo (168) y prompt `p2` en el ciclo completo | saldo recargado (2026-11-20); pendiente de correr (la evaluación es reanudable) |
| Prueba con usuario real | API lista (`api/`, 2026-11-20): chat, búsqueda en las fuentes, visor de documentos y valoraciones; registro solo con texto enmascarado. Falta el frontend (React + TypeScript) |
| Preguntas «este mes» que mezclan vencidos | la política blanda trae documentos vencidos (p. ej. tasas de 2025) junto a la versión vigente; el aviso sale, pero la respuesta cita ambos. Revisar con la prueba real si conviene preferir la versión vigente cuando la pregunta dice «hoy/este mes» |
| Tasas empresariales por tabla | «tasa de compras de la tarjeta de crédito empresarial» no recupera el PDF de tasas empresariales (tabla); prioridad del benchmark de tablas |
| Rama de aclaración antes de la compuerta (preguntas ambiguas: 1 de 3) | por construir |
| Prueba de abuso con intentos reales (*red team*) y conversaciones de varios turnos | pendiente |
| Verificador de suficiencia | medido con rerank-3 y con DeepSeek (flash y v4-pro, thinking desactivado); combinados: 96,3 % de abstención correcta con ≈4,5–4,8 % de rechazo falso (prompt `p1`). Falta una muestra mayor y revisada por expertos, y medir OpenAI si se elige |
| WhatsApp de quejas | por confirmar con el banco |
| Documentos internos | solo público hasta que haya autenticación; diseño de colección aparte pendiente de seguridad |
| Preguntas multi-turno (seguimiento) | el contrato cubre un turno; falta definir reescritura de la pregunta con el historial |
| Formato visual de citas y avisos en el canal | depende del canal (web, WhatsApp); fuera del contrato |
