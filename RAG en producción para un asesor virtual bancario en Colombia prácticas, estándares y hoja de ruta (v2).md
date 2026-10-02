# RAG en producción para un asesor virtual bancario en Colombia: prácticas, estándares y hoja de ruta (v2)

_Versión 2 · 2026-10-01 · complementa (no reemplaza) la guía `(2024-2026).md`. Esta versión parte de **datos medidos sobre el corpus real** (`rag-bocc/`, 308 URLs) y de la lectura de los libros de `…/AI Engineering applied/2024-2026/recomendados`._

## 0. Respuestas directas a tus preguntas

**1. ¿El corpus cubre todo lo que hay en la web, o debo revisar paso a paso desde el id 1?**
**La primera versión del corpus no cubría todo, y no necesitas revisarlo a mano id por id.** (Tras el rastreo del lote 2 —secciones 1.0 y 1.5— el corpus pasó de 308 a **1.175 documentos**; la brecha principal se cerró y quedan los huecos de la sección 1.2 que no son documentos, como el buscador de oficinas.) Medí la brecha: dentro de las 163 páginas HTML ya descargadas hay **763 enlaces internos adicionales** a `bancodeoccidente.com.co` que no están en las 308 URLs (704 documentos: ~200 PDF y ~504 enlaces `documents/d/guest/…`; más 59 páginas/variantes). Casi todo lo que pediste que falta está ahí: reportes financieros y de accionistas de 2010-2026, informes de sostenibilidad por año, políticas 2022-2025, y buena parte del segmento **empresas** (solo hay 2 URLs `/web/empresas/…` en las 308; el mapa del sitio lista además páginas como «Banco de las Empresas», «Bienes para la venta», «Colombianos en el Exterior», «Usa tu crédito», «Pensiones voluntarias», «Préstamo personal dinámico», «Club de mascotas», «Empleado para la vida», «Talento joven»… para las que no encontré título equivalente en el corpus). Lo que sí está bien cubierto: productos de personas (tarjetas, créditos, cuentas, seguros, inversión CDT), tarifas/tasas 2026 en PDF, FAQs de la página de ayuda, legal y políticas, educación financiera (blog `/b/…`) y los reportes de gestión 2025.
En vez de revisar a mano: (a) **cerrar la brecha con un rastreo guiado** (sección 1.3) y (b) pasar una **auditoría automática por documento + muestreo estratificado de ~10 %** (sección 1.4). El detalle de lo pendiente quedó en `rag-bocc/enlaces-pendientes.txt|json`.

**2. ¿Cuáles son las mejores prácticas para el «set de evaluación» (pares pregunta-respuesta-fuente por documento)?**
Generar por documento es un buen punto de partida, pero **tres matices cambian el resultado** (sección 2): (i) el golden set oficial se arma **por unidad de conocimiento, no por archivo** (hay 9 duplicados exactos y 183 documentos de licitaciones que no deberían pesar igual que las tarifas); (ii) cada par lleva una **cita textual verificable** (documento, página y fragmento literal) para poder auditar automáticamente que la respuesta está soportada; (iii) se trabaja en **niveles** (sintético masivo → filtrado → validado por expertos) con **separación desarrollo/prueba por documento** para no sobreajustar (lo advierte con fuerza *Architecting Generative AI Applications*, cap. 2).

**3. ¿Cómo se manejan hoy los documentos con gráficos o imágenes? ¿Modelo multimodal para chunks o embeddings?**
La práctica actual es **híbrida, no «todo multimodal»** (sección 3): texto y tablas nativos primero; un VLM **solo donde hay información que existe únicamente como imagen**; y un **índice visual por página (ColPali/ColQwen)** como complemento, no como índice único. En tu corpus medí dónde importa: 35 de 79 PDF tienen imágenes grandes, pero solo un puñado concentra información visual relevante (informe de gestión 2025: 361 páginas y 674 imágenes grandes; guías de uso de tarjetas; instructivos paso a paso con casi nada de texto). No hace falta aplicar VLM a todo.

---

## 1. Auditoría de cobertura del corpus actual

### 1.0 Actualización: rastreo ejecutado (lote 2, 2026-10-01)

Con el alcance que definiste (**personas + empresas + inversionistas, solo 2022-2026, sin licitaciones**) hice el rastreo guiado de la sección 1.3. Resultado **medido**:

| Concepto | Lote 1 (inicial) | Lote 2 (rastreo) | Notas |
|---|---|---|---|
| Páginas web | 163 con texto | **+176 páginas nuevas en español** (115 de **empresas**, 61 de personas/otros) | Se rastrearon 402 páginas únicas; se descartaron las versiones `/en/` duplicadas y las rutas antiguas `/wps/…` |
| Secciones de empresas halladas | 2 URLs | moneda extranjera (19), seguros (15), tarjetas empresariales (11), créditos (9), pagos (9), leasing (8), canales digitales (7), recaudos (7), segmentos (5), cuentas, inversiones empresariales, factoring (4 c/u), Bre-B, impuestos, pagos masivos, líneas verdes… | Era el mayor hueco |
| Páginas de personas antes ausentes | — | «Colombianos en el exterior», «Bienes para la venta», «Proyectos de vivienda», «Duplica tu saldo», «Pensiones voluntarias», «Préstamo personal dinámico», «Club de mascotas», «Banco de las Empresas», «Trabaja con nosotros / Nuestros beneficios / Talento joven», seguros de libranza (4), LATAM Pass Platinum/Signature, Mastercard Joven, etc. | — |
| Documentos (PDF/Word/Excel) | 123 | **801 seleccionados → 776 descargados** (320 inversionistas, 240 otros, 135 empresas, 81 sostenibilidad); 25 no descargados | Filtrados por alcance 2022-2026; los **183 de licitaciones se excluyeron** y se descartó lo anterior a 2022 |
| Documentos únicos descubiertos en total | — | 1.279 (incluye lo ya cubierto y lo excluido) | |

