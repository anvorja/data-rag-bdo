# El reranker explicado paso a paso

Documento para leer con calma. Explica qué es un reranker, por qué lo usamos, qué resultados dio en nuestras pruebas y qué significan las
métricas. Todas las cifras salen de las evaluaciones del proyecto (carpeta `rag-bocc/evaluacion/fase3a/`) sobre el conjunto de **desarrollo** (`dev`) del golden set:
167 preguntas con fuente y 168 variantes coloquiales. Actualizado 2026-10-02.

---

## 1. El problema que resuelve

Un asistente RAG funciona en dos tiempos: primero **encuentra** los fragmentos de documentos que pueden contener la respuesta (recuperación)
y luego **redacta** la respuesta con esos fragmentos (generación). Si la recuperación falla, el generador no puede arreglarlo: o inventa o responde mal.
Por eso casi todo el trabajo de la fase 3a fue medir y mejorar la recuperación.

El corpus tiene **21.972 fragmentos** (trozos de hasta 1.500 caracteres). Para cada pregunta hay que escoger, entre esos 21.972,
los pocos fragmentos que sirven. Hacerlo bien y rápido es difícil, y por eso se hace en etapas.

## 2. La recuperación en etapas (un embudo)

```
Pregunta del cliente
   │
   ▼
[1] Búsqueda amplia y barata  →  200 candidatos
      · BM25 (palabras clave)
      · Búsqueda densa (embeddings, significado)
      · Se fusionan con RRF
   │
   ▼
[2] Filtro de vigencia  →  se quitan documentos vencidos/históricos (salvo que la pregunta sea de un periodo pasado)
   │
   ▼
[3] RERANKER  →  se queda con los 20 primeros candidatos y los REORDENA con un juicio más fino
   │
   ▼
[4] Los mejores 3-5 fragmentos van al generador (fase 3b)
```

La idea de fondo: la etapa [1] es **rápida pero tosca** (mira miles de fragmentos en milisegundos); la etapa [3] es **lenta pero precisa**
(mira pocos fragmentos, pero cada uno con mucho detalle). Combinar ambas da calidad sin pagar el costo de analizar todo con el método lento.

### 2.1 BM25: palabras clave
Cuenta qué palabras de la pregunta aparecen en el fragmento y cuán raras son en el corpus. Una palabra rara (por ejemplo «Kubo») pesa más que una común («cuenta»).
- Ventaja: encuentra con precisión nombres propios, cifras, códigos, siglas.
- Límite: si la pregunta usa otras palabras («plata» en vez de «dinero») no lo encuentra.

### 2.2 Búsqueda densa: significado (embeddings)
Un **modelo de embeddings** convierte cada texto en una lista de números (un vector: 384 números en e5-small, 1.024 en Voyage). Textos con significado parecido quedan con vectores cercanos.
Se calcula una vez para todos los fragmentos y se guarda (archivos `.npy`); al llegar una pregunta se convierte en vector y se buscan los fragmentos más cercanos.
- Ventaja: entiende sinónimos y paráfrasis.
- Límite: pierde precisión con cifras, nombres y detalles exactos, y comprime todo un texto en un solo vector, así que se pierden matices.

### 2.3 Fusión RRF (Reciprocal Rank Fusion)
BM25 y la búsqueda densa dan dos rankings distintos. RRF los combina sin tener que comparar sus puntuaciones (que están en escalas diferentes):
a cada fragmento le suma `1 / (60 + posición)` por cada ranking donde aparece. Si un fragmento está alto en ambos, gana. A esa mezcla la llamamos **híbrida**.

## 3. Qué es el reranker y por qué es diferente

Los embeddings son un **bi-encoder**: la pregunta y el fragmento se convierten en vectores *por separado* y luego se comparan.
Eso permite pre-calcular los vectores de los fragmentos (rápido), pero el modelo nunca ve la pregunta y el fragmento *juntos*.

Un reranker es un **cross-encoder**: recibe **la pregunta y el fragmento juntos** en una sola entrada y devuelve un solo número, «cuán bien responde este fragmento a esta pregunta».
Al leerlos juntos puede notar cosas que el bi-encoder no ve: que la cifra pedida coincide, que el fragmento habla del producto correcto y no de uno parecido, que la condición se aplica a otro segmento.

Analogía: el embedding es una bibliotecaria que, por el título y el resumen de cada libro, te trae 20 que parecen servir. El reranker es un experto que abre esos 20 libros, lee el pasaje
y te dice cuál responde de verdad, en qué orden. No puede revisar los 21.972, pero sí los 20 que le pasó la bibliotecaria.

