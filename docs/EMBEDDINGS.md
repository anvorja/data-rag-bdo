# Comparación de modelos de embeddings (fase 3a-bis)

Estado: **comparación en dev terminada; decisión pendiente** · actualizado 2026-10-02. Resultados sobre el split `dev` del golden set; `test` no se ha tocado.

## Por qué se hizo
La fase 3a usó `intfloat/multilingual-e5-small` (local, CPU) por rapidez para iterar, no por ser el mejor. Un colega
recomendó comparar modelos de alta calidad por API y guardar los vectores en archivos propios
(sin vector DB ni servicio de embeddings aparte), y decidir con un test sobre las preguntas propias, no con benchmarks genéricos.
Los datos son públicos (sitio web del banco), por eso se pueden enviar a Voyage/OpenAI para evaluar. En producción las
consultas de clientes sí pasarían por el proveedor: eso depende de la decisión de residencia de datos (CE 005/2019, CE 007/2018).

## Cómo se hizo
- **Mismos fragmentos y mismas preguntas** para todos: 21.972 fragmentos (chunking estructural, ≤1.500 caracteres), 167 preguntas de `dev` y 168 variantes coloquiales.
- Dos variantes por modelo: con el prefijo de metadatos (`ctx1`: título, tipo, área, segmento, vigencia) y sin él (`ctx0`).
- Dos sistemas: **denso solo** y **híbrido** (BM25 + denso, RRF k=60) con **filtro de vigencia**.
- Métrica principal: `cita@k` (la cita literal de la fuente aparece entre los k primeros fragmentos), MRR y `doc@10`.
- Vectores normalizados; búsqueda exacta con NumPy (producto punto = coseno). 1.024 dimensiones en Voyage, 1.536 en OpenAI.
- `voyage-context-4` recibe los fragmentos agrupados por documento (los documentos largos se parten en grupos de ≤16.000 tokens porque el modelo admite 32.000 y no trunca).

## Resultados en `dev` (híbrido + vigencia, con contexto de metadatos)
| Modelo | cita@1 | cita@10 | MRR | variantes cita@10 | variantes MRR |
|---|---|---|---|---|---|
| e5-small (línea base) | 0,611 | 0,940 | 0,729 | 0,804 | 0,542 |
| text-embedding-3-small | 0,599 | 0,922 | 0,705 | 0,780 | 0,512 |
| voyage-4-lite | 0,617 | 0,952 | 0,740 | 0,851 | 0,561 |
| voyage-4 | 0,659 | 0,946 | 0,762 | 0,845 | 0,579 |
| voyage-4-large | 0,659 | 0,952 | 0,768 | 0,875 | 0,622 |
| **voyage-context-4** | **0,689** | 0,946 | **0,787** | **0,887** | **0,646** |

Denso solo (cita@10): voyage-context-4 0,934 · voyage-4-large 0,940 · voyage-4 0,940 · e5 0,874 · text-embedding-3-small 0,814.

Lecturas: (1) el contexto de metadatos ayuda en todos los modelos (1-5 puntos); (2) `text-embedding-3-small` queda por debajo de e5 y se descarta;
(3) los modelos Voyage 4 mejoran sobre e5 sobre todo en el denso solo y en las preguntas coloquiales; (4) con 167 preguntas el margen
de error es de unos ±3-4 puntos: las diferencias entre `voyage-context-4`, `voyage-4-large` y `voyage-4` **no son concluyentes**;
(5) el set sintético se parece al texto fuente y favorece a BM25: con consultas reales las diferencias pueden ser mayores.

Archivos: `rag-bocc/evaluacion/fase3a/comparacion-embeddings-dev.json`.

## Con reranker `bge` (top-20, híbrido + vigencia + contexto, `dev`)
| Modelo de embeddings | cita@1 | cita@10 | MRR | variantes cita@10 | variantes MRR |
|---|---|---|---|---|---|
| e5-small (referencia) | 0,808 | 0,958 | 0,870 | no medido | no medido |
| voyage-4-large | 0,802 | 0,964 | 0,870 | 0,911 | 0,664 |
| voyage-context-4 | 0,808 | 0,970 | 0,876 | 0,905 | 0,649 |

**Con reranker las diferencias desaparecen** (≤1,2 puntos en cita@10 y 0,6 en MRR, muy por debajo del margen de error de ±3-4 puntos).
El reranker corrige lo que el modelo de embeddings ordena peor: la ventaja de `voyage-context-4` (+8 puntos de cita@1 sin reranker) se diluye.
Los modelos de pago se justificarían solo si no se usa reranker, o por las preguntas coloquiales (no medidas para e5 con reranker).
Archivo: `rag-bocc/evaluacion/fase3a/embeddings-reranker-dev.json`.

## Costo y límites observados
~9,7 M tokens por configuración con contexto y ~9,0 M sin él; ~93 M en total. Voyage tardó 1-3 min por configuración;
OpenAI ~7 min por su tope de 1 M tokens/min (el script lo espera). Consumo real: ver el panel de cada proveedor y `_raw/emb/uso.json`.

## Cómo reproducirlo
```bash
set -a; . ./.env; set +a                       # VOYAGE_API_KEY / OPENAI_API_KEY (ver .env.example)
python pipeline/13_embeddings_api.py --modelos voyage-4 voyage-context-4 --ctx 1 0 --splits dev
python pipeline/14_comparar_embeddings.py      # denso e híbrido por modelo
python pipeline/15_embeddings_con_reranker.py --modelos voyage-context-4 voyage-4-large   # + reranker bge (CPU: lento)
```
Los vectores se guardan en `_raw/emb/` (no versionado). Convención: `<modelo>__<chunking>__ctx<0|1>.npy` + `.ids.json`
(orden de los `cid` de fragmentos, que el evaluador verifica) y `q__<modelo>.npz` (vectores de consultas). Carpeta plana a propósito:
el prefijo ya identifica el modelo y los scripts buscan por nombre; si crece mucho se pasa a una subcarpeta por modelo y se ajusta `13`/`14`/`15`.

## Pendiente
- ~~Híbrido + reranker `bge`~~ hecho: sin diferencias apreciables entre modelos. Falta medir e5+bge en las variantes coloquiales para cerrar la comparación.
- Probar 512 dimensiones (Matryoshka) para reducir almacenamiento.
- Una sola corrida en `test` con el modelo elegido.
- Candidato local abierto (`bge-m3`) solo si se exige no depender de API externa; en CPU tarda varias horas.