**Qué no se descargó, y por qué:** 1 archivo de 136 MB (`tarifario-de-transporte`, empresas), 2 enlaces con 404, 1 con 401, los enlaces de `webavc.…` (otro dominio, duplicados de formatos ya presentes), 4 paquetes `.zip` de informes de asamblea 2022-2025, certificados de RUT/Cámara de Comercio para proveedores y copias numeradas de los mismos formularios `.xlsm/.xlsx`. La lista exacta queda en `rag-bocc/omitidos-lote2.json` al terminar la extracción.

**Lo que trae el lote 2 y antes no había:** estados financieros separados y consolidados trimestrales y anuales 2022-2026 (español e inglés), informes periódicos de fin de ejercicio, información relevante, calificaciones (Fitch, BRC/S&P), actas y presentaciones de asamblea, reglamentos de junta y comités, estatutos, código de buen gobierno, informes de sostenibilidad y políticas 2022-2025, **estudios económicos para empresas** (Pulso económico, Radar, Radiografías regionales, TES sectoriales), **calendarios tributarios** y manuales de actualización tributaria, **~80 instructivos de canales empresariales** (portal, app, PSE, tokens, pagos, leasing, fiducia), guías de leasing, contratos y formatos para empresas, y T&C de campañas.

**Implicaciones nuevas:**
- Hay **muchos documentos en inglés duplicados** de los de español (estados financieros, políticas). Conviene marcarlos con `idioma` y excluirlos del índice por defecto para el asesor en español.
- Los **instructivos de empresas** (~80) son PDF de capturas con poco texto: se convierten en el principal caso de uso del VLM/OCR de la sección 3.
- Los **estados financieros** (cientos de páginas cada uno) hacen crítico el parsing de tablas (sección 3 y mini-benchmark).
- Los **estudios económicos** son contenido de opinión con fecha: deben etiquetarse `tipo=analisis_economico` y con vigencia corta, sin mezclarlos con tarifas ni condiciones de producto.
- **Sigue sin cubrirse:** el buscador de oficinas/cajeros, la banca en línea autenticada y los cotizadores JS (deben ser herramientas), y las normas oficiales completas (SFC, Senado).

_(Conteos finales tras la extracción en la sección 1.5.)_


### 1.1 Qué tenemos (medido)

| Concepto | Dato |
|---|---|
| URLs procesadas | 308 → 294 con texto (9 duplicados exactos) y 14 sin contenido |
| Formatos | 171 páginas web, 109 PDF (2 por OCR), 10 Excel, 5 Word, 1 imagen |
| PDF | 79 propios del sitio, 1.983 páginas en total |
| PDF con ≥1 imagen grande | 35 de 79 |
| Sin contenido (14) | redes sociales, bolsas de empleo, cotizadores y portales de pago JS, línea ética (plantilla vacía) |

### 1.2 Qué falta (medido sobre los enlaces internos de las páginas ya descargadas)

| Grupo | Enlaces | Valor para el asesor | Prioridad |
|---|---|---|---|
| **A. Información a inversionistas / accionistas** (`/quienes-somos/informacion-inversionistas`) | **418** (2010-2026; ~92 de 2022-2025 y 13 de 2026 por nombre de archivo; 173 sin año en el nombre) | Estados financieros trimestrales/semestrales/anuales, informes de fin de ejercicio, convocatorias a asamblea, información relevante, calificaciones, reglamentos | **Alta** para 2022-2026; media/baja para 2010-2021 |
| **B. Sostenibilidad** | 41 | Informes de gestión y sostenibilidad por año, GRI, TCFD, balances de valor social 2010-2019, políticas | Alta (2021-2025), media (histórico) |
| **C. Otros documentos** | 72 | Autorizaciones, guías de uso, formatos, políticas | Alta |
| **D. Licitación banca-seguros** | 183 | Procesos de contratación de seguros (pliegos, adendas, actas). Útil solo si el asesor atenderá a proveedores | **Baja** (excluir del índice principal) |
| **E. Páginas nuevas** | 49 | Varias son variantes con `utm_` o rutas antiguas (`/wps/portal/…`); reales: `/web/empresas/creditos`, `/web/empresas/cuentas`, `/web/empresas/leasing`, `/web/empresas/inversiones-empresariales`, `/web/empresas/canales-digitales/aval-pay`, `latam-pass-platinum/signature`, `mastercard-joven`, `/compra-cartera`, `/seguros/vida`, `/seguros/productos`, `/seguros/mascotas-perros-gatos`, `contactenos.bancodeoccidente.com.co`, `BuscadordePuntosOccidente` (cajeros/oficinas) | Alta |

Notas importantes:
- **Segmento empresas:** es el mayor hueco temático. El sitio lo sirve bajo `/web/empresas/…` y se descubre navegando desde la home de empresas, que no está entre las 308 URLs. Hay que partir de esa home y del menú, no solo de los enlaces que ya conocemos.
- **Horarios, oficinas y cajeros:** el contenido está en un buscador dinámico (`BuscadordePuntosOccidente`); no es texto estático. Solo hay un «horario de atención» suelto en la página de corresponsales. Para el asesor virtual esto debe ser una **herramienta/API**, no un documento.
- **Cultura, historia, valores:** historia está en «Nuestro Banco» (con década por década); «cultura» y beneficios laborales viven en las páginas de «Trabaja con nosotros», «Empleado para la vida», «Talento joven», que faltan.
- **Decretos y normas:** hay normas ya capturadas (Ley 2157 y 266 de habeas data, Decreto 587/2016, circular básica jurídica…) pero no un repositorio sistemático; considera obtener las normas desde las fuentes oficiales (SFC, Secretaría del Senado, Función Pública) y no solo las copias que el banco enlaza.

### 1.3 Cómo cerrar la brecha (rastreo guiado, repetible)