**Costo:** hay que ejecutar el modelo una vez por cada par (pregunta, fragmento). Con 20 candidatos son 20 ejecuciones por pregunta. Por eso solo se aplica a los mejores candidatos.

## 4. Los dos rerankers que probamos

| Reranker | Tamaño | Notas |
|---|---|---|
| `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` («mmarco») | pequeño (~118 M parámetros) | Multilingüe, entrenado con traducciones de MS MARCO. Rápido en CPU. |
| `BAAI/bge-reranker-v2-m3` («bge») | mediano (~568 M parámetros) | Multilingüe, más preciso; muy lento en CPU, razonable en GPU o servicio. |

Ambos son de pesos abiertos: se pueden ejecutar en servidores propios, sin enviar texto a terceros.

## 5. Qué significan las métricas

- **cita@k:** la fracción de preguntas para las que *el fragmento que contiene la cita literal de la respuesta* aparece entre los **k primeros** resultados.
  `cita@1` = acertó el primero; `cita@10` = estaba en los diez primeros. Es la métrica más exigente porque exige el fragmento exacto, no solo el documento.
- **doc@k:** lo mismo pero basta con que aparezca *algún* fragmento del documento correcto.
- **MRR (Mean Reciprocal Rank):** promedio de `1 / posición` del primer acierto. Si el acierto está en el lugar 1 vale 1; en el 2, 0,5; en el 4, 0,25. Premia que lo correcto esté arriba, que es lo que más importa porque el generador lee primero los de arriba.
- **Variantes coloquiales:** la misma pregunta reescrita como la diría un cliente («¿cuánto me cobran por tener la tarjeta?»). Más difícil porque se parece menos al texto del documento.

Una nota importante: con **167 preguntas**, cada resultado tiene un margen de error de unos **±3 a 4 puntos**. Diferencias menores no son concluyentes.

## 6. Qué pasó en nuestras pruebas

### 6.1 Sin reranker → con reranker (preguntas originales, `dev`)

| Sistema | cita@1 | cita@10 | MRR |
|---|---|---|---|
| BM25 (con contexto de metadatos) | — | 0,892 | 0,722 |
| Híbrido (BM25 + e5) con filtro de vigencia | 0,611 | 0,940 | 0,729 |
| + reranker mmarco (top-30) | 0,707 | 0,958 | 0,805 |
| + reranker bge (top-20) | 0,808 | 0,958 | 0,870 |

Lectura: el híbrido ya encuentra casi siempre el fragmento correcto *entre los diez primeros* (94 %), pero solo lo pone **primero** en el 61 % de los casos.
El reranker casi no cambia cuántas veces está entre los diez primeros (de 0,940 a 0,958), pero **lo sube de lugar**: el acierto en primer lugar pasa de 0,61 a 0,81 con bge.
Eso es exactamente su función: ordenar mejor lo que ya se encontró. Por eso el MRR sube de 0,73 a 0,87.

### 6.2 Una sola corrida en `test` (88 preguntas, informativa)
El mismo orden de sistemas se repitió en el conjunto de prueba, que no se usó para decidir: híbrido con vigencia cita@10 0,909; con mmarco 0,966 (MRR 0,778); con bge 0,943 (cita@1 0,761, MRR 0,843).
Con tan pocas preguntas el margen es de ±4-5 puntos, así que confirma la tendencia pero no los decimales.

### 6.3 Por qué con reranker los embeddings caros dejaron de importar
Comparamos varios modelos de embeddings (ver `EMBEDDINGS.md`). **Sin reranker**, los de Voyage ganaban claramente a e5 (por ejemplo, `voyage-context-4` ponía el acierto primero en 0,689 contra 0,611).
**Con reranker bge**, los tres quedaron casi iguales:

| Embeddings | cita@1 | cita@10 | MRR | variantes coloquiales: cita@10 | variantes: MRR |
|---|---|---|---|---|---|
| e5-small (local, gratis) | 0,808 | 0,958 | 0,870 | 0,857 | 0,642 |
| voyage-4-large | 0,802 | 0,964 | 0,870 | 0,911 | 0,664 |
| voyage-context-4 | 0,808 | 0,970 | 0,876 | 0,905 | 0,649 |

Explicación sencilla: los embeddings de más calidad mejoran el *orden* de la lista de candidatos. Pero el reranker vuelve a ordenar esa lista desde cero con un criterio mejor, así que el orden inicial importa menos.
Lo que sí sigue importando es que el fragmento correcto **esté dentro de los 20 candidatos**; ahí los modelos buenos ayudan poco porque BM25 + e5 ya lo logran en ~94-97 % de los casos.

