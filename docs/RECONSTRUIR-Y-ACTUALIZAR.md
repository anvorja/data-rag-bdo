# Qué no está en git, cómo reconstruirlo y cómo se actualiza cada mes

Guía para quien herede el proyecto (ingeniero del RAG). Actualizado 2026-10-02.

## 1. Qué vive en git y qué no
| Elemento | ¿En git? | Si falta |
|---|---|---|
| `rag-bocc/documentos/**/*.md` (1.178 documentos con cabecera YAML) y `rag-bocc/indice.json` | **Sí** | Es la fuente de verdad versionada del corpus |
| `rag-bocc/corpus.jsonl` (68 MB; lo leen casi todos los scripts) | **No** (generado, ignorado) | **`python pipeline/20_reconstruir_corpus.py`** lo regenera desde los `.md` y `indice.json`, sin `_raw/` (verificado: idéntico al original, mismos fragmentos) |
| `rag-bocc/golden/`, `rag-bocc/vigencia/`, `rag-bocc/relaciones*`, `rag-bocc/evaluacion/` | **Sí** | — |
| `_raw/` (originales descargados, embeddings, recapturas) | **No** | Los originales solo se regeneran volviendo a rastrear el sitio (ver `pipeline/README.md`); los embeddings se recalculan (`embed.py`, `13_embeddings_api.py` o los cuadernos de Colab) |
| `.env` (claves de API) | **No** (nunca) | Crear desde `.env.example`; las claves están en la cuenta de Voyage/OpenAI de la empresa |

Un clon limpio funciona así: `git clone` → `python pipeline/20_reconstruir_corpus.py` → ya se pueden ejecutar los scripts de recuperación y evaluación. El CI ejecuta ese paso en cada PR para garantizar que sigue funcionando.
**Importante:** si cambias el corpus (por ejemplo `05_escribir_y_auditar.py`), los `.md` y `indice.json` quedan actualizados y se versionan; `corpus.jsonl` se regenera, no se sube.

## 2. Qué no se puede reconstruir desde el repositorio
- Las descripciones largas y las etiquetas crudas del rastreo (`descripcion`, `etiquetas` en bruto) solo vivían en `_raw/`. El resto de campos vuelve idéntico (la prueba compara los 1.178 documentos).
- Los PDF y páginas originales. Si hicieran falta (para reextraer con otro método, por ejemplo OCR o un modelo de visión), hay que volver a descargarlos con los scripts de `pipeline/crawl/` (en el navegador, porque el sitio responde 403 a curl). **Recomendación:** guardar `_raw/` en un almacenamiento del banco con un manifiesto de hashes.

## 3. Procedimiento mensual (tasas) y por evento (campañas, tarifas)
1. **Capturar los documentos vivos** desde una pestaña del navegador en bancodeoccidente.com.co (`fetch()` de `/documents/d/guest/<slug>`, ver el ejemplo de la recaptura del 2026-10-02) y guardarlos en `_raw/recaptura/<slug>.pdf`.
   Documentos vivos conocidos: `tarifas-persona-bdo`, `tarifas-empresariales-bdo`, `tasas-personas-bdo`, `tasas-empresariales-bdo`.
2. `python pipeline/17_recaptura.py --fecha AAAA-MM-DD`: si el contenido cambió, la versión anterior queda `historico` y se crea la nueva (`version_de`). Nunca se sobrescribe (exigencia de las directivas).
3. `python pipeline/05_escribir_y_auditar.py`: regenera `documentos/`, `indice.json`, `corpus.jsonl` y `auditoria/`; aplica `rag-bocc/vigencia/decisiones.jsonl`.
4. `python pipeline/validate.py` (0 errores) y `python pipeline/19_relaciones.py` (relaciones página → documentos).
5. Embeddings (solo lo que cambió): `python pipeline/fase3a/embed.py e5-small` y, si se usa Voyage, `python pipeline/13_embeddings_api.py --modelos <modelo> --ctx 1 0`. Cada mes son del orden de cientos de fragmentos.
6. Rama `feature/*` → commit → PR a `develop` (squash). Si el cambio es una versión del corpus, etiquetarla (`corpus-AAAA-MM-DD`).

Reglas de negocio de vigencia, estados y escalamiento: `docs/DECISIONES.md`. Estado del corpus y relaciones: `docs/CORPUS-METADATOS-Y-ENLACES.md`. Embeddings: `docs/EMBEDDINGS.md` (y el reranker, explicado en `docs/reranker-explicacion.md`).

## 4. Alertas que debe vigilar el ingeniero del RAG
- Tasas: el día 1 de cada mes debe cargarse el PDF nuevo; si no está, el asistente responde con la última tasa **indicando la fecha** (regla confirmada).
- Contradicciones entre una página y su PDF: **manda el PDF oficial**; hay que registrar la alerta.
- Campañas sin fecha de fin (`sujeta_a_existencias`): confirmar periódicamente con el responsable si siguen abiertas.
- Documentos con datos personales de terceros (p. ej. cédulas): se excluyen del índice (`motivo_no_indexar: contenido_sensible`) y se reportan.