1. **Semillas:** home de personas, home de empresas, mapa del sitio, páginas de inversionistas, sostenibilidad, transparencia y legal/políticas.
2. **Rastreo en dos niveles** (los enlaces de las páginas semilla + los de esas páginas), restringido a `bancodeoccidente.com.co` y `portalpublico.…`, deduplicando por ruta sin `utm_`.
3. **Detectar PDF por tipo de contenido (no por extensión):** muchos enlaces `documents/d/guest/<slug>` no tienen extensión.
4. **Registrar para cada URL:** `estado_http`, `content_type`, `hash`, `fecha_descarga`, `aparece_en` (páginas que la enlazan; sirve como contexto y como señal de autoridad).
5. **Reglas de exclusión explícitas** (licitaciones, redes sociales, bolsas de empleo, páginas `utm_`), documentadas en un archivo para que el rastreo sea reproducible.
6. **Frecuencia:** semanal para páginas, diaria para tarifas/tasas (cuando existan fuentes estructuradas), y re-rastreo completo trimestral para detectar páginas nuevas o retiradas.
7. **Aviso técnico:** el sitio bloquea `curl` y Chrome headless con 403 de CloudFront; lo obtuve con el navegador de Playwright. Para un pipeline productivo conviene pedir al equipo web del banco un **export oficial** (CMS Liferay) o una lista blanca de la IP, en vez de depender de scraping.

### 1.4 Auditoría de calidad sin revisar a mano cada documento

Un script que corra sobre `corpus.jsonl` y marque, por documento:
- **Cobertura de texto:** caracteres por página (PDF) o por URL (web). Alerta si < 300 caracteres/página (probable escaneado o imagen).
- **Densidad de imágenes:** imágenes grandes por página (candidato a VLM, sección 3).
- **Tablas rotas:** líneas con columnas desalineadas, celdas vacías repetidas, números sin encabezado.
- **Idioma y codificación:** detectar mojibake (`Ã³`, `�`) y mezclas es/en (hay informes en inglés duplicando los de español).
- **Duplicados y casi-duplicados:** hash exacto (ya hecho) y MinHash/coseno para versiones casi iguales (guías de uso por tarjeta comparten texto legal).
- **Vigencia:** extraer fechas del texto (año en el nombre, «vigente desde», «2026») y marcar los documentos sin fecha.
- **Boilerplate:** menús/pies que se hayan colado en el texto.

Con ese reporte, la **revisión manual se limita a** (a) los marcados, y (b) una muestra estratificada de **~10 % (≈30 documentos)** por tipo (página, PDF de producto, tarifas, reporte financiero, legal) con una lista de verificación: ¿el texto coincide con el original?, ¿las tablas conservan filas/columnas?, ¿faltan secciones (acordeones, pestañas)?, ¿hay cifras en imágenes?

### 1.5 Corpus final tras el lote 2 (medido, 2026-10-01)

| Concepto | Dato |
|---|---|
| Documentos en `rag-bocc/` | **1.175** (308 del lote 1 + **867** del lote 2: 690 documentos y 177 páginas) |
| Con texto propio | **1.041**; 119 son duplicados exactos de otro (el contenido no se repite) y 15 sin texto |
| Tipos en el lote 2 | PDF 623 · páginas web 177 · PDF por OCR 26 · Excel 25 · Word 11 · imagen por OCR 5 (34 documentos en total pasaron por OCR) |
| Por etiqueta principal | PERSONAS 604 · INVERSIONISTAS 253 · EMPRESAS 249 · SOSTENIBILIDAD 69 |
| Volumen de texto | ≈ 65,4 millones de caracteres (≈ 16 millones de tokens estimados a 4 caracteres/token). Los dos informes de gestión 2025 pesan ≈ 2,6 millones de caracteres cada uno |
| Posibles documentos en inglés | ~54 en el lote 2 (heurística) → marcar `idioma` |
| Omitidos del lote 2 | **86**: 77 fuera de alcance (el contenido indica un año ≤ 2021), 4 enlaces que devolvieron HTML/404, 2 exclusiones deliberadas (una lista de NIT y nombres con posibles datos personales y el listado masivo de corresponsales, que debe ser una herramienta), 3 por formato no soportado (`.doc` antiguo, `.xlsb`) o archivo dañado. Lista exacta en `rag-bocc/omitidos-lote2.json` |

Esquema del lote 2: igual al del lote 1 más el campo `lote` (`crawl2-paginas` / `crawl2-documentos`). Las etiquetas del lote 2 se asignaron por **reglas sobre la ruta y el nombre** (no vienen de tu JSON de etiquetas); por eso **conviene revisarlas** antes de usarlas como filtros.

**Defectos conocidos del lote 2 (atendidos en parte en la sección 1.6):**
- **Etiquetado grueso:** 235 documentos quedaron en `PERSONAS > documentos y formatos` y 82 en `INVERSIONISTAS > otros`; falta un clasificador (reglas + LLM) por tipo y producto.
- **Títulos pobres:** 212 documentos tenían como título un identificador (UUID); los reemplacé por la primera línea legible del texto o por «Documento N». Lo ideal es tomar el título de los metadatos del PDF o del enlace que lo describe.
- **Extracción no auditada:** los 867 documentos pasaron por el pipeline pero **no** por la revisión de la sección 1.4 (muestreo y alertas). Los estados financieros de ≈ 700.000 caracteres necesitan validar tablas; los instructivos leídos por OCR, validar nombres de botones y pantallas.
- **Cobertura 2022-2026 de inversionistas:** el filtro de alcance usó el año del nombre o los primeros 6.000 caracteres del texto; puede haber errores en ambos sentidos.
- **Versiones y vigencia:** los estados financieros trimestrales de años distintos conviven sin `vigente_desde/hasta` ni `reemplaza_a`; es el insumo para la gobernanza de vigencia (sección 4).

### 1.6 Resultado de la Fase 1 (auditoría automática y etiquetado, 2026-10-01)

Ejecuté la auditoría de la sección 1.4 sobre los 1.175 documentos y reorganicé el corpus. **Entregables** en `rag-bocc/`: `documentos/<segmento>/<área>/` (árbol nuevo), metadatos enriquecidos en cada `.md`, `corpus.jsonl` e `indice.json`, y `auditoria/` (`reporte.md`, `auditoria.csv`, `casi-duplicados.csv`, `muestra-revision.md`). Respaldo del estado previo en `_raw/corpus.pre-fase1.jsonl`.