### 6.4 ¿Con o sin contexto de metadatos?
A cada fragmento le anteponemos, solo para indexar, una línea con título, tipo de documento, área, segmento y estado de vigencia
(«Tarifas Productos y Servicios 2026 | tarifas tasas | personas | …»). Esto ayuda a todos los sistemas, incluso con reranker:
sin contexto, mmarco bajaba de cita@10 0,958 a 0,934 y de MRR 0,805 a 0,758.

## 7. Cuánto cuesta en tiempo

Medido en este equipo, **sin GPU** (12 núcleos de CPU):
- mmarco (pequeño): del orden de 2-3 segundos por pregunta con 30 candidatos. Aceptable para pruebas.
- bge (mediano): ~15-17 segundos por pregunta con 20 candidatos (la evaluación de ~335 consultas tardó unos 93 minutos). **No sirve para atender clientes en CPU.**
- En una GPU de servidor o con un servicio de reranking, bge baja a décimas de segundo por consulta. Por eso la recomendación es: **bge con GPU o servicio; mmarco como alternativa de CPU**.

Esto sale de las pruebas; la latencia real en producción depende del servidor que elija el banco.

## 8. Qué NO resuelve un reranker

1. **No responde cuándo no debe.** Para preguntas cuya respuesta no está en el corpus, la puntuación del reranker sirve como señal, pero un umbral solo no basta: medimos un AUROC de 0,83 (1,0 sería perfecto, 0,5 azar).
   Para tener solo 10 % de rechazos injustificados, deja pasar casi la mitad de lo que no está en el corpus. Se necesita un **verificador de suficiencia** en la fase 3b (por ejemplo, que el LLM juzgue si los fragmentos bastan para responder).
2. **No arregla un corpus malo.** Si un documento está desactualizado, mal clasificado o contradice otro, el reranker puede ponerlo primero. De ahí la importancia de las etiquetas de vigencia y de la regla «el PDF oficial manda».
3. **No sustituye la validación humana.** Nuestro golden set es sintético (generado con ayuda de IA y verificado contra el texto) y se parece al texto fuente, lo que favorece a BM25 y puede subestimar las diferencias entre modelos. Hace falta contrastar con consultas reales de usuarios.
4. **Solo reordena lo que recibe.** Si el fragmento correcto no está entre los 20 candidatos, el reranker no puede traerlo.

## 9. Cómo encaja en la decisión de producción (resumen)

- Para la recuperación en producción con **PostgreSQL + pgvector**: guardar los vectores (1.024 dimensiones en Voyage, 384 en e5), mantener BM25 (por ejemplo con búsqueda de texto de PostgreSQL), fusionar con RRF, filtrar por vigencia y aplicar el reranker a los 20 mejores.
- **No hay evidencia en `dev` de que los embeddings de pago superen a e5 cuando se usa el reranker** (con preguntas coloquiales, Voyage mejora ~5 puntos en cita@10, en el límite del margen de error, y nada en MRR).
- El reranker bge necesita GPU o un servicio; sin eso, mmarco con ~2-3 s por consulta, aceptando algo menos de precisión en el primer lugar (0,71 contra 0,81).

## 10. Glosario rápido

| Término | Significado |
|---|---|
| Fragmento (chunk) | Trozo de documento de hasta 1.500 caracteres; unidad que se indexa y se recupera. |
| Embedding | Vector de números que representa el significado de un texto. |
| Bi-encoder | Modelo que codifica pregunta y texto por separado (embeddings). Rápido. |
| Cross-encoder | Modelo que lee pregunta y texto juntos y da un puntaje. Preciso y lento (el reranker). |
| Top-k | Los k primeros resultados de una lista ordenada. |
| BM25 | Algoritmo clásico de búsqueda por palabras clave. |
| RRF | Forma de fusionar varias listas ordenadas sumando `1/(60+posición)`. |
| Golden set | Conjunto de preguntas con respuesta y fuente conocidas, para medir el sistema. |
| `dev` / `test` | Partes del golden set: `dev` para decidir y ajustar; `test` guardado para una sola comprobación final. |
| AUROC | Medida de qué tan bien una señal separa dos grupos (1,0 perfecto, 0,5 azar). |

## 11. Dónde ver los datos
- `rag-bocc/evaluacion/fase3a/README.md` y `configuracion-elegida.json`: configuración elegida y experimentos de la fase 3a.
- `rag-bocc/evaluacion/fase3a/embeddings-reranker-dev.json`: resultados con reranker por modelo de embeddings.
- `docs/EMBEDDINGS.md`: comparación de modelos de embeddings.
- Guía v2, secciones 3.5 y 3.6.
