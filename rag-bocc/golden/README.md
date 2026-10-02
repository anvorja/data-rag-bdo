# Golden set v0 — Banco de Occidente (asesor virtual)

**290 pares pregunta-respuesta-fuente**, generados el 2026-10-01 sobre el corpus indexable (958 documentos). Nivel **plata**: verificados automáticamente (la cita literal existe en el documento fuente), **no validados por expertos**. No hay pares de nivel **oro** todavía.

## Archivos

| Archivo | Contenido |
|---|---|
| `golden-v0.jsonl` | Los pares (un JSON por línea). Esquema abajo |
| `test.sha256` | Hash del `split=test`: **congelado**. CI falla si cambia; los cambios van en `golden-v1` |
| `docs-test.json` | Documentos asignados a la partición de prueba |
| `fuentes/qa_*.jsonl`, `fuentes/bloques.json` | Entradas de generación (pares con clave corta + bloques de texto muestreados) |
| `rechazados.jsonl` | Pares descartados por los filtros automáticos (vacío en v0) |
| `baseline-bm25.json` | Línea base léxica (prueba de cordura) |
| `revision-experta.md` | 144 pares para que los expertos los promuevan a oro |

## Esquema de cada par

`id` (estable: hash de la pregunta) · `nivel` · `pregunta` · `variantes` (reformulaciones coloquiales) · `tipo` · `segmento` · `producto` · `respuesta_referencia` · `accion_esperada` (responder | aclarar | abstenerse | escalar | corregir_premisa) · `debe_abstenerse` · `fuentes[{doc_id, url, titulo, pagina, cita_literal}]` · `fecha_referencia` (2026-10-01) · `vigencia_nota` · `dificultad` · `origen` (sintetico_claude) · `validado_por` (null) · `tipos_doc` · `split` (dev | test) · `notas`

## Composición

| tipo | n |
|---|---|
| factual | 136 |
| numerica_tabla | 62 |
| temporal | 27 |
| sin_respuesta | 15 |
| regulatoria | 13 |
| adversarial | 8 |
| premisa_falsa | 6 |
| ambigua | 6 |
| comparativa | 5 |
| fuera_alcance | 4 |
| multi_salto | 4 |
| datos_personales | 4 |

| segmento | n |
|---|---|
| personas | 210 |
| empresas | 55 |
| inversionistas | 15 |
| transversal | 10 |

Partición: dev 197 · test 93 (por **documento**: 43 de 137 documentos fuente son de prueba; una pregunta es `test` si alguna de sus fuentes lo es). Acciones: responder 246, abstenerse 28, corregir_premisa 7, aclarar 6, escalar 3.

## Cómo se generó

1. **Bloques:** 242 bloques de conocimiento muestreados de forma estratificada por (segmento, tipo_doc) sobre los documentos indexables (`pipeline/06_golden_bloques.py`).
2. **Redacción:** preguntas, variantes coloquiales, respuesta de referencia y **cita literal** escritas por Claude leyendo cada bloque (no hay otro LLM disponible en este entorno), incluidas preguntas sin respuesta, con premisa falsa, ambiguas, fuera de alcance, de datos personales y adversariales.
3. **Filtros automáticos** (`pipeline/07_golden_ingerir.py`): la cita debe aparecer en el documento; sin preguntas casi duplicadas (Jaccard ≥ 0,8); en las preguntas sin respuesta, los términos «ausentes» no deben aparecer en el corpus (el filtro rechazó 3 intentos iniciales).
4. **Partición** por documento, estratificada por (segmento, tipo_doc).

## Línea base BM25 (prueba de cordura, no el RAG final)

| consulta | recall doc@10 | recall cita@10 | MRR cita |
|---|---|---|---|
| pregunta original (n=255) | 0.933 | 0.847 | 0.661 |
| variante coloquial (n=256) | 0.812 | 0.656 | 0.45 |
| dev (n=167) | 0.934 | 0.838 | 0.675 |
| test (n=88) | 0.932 | 0.864 | 0.634 |

Lectura: el retrieval léxico encuentra la fuente en el top-10 para ~93 % de las preguntas originales, pero cae a ~81 % con reformulaciones coloquiales y es débil en **multi-salto** (cita@10 = 0,25) y **comparativas** (0,4). Esa brecha es el margen de mejora para el híbrido + reranker de la fase 3.

## Limitaciones (importante)

- **Sesgo léxico:** las preguntas se redactaron mirando el bloque fuente, por lo que se parecen al texto; el recall real con preguntas de clientes será menor. Mezclar con consultas reales (call center, PQRS) apenas existan.
- **Cobertura:** 137 de 958 documentos indexables (14 %). Poco cubiertos: estudios económicos (1/72), informes de gestión y sostenibilidad (0/33), contratos y formatos (2/55), información relevante a inversionistas (1/52). Inversionistas: 14 pares; empresas: 55; personas: 187.
- **Sin validar:** ningún par ha sido revisado por un experto del banco. Las respuestas de referencia pueden estar desactualizadas; las tasas y campañas caducan.
- **Pocas preguntas de abstención:** sin respuesta 15, adversariales 8, datos personales 4, fuera de alcance 4. La meta de la guía (10-15 % sin respuesta, 5-10 % adversarial) se cumple solo a medias: ampliar en v1.
- **Contradicciones reales del sitio** convertidas en pruebas (cajeros: 2.800 / 3.500 / 3.800; libre inversión: 1,35 % vs 1,30 % en la misma página; CDT: $1.000.000 vs $500.000) deben revisarse con los dueños de contenido.
- **Dependencia del corpus:** si se limpia o se re-extrae un documento, la cita puede dejar de aparecer: ejecutar `python pipeline/validate.py`.

## Cómo promover a oro

1. Un experto por dominio (tarjetas, crédito, cuentas, seguros, inversión, empresas, cumplimiento) revisa `revision-experta.md` con ✓/✗ y crítica.
2. Los aprobados pasan a `nivel: oro` con `validado_por` en un **golden-v1** (no se edita v0).
3. Con ≥ 300 pares oro (meta 300-600 de la guía), el oro decide el paso a producción; el plata sirve para desarrollo.