| Resultado | Dato |
|---|---|
| Segmentos | personas 670 · inversionistas 254 · empresas 251 |
| Tipo documental (`tipo_doc`) | 23 tipos; 56 en `otro` (12 son redes/cotizadores sin contenido) |
| Área de producto (`area`) | 24 áreas; 52 en `otros` (antes 224 en el catch-all de la primera pasada) |
| **Indexables por defecto** | **958 de 1.175** (excluidos: 119 duplicados exactos, 73 en inglés, 17 sin contenido útil y 12 casi-duplicados ≥ 0,95) |
| Casi-duplicados (Jaccard ≥ 0,8) | 37 pares/documentos; varios con similitud 1,0 que el hash exacto no detectaba (mismo estado financiero publicado en dos URL) |
| Vigencia | vigente 689 · histórico 241 · **por verificar 227** · periodo reciente 15 · **vencido 3** |
| Candidatos a VLM / OCR reforzado | **154** PDF (≥ 3 imágenes grandes y poco texto): sobre todo instructivos de canales (62) y brochures de seguros (14) |
| Con tablas numéricas (parser de layout) | 48 PDF (estados financieros) + 19 páginas con tablas Markdown |
| Otras alertas | 45 sin fecha detectable · 44 con < 300 caracteres/página · 34 por OCR · 23 con título dudoso · 6 con caracteres rotos · 5 muy largos (> 1,5 M caracteres) |

**Hallazgo clave de vigencia:** el PDF «tasas personas» vigente dice *«Vigencia del 01 al 30 de septiembre de 2026»*: **al día de la extracción (1-oct-2026) ya estaba vencido**, y los otros dos de tasas hallados cubren diciembre de 2025 y mayo de 2025. Las tasas se publican **por mes**, así que un índice documental las vuelve obsoletas cada 30 días; confirma la decisión de la sección 4 (tasas y tarifas por herramienta/API, el PDF solo para explicar).

**Títulos:** corregí 19 títulos de página que no correspondían a su contenido (por ejemplo «Información para Accionistas» sobre la página de «Paquete mínimo de servicios»), usando el primer encabezado del texto y conservando `titulo_original`; algunos nuevos títulos son genéricos (p. ej. «Auto Liviano») y quedan marcados `titulo_dudoso` para revisión.

**Lo que Fase 1 NO hizo (pendiente, requiere personas o datos del banco):**
1. **Revisión humana** de la muestra de 142 documentos (`auditoria/muestra-revision.md`, con lista de verificación A-F). Sin ella, las etiquetas y la calidad de extracción no están validadas.
2. **Vigencia real:** `vigente_desde/hasta`, `reemplaza_a` y la jerarquía de autoridad necesitan al dueño de cada documento; hoy son heurísticas sobre nombres y textos.
3. **Idioma:** la marca `ingles` es heurística; falta enlazar cada documento en inglés con su equivalente en español.
4. **Tablas de los estados financieros** y **OCR de instructivos:** detectados, no validados.
5. **Normas oficiales** (SFC, Senado) y buscador de oficinas/cajeros: fuera del sitio o dinámicos.

---

## 2. Set de evaluación (golden set): mejores prácticas

### 2.1 Qué dicen los libros y qué tomé

| Fuente | Idea aplicable |
|---|---|
| **Huang, *RAG from First Principles* (2026), cap. 9** | Construir **con el cliente** el set de evaluación a partir de las preguntas más comunes y de los documentos más usados; el set contiene **pregunta, respuesta estándar, documento fuente y página**; **~200 pares** bastan para las primeras pruebas y se amplía con el proyecto. Separa evaluación del *retrieval* (precisión, recall, MRR, MAP, P@K, precisión por documento/página) y de la *respuesta* (relevancia, fidelidad). El **RAG Triad** (relevancia del contexto, fidelidad, relevancia de la respuesta) sirve como evaluación **sin referencia**, pero el propio autor advierte que no sustituye la confirmación del negocio. |
| **Bourne, *Unlocking Data with Generative AI and RAG* (2025), cap. 9** | Cuatro vías para obtener *ground truth*: anotación humana, **conocimiento experto (incluida la generación basada en plantillas que los expertos «hidratan»)**, *crowdsourcing* y **sintético** (LLM o recuperación). Evaluar **mientras se construye y después del despliegue**: los datos se desactualizan y las preguntas de los usuarios cambian; mantener un bucle de retroalimentación. Ragas para generar y puntuar. |
| **Kimothi, *A Simple Guide to RAG* (2025), cap. 5** | Tres puntajes de calidad (relevancia del contexto, fidelidad, relevancia de la respuesta) y cuatro capacidades (robustez al ruido, **rechazo negativo**, integración de información, robustez contrafactual). Limitaciones: no hay métricas estándar; **no sobre-confiar en LLM-as-judge**; usar un **juez distinto del generador**; los benchmarks son estáticos → usar uno propio del dominio y datos que se actualicen. |
| **Architecting Generative AI Applications (2026), cap. 2** | Evitar el **sobreajuste al set de evaluación**: si iteras prompts hasta que pasen las mismas 20-30 preguntas, filtras ese set al prompt. Separar **entrenamiento/validación/prueba**; los ejemplos *few-shot* se tratan como entrenamiento y se excluyen de la validación; dividir **por entidad** (en el ejemplo, por usuario) para que nada se «cuele». En juez-LLM: **2-3 rúbricas** que importen, no muchas; puntual (pointwise), por pares o con respuesta de referencia. |
| **Building Reliable AI Systems (2026), cap. 9** | Los jueces alucinan y tienen sesgos (respuestas largas, estilo propio, errores sutiles): **votación entre varios jueces, validación humana de una muestra aleatoria y verificación contra bases estructuradas**. Red teaming con humanos para hallar fallos que las métricas no ven. |

La guía v1 (sección 3) ya fija métricas, herramientas y el uso de RAGAS/RAGChecker/Hamel Husain (critique shadowing). **No lo repito**; abajo va lo operativo.

### 2.2 Cómo adaptar «pares pregunta-respuesta-fuente por documento»

**Por documento sí, pero con presupuesto y niveles:**

| Nivel | Qué es | Cantidad orientativa (criterio propio) | Uso |
|---|---|---|---|
| **Bronce** | Pares sintéticos generados por fragmento, sin validar | 1 por cada ~2.000 caracteres útiles, máximo 10 por documento | Pruebas de humo del *retrieval* (¿el fragmento correcto aparece en el top-k?) y regresión barata |
| **Plata** | Bronce filtrado automáticamente (reglas + LLM) y con muestra revisada | ~1.500-3.000 | Ajuste de chunking, embeddings, reranker |
| **Oro** | Validado por expertos del banco, con tipos de pregunta cubiertos | **300-600** (arranque ~200 según Huang) | **Decide el paso a producción**; nunca se usa para ajustar prompts |

**Reglas para cada par** (esquema `golden.jsonl`):
```json
{
  "id": "G-000123",
  "nivel": "oro",
  "pregunta": "¿Qué cuota de manejo tiene la tarjeta Mastercard Black?",
  "variantes": ["cuanto cobran de manejo la black", "cuota manejo tc black"],
  "tipo": "factual | multi_salto | comparativa | temporal | numerica_tabla | ambigua | sin_respuesta | premisa_falsa | fuera_alcance | datos_personales | adversarial | regulatoria",
  "segmento": "personas | empresas | inversionistas",
  "producto": "tarjetas/mastercard-black",
  "respuesta_referencia": "…",
  "debe_abstenerse": false,
  "fuentes": [{"doc_id": "108", "url": "…", "pagina": 7, "cita_literal": "…fragmento exacto…"}],
  "fecha_referencia": "2026-10-01",
  "split": "dev | test",
  "origen": "sintetico | experto | log_real",
  "validado_por": "experto_tarjetas",
  "notas": ""
}
```
- **`cita_literal` obligatoria:** permite comprobar por código (búsqueda de la cadena en el documento) que la respuesta de referencia está soportada y detectar cuándo un cambio del sitio invalida el par.
- **`fecha_referencia` + `split`:** los pares se versionan igual que los documentos.
- **Tipos de pregunta:** usar la taxonomía de la v1 (sección 2) y cuota por tipo: 10-15 % sin respuesta, 5-10 % adversariales, 10 % temporales (necesitan los documentos 2022-2025 de inversionistas/políticas; hoy no están).

### 2.3 Flujo de generación (reproducible)

1. **Unidad de generación = «bloque de conocimiento»** (sección/tabla/página del documento, no el archivo entero) con su contexto (título, jerarquía). Excluir duplicados y los grupos de baja prioridad.
2. **Generación sintética** con un LLM *distinto del que responderá* en producción: varias preguntas por bloque, de tipos distintos, **con respuesta + cita literal**. Complementar con RAGAS (grafo de conocimiento) para preguntas multi-salto entre documentos.
3. **Perturbaciones controladas:** ortografía, jerga («plata», «la tarjeta», «me clavaron un cobro»), preguntas incompletas, mezcla español/inglés.
4. **Preguntas sin respuesta ancladas al corpus:** productos inexistentes, fechas futuras, condiciones que el banco no publica.
5. **Filtros automáticos** (descartar):
   - La cita literal no aparece en el documento.
   - Un LLM la responde **sin contexto** (conocimiento previo, no mide RAG).
   - Una «multi-salto» que un solo fragmento ya responde (ver porcentaje de «falsas multi-salto» en la v1).
   - Duplicadas semánticamente (similitud > umbral).
6. **Validación experta:** un experto por dominio (tarjetas, crédito, cuentas, inversión, cumplimiento) corrige **pregunta, respuesta y fuente**, con **etiqueta binaria + crítica escrita** (aprobada/rechazada y por qué), como en la v1.
7. **Partición:** dividir **por documento/familia de producto** (no por pregunta). Por ejemplo 70 % desarrollo / 30 % prueba, de modo que los documentos de la prueba no hayan inspirado ningún ejemplo *few-shot*, regla de reescritura de consultas ni diccionario de siglas. Congelar `test` y reportarlo solo en los hitos.
8. **Mezclar con consultas reales** (call center, PQRS, chat) anonimizadas apenas existan; el sintético es un arranque, no un sustituto.
9. **Canarios:** 20-30 pares «imposibles de fallar» (horarios, línea de servicio, definiciones) que bloquean el despliegue si fallan.

### 2.4 Qué medir y con qué umbrales (propuestas propias, a calibrar)

| Capa | Métrica | Punto de partida sugerido |
|---|---|---|
| Retrieval | recall@10 de la **fuente correcta** (documento y fragmento) | ≥ 90 % en oro; informar por producto/tipo |
| Retrieval | MRR y nDCG@10 | seguimiento de tendencia; sin umbral duro al inicio |
| Retrieval | precisión por página/documento (Huang) | para ver ruido que llega al LLM |
| Generación | fidelidad (afirmaciones soportadas por el contexto) | ≥ 95 % en oro |
| Generación | **exactitud de cifras y fechas** (comparación por código) | 100 % en tarifas/tasas del oro; si falla, el sistema debe abstenerse |
| Abstención | tasa de **respuesta indebida** (debía abstenerse y no lo hizo) | ≈ 0 % en preguntas sobre tasas, tarifas y condiciones |
| Abstención | tasa de **rechazo falso** | ≤ 10 % (ajustable) |
| Citación | la fuente citada soporta la afirmación y está vigente | ≥ 95 % |
| Seguridad | pruebas adversariales (inyección, PII, fuera de alcance) | 0 fugas en el conjunto de red team |

Todo con **juez binario por modo de fallo**, calibrado contra etiquetas humanas (precisión y recall del juez), con **un juez distinto del generador** y **votación entre dos jueces** para el oro (Kimothi + *Building Reliable AI Systems*). Las aserciones por código (cifras, citas literales, formato) van antes que cualquier juez.

### 2.5 Evaluación continua
- Cada cambio de prompt, chunking, embeddings, reranker o modelo corre `dev` en CI; `test` solo en hitos.
- Cuando cambia un documento, se **regeneran/invalidan** los pares cuya `cita_literal` ya no aparece.
- En producción: muestreo de trazas, 👍/👎 con motivo, reformulaciones y escalamientos como señales; agrupar temas nuevos semanalmente para ampliar el oro (Bourne: evaluar también después del despliegue).

---

## 3. Documentos con gráficos e imágenes: estado actual y decisión

### 3.1 Panorama (qué se hace hoy)

| Enfoque | Qué dicen los libros | Evidencia / matiz |
|---|---|---|
| **Convertir a texto con un modelo multimodal** y usar RAG de texto | Kimothi (cap. 8.2) lo presenta como una de las tres opciones; advierte **pérdida de información** al pasar imagen→texto. Variante de **dos puntas**: el texto/resumen se embebe para buscar, pero **para generar se recupera el archivo original (la imagen) y se le pasa al LLM multimodal**; requiere un almacén de documentos con mapeo resumen→original | Compatible con BM25, auditable; el costo se concentra en la ingesta |
| **Embeddings multimodales compartidos** (CLIP-like) | Kimothi: sirven para imágenes generales, pero **fallan en el detalle fino de gráficos, tablas como imagen e infografías** | La v1 ya citaba que los CLIP-like rinden mal en documentos |
| **Embeddings por modalidad** | Imagen–texto (CLIP) y audio–texto (CLAP) en espacios separados | Poco útil para páginas de reportes |
| **Parsing con LLM multimodal** | Huang (cap. 1) clasifica el parsing de PDF en reglas, aprendizaje profundo y **LLM multimodal**; sugiere pasar el PDF directo a un modelo multimodal cuando hay diseños complejos, gráficos o ilustraciones; el ejemplo del libro convierte **cada página/diapositiva en una descripción estructurada** (título, cuerpo, contenido de imagen) y la guarda como documento | Costo por página; riesgo de descripciones inexactas |
| **Interacción tardía sobre imágenes de página (ColPali/ColQwen)** | — (no es tema central de los cuatro libros) | Resultados 2026 mixtos: reseñas de práctica reportan ventaja sobre pipelines OCR en gráficos/tablas, pero un trabajo reciente sobre recuperación científica concluye que **representar documentos solo como imagen se queda corto** ([arXiv 2604.18508](https://arxiv.org/pdf/2604.18508)); un estudio previo ([arXiv 2505.05666](https://arxiv.org/pdf/2505.05666)) comparó visión vs OCR. Almacenamiento alto: miles de vectores por página (el recorte de vectores, p. ej. DocPruner, intenta reducirlo). **Hacer prueba propia.** |
| **Embeddings multimodales comerciales** | — | En 2026 hay opciones gestionadas (Cohere Embed v4, Jina v4, Voyage, Gemini Embedding), citadas en blogs comparativos de calidad variable; elegir solo tras medir en tu golden set |

Fuentes web usadas (de calidad desigual; tratarlas como pistas, no como prueba): [Lost in OCR Translation?](https://arxiv.org/pdf/2505.05666), [REAL-MM-RAG](https://arxiv.org/pdf/2502.12342), [Document-as-Image… Fall Short](https://arxiv.org/pdf/2604.18508), [guía de embeddings multimodales (Spheron)](https://www.spheron.network/blog/multimodal-embedding-models-gpu-cloud-siglip2-jinaclip-cohere/).

### 3.2 Qué hay realmente en este corpus (medido)

| Tipo de documento | Ejemplos (id en `rag-bocc`) | Riesgo |
|---|---|---|
| **Reporte de gestión con muchos gráficos** | 055 (informe de gestión 2025, 361 p., 674 imágenes grandes), 307 y 298 (capítulos), 297 | Tendencias y cifras en gráficos; texto de apoyo suele repetirlas |
| **Guías de uso de tarjetas/cuentas** | 108, 110, 112, 118, 120, 242 (≈20 págs. con 100-340 imágenes grandes) | Beneficios y pasos con iconografía; el texto extraído parece completo pero puede omitir iconos/etiquetas |
| **Instructivos paso a paso con capturas** | 039, 040 (6-8 págs., ~1.500 caracteres en total) | **Casi sin texto**: el valor está en las capturas |
| **Brochures de segmento** | 031, 036 | Marketing con cifras en imágenes |
| **PDF escaneados / presentaciones con poco texto** | 074 y 192 (OCR aplicado); 032 y 033 (6 y 8 págs., ~1.300-1.500 caracteres, tipo presentación) | Errores de OCR en cifras; contenido en imagen |
| **Páginas web** | banners, tablas como imagen | Hoy solo se conserva el `alt` de las imágenes; no sabemos cuántas cifras viven en imagen |
| **Tablas** | tarifas, tasas, estados financieros (299: 168 págs.) | El problema principal es **tabla bien extraída**, no gráfico |

### 3.3 Decisión recomendada (por capas, de menos a más costo)

**Capa 0 — base (todo el corpus):** texto nativo + tablas bien serializadas (Markdown/HTML). Mini-benchmark de parsing con 30-50 páginas difíciles (v1, sección 4).
**Capa 1 — VLM selectivo en ingesta (solo candidatos):**
- Selección automática por reglas: páginas PDF con **imágenes grandes y poco texto**, o con figuras tipo gráfico; páginas web con imágenes que parezcan banners informativos (comparar con una captura de la página renderizada).
- Para cada figura: un modelo de visión produce una **descripción estructurada** (tipo de gráfico, título, ejes, unidades, periodo, **valores legibles**, conclusión y *nivel de confianza*) → se guarda como fragmento `tipo=descripcion_figura` con `pagina`, `bbox` e imagen original referenciada.
- **Regla de oro:** si la misma cifra existe en una tabla o en el texto, **la tabla manda**; la descripción del gráfico no puede contradecirla (comprobación por código). Las descripciones se marcan como «derivadas» y se citan con cautela.
- Instructivos con capturas (039, 040, y los que aparezcan): transcribir **pasos + nombres de pantallas/botones** en texto; el asesor responde en texto y puede adjuntar la imagen original.
**Capa 2 — generación multimodal:** al recuperar un fragmento de figura, pasar al modelo generador **la imagen de la página** además del texto (patrón de «dos puntas» de Kimothi). Útil para preguntas como «¿cómo evolucionó X según el gráfico?».
**Capa 3 — índice visual por página (ColQwen/ColPali) — opcional:** solo para reportes a accionistas y brochures si el *golden set* muestra preguntas visuales que el texto + VLM no resuelve. Es un **índice complementario** fusionado con RRF, no un reemplazo (coincide con la v1).

**Qué NO hacer:** embeber imágenes sueltas con un CLIP genérico como índice principal; aplicar VLM a todas las páginas; usar descripciones de gráficos como fuente de cifras oficiales sin tabla de respaldo.

### 3.4 Cómo medirlo (antes de gastar)
- Añadir al golden set un bloque de **preguntas visuales** (≥ 40): gráficos del informe de gestión, pasos de instructivos, cifras en brochures, tablas como imagen.
- Comparar **A** (texto+tablas) vs **B** (+VLM selectivo) vs **C** (+índice visual) en recall@k y fidelidad **solo en ese bloque** y reportar costo por página y latencia. Decidir con datos.
- Chunking de imágenes: Kimothi indica que a las imágenes **normalmente no se les hace chunking**; la unidad es la figura (con su pie y su página), no un recorte.

---

## 4. Arquitectura y decisiones de diseño (cambios sobre la v1)

La arquitectura de la v1 se mantiene. Estos son los **ajustes y precisiones**, con su fuente:

| # | Decisión | Fundamento |
|---|---|---|
| 1 | **Corpus por niveles de autoridad y vigencia**: política/tarifa/producto/FAQ/informe/legal/histórico, con `vigente_desde`, `estado`, `reemplaza_a` (esquema de la v1, sección 1). El frontmatter actual del corpus ya trae `id, url, titulo, tipo_contenido, etiquetas, fecha_extraccion`; **faltan** `vigente_desde/hasta`, `estado`, `segmento`, `clasificacion_acceso` y `hash` | v1; Bourne: los datos se desactualizan |
| 2 | **Tasas, tarifas, horarios, TRM y puntos de atención por herramienta/API**, no por vectores. Los PDF de tarifas se indexan para **explicar** y citar, no como fuente de verdad numérica | v1; Kimothi 7.2 (alucinación persistente → validación posterior y recomendación vs acción) |
| 3 | **Caché semántico solo para la «cabeza» de la cola larga**: en los logs típicos, una pequeña fracción de consultas concentra gran parte del tráfico (Bourne cap. 15 habla de 20 % de consultas → ~80 % de cobertura y ahorros de latencia/costo de 10-100×; son cifras del autor, a validar). Para un banco: respuestas **curadas y aprobadas** a FAQs estables (horarios fijos, definiciones, cómo activar la tarjeta), con invalidación al cambiar la fuente; **nunca** para tasas, saldos o respuestas personalizadas | Bourne cap. 15; v1 |
| 4 | **Chunking**: estructural y jerárquico, con tamaño y solapamiento **elegidos por evaluación** (no hay regla universal: Kimothi 3.2.4, 6.3.1). Contextual retrieval para anteponer título/producto/fecha a cada fragmento (Anthropic, citado por Huang cap. 10 y por la v1) | Kimothi; Huang; v1 |
| 5 | **Ruteo por dominio** (productos personas / empresas / inversionistas / legal / FAQ / herramientas de tasas) con índices separados | v1; Kimothi 7.1 (orquestación) |
| 6 | **Seguridad**: contenido recuperado = no confiable (inyección indirecta), RBAC en el retrieval, PII enmascarada en entradas y trazas, *red team* continuo con humanos y automatizado (Bourne cap. 5; *Building Reliable AI Systems* 9.1.5; OWASP LLM 2025 en la v1) | Varios |
| 7 | **Humano en el circuito**: el asesor virtual **recomienda/informa**, no ejecuta transacciones; escalamiento al SAC o a un asesor | Kimothi 7.2; v1 (Ley 1328) |
| 8 | **Empezar clásico, evolucionar a agéntico acotado** (herramientas de solo lectura: tasas, simulador, buscador de oficinas) | Huang cap. 10; v1 |

**Elección de modelos (decidir con el golden set, no por moda):** al menos dos embeddings multilingües (uno abierto, uno comercial), un reranker multilingüe, un generador y un juez distintos entre sí. Verificar residencia de datos y cláusulas de proveedor según CE 005/2019 y CE 007/2018 (v1, sección 5).

---

## 5. Ruta clara (ordenada por dependencias)

**Fase 0 — Decisiones y gobierno (semana 1)**
- Alcance: ¿solo personas o también empresas e inversionistas? ¿histórico 2010-2021 sí/no? ¿se incluyen licitaciones? (recomendado: **no**).
- Acuerdo con el banco sobre fuente oficial (export CMS o acceso al sitio) y propietarios por dominio (producto, cumplimiento, relaciones con inversionistas).
- Esquema de metadatos de vigencia (v1) y jerarquía de autoridad.
- Estudio de impacto de privacidad y evaluación del proveedor de LLM/nube en marcha (v1).
_Salida:_ documento de alcance de 1-2 páginas + dueños asignados.

**Fase 1 — Cerrar la brecha del corpus (semanas 1-3) — _ejecutada el 2026-10-01 en su parte automática (rastreo, extracción, auditoría, etiquetado heurístico); pendiente la revisión humana de la muestra y la vigencia validada por los dueños_**
- Rastreo guiado (sección 1.3): primero **inversionistas 2022-2026**, **sostenibilidad 2021-2025**, **empresas** y las 49 páginas nuevas; luego histórico si se aprueba.
- Reextraer con el mismo pipeline (páginas renderizadas con JS incluidas) y regenerar `rag-bocc/`.
- Auditoría automática y muestreo del 10 % (sección 1.4).
_Salida:_ inventario con estado/vigencia por documento; lista de huecos restantes; corpus ≥ 95 % de las URLs relevantes con texto verificado.

**Fase 2 — Golden set v0 (semanas 2-4, en paralelo)**
- Generar **bronce** (sección 2.3) y filtrar a **plata**; armar la partición `dev/test` por documento.
- Expertos validan **oro v1 (~200 → 300-600)** con binario + crítica. Incluir ≥ 40 preguntas visuales y las temporales.
- Montar Langfuse/Phoenix + RAGAS/DeepEval en CI con **canarios**.
_Salida:_ `golden.jsonl` versionado, métricas definidas y tablero base.

**Fase 3 — Línea base y parsing (semanas 4-6)**
- Mini-benchmark de parsing (30-50 páginas: tarifas, estados financieros, instructivos con capturas, escaneados) y elección de herramienta.
- RAG base: chunking estructural + híbrido (BM25+denso) + reranker + filtro de vigencia + citas obligatorias + abstención.
- Medir en `dev` por segmento y tipo; fijar umbrales de la sección 2.4.
_Salida:_ informe de línea base con fallos clasificados (retrieval vs generación).

**Fase 4 — Mejora dirigida por errores (semanas 6-10)**
- Contextual retrieval, ruteo por dominio, herramientas de tasas/tarifas/horarios, verificación de cifras.
- **Capas 1-2 multimodales** (sección 3.3) solo en los documentos candidatos; evaluar A/B/C en el bloque visual.
- Calibrar jueces vs humanos; red team de inyección y datos personales.
_Salida:_ cumplir los umbrales en `dev`; primera corrida en `test`.

**Fase 5 — Piloto controlado (semanas 11+)**
- Asesores internos como usuarios; luego un grupo limitado de clientes. Feedback, escalamientos, drift semanal, regeneración del golden set ante cada cambio de tarifa/política. Caché semántico para la cabeza de la cola larga.

**Riesgos principales**
| Riesgo | Mitigación |
|---|---|
| Brecha de cobertura (empresas, histórico) | Fase 1 con rastreo guiado y export oficial |
| Citar tarifas o normas obsoletas | Metadatos de vigencia + herramienta de tasas + intención temporal |
| Sobreajuste al set de evaluación | Partición por documento, `test` congelado, oro separado |
| Cifras erróneas desde gráficos/OCR | «La tabla manda», verificación por código, abstención |
| Dependencia del scraping (403 de CloudFront) | Export oficial/lista blanca del banco |
| Costo del VLM/índice visual | Aplicación selectiva y A/B con medición previa |

---

## 6. Mapa de lectura: qué libro y dónde

| Tema | Libro y capítulos leídos |
|---|---|
| Fundamentos y RAGOps (capas críticas/esenciales/de mejora, mejores prácticas de producción) | Kimothi, *A Simple Guide to RAG*: caps. 2, 6, 7 (7.1-7.2) |
| Chunking y optimización de índice | Kimothi 3.2.4, 6.3.1; Huang cap. 2 |
| **Evaluación y golden set** | Huang cap. 9; Bourne cap. 9; Kimothi cap. 5; *Architecting GenAI Applications* cap. 2; *Building Reliable AI Systems* cap. 9 |
| **Multimodal** | Kimothi 8.2; Huang cap. 1 (PDF) y cap. 10 (RAG multimodal) |
| Seguridad y red team | Bourne cap. 5; *Building Reliable AI Systems* 9.1.5; *AI-Native LLM Security* (consulta puntual) |
| Caché semántico y memoria | Bourne caps. 15-19 |
| RAG agéntico / modular / contextual | Huang cap. 10; Rothman 2026 (cap. 8, realimentación humana y evaluador con expertos); Bourne caps. 12-14 |

_Nota:_ no leí cada libro de punta a punta; leí los capítulos arriba indicados y busqué por términos en el resto. Las **citas y cifras de papers 2025-2026 de la v1 no las volví a verificar** en esta versión; las nuevas fuentes web que agrego arriba son de calidad desigual y las marco como tales.

---

## 7. Anexos

### 7.1 Prompt base para generar pares (bronce)
```
Eres un experto en productos del Banco de Occidente. A partir del FRAGMENTO, genera hasta {k} preguntas
que un cliente real haría y que SOLO puedan responderse con este fragmento.
Para cada pregunta devuelve JSON: {pregunta, tipo, respuesta, cita_literal}.
Reglas: (1) la cita_literal debe aparecer EXACTAMENTE en el fragmento; (2) no uses conocimiento externo;
(3) varía el tipo (factual, numerica_tabla, comparativa, condicion/requisito); (4) escribe como cliente
(sin citar el documento); (5) si el fragmento no contiene información útil, devuelve [].
Metadatos del fragmento: título={titulo}, producto={producto}, fecha={fecha}.
FRAGMENTO:
{texto}
```
Después: filtros automáticos (cita literal presente, sin respuesta sin contexto, no duplicada) y muestra para revisión experta.

### 7.2 Rúbricas del juez (binarias)
1. **Fidelidad:** ¿cada afirmación está soportada por el contexto recuperado? (sí/no + afirmaciones sin soporte)
2. **Vigencia y citación:** ¿cita una fuente vigente que respalda la afirmación? (sí/no)
3. **Abstención correcta:** si no había evidencia suficiente, ¿se abstuvo y ofreció escalar? (sí/no)
Más aserciones por código: cifras exactas, fecha de vigencia, presencia de cita, ausencia de PII.

### 7.3 Archivos generados en esta etapa
- `rag-bocc/` (corpus de 1.175 documentos, 958 indexables, con metadatos y `auditoria/`), `rag-bocc/enlaces-pendientes.txt|json` (los 763 enlaces del primer análisis; en su mayoría ya cubiertos por el lote 2) y `rag-bocc/omitidos-lote2.json` (86 omitidos con motivo).
- Este documento (v2).
