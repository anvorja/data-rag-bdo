# API del panel de pruebas

Backend para la prueba con usuario real desde un dashboard web. El frontend (React + TypeScript + Tailwind + shadcn/ui) va aparte y consume esta API.
El turno del asistente es el de `pipeline/fase3b/asistente.py` y sigue las reglas de `docs/CONTRATO-3B.md`.

## Arranque
```bash
source .venv/bin/activate                     # el python del .venv: el uvicorn del sistema no ve sentence-transformers
pip install -r requirements-ml.txt -r requirements-api.txt
set -a; . ./.env; set +a                      # VOYAGE_API_KEY y DEEPSEEK_API_KEY (u OPENAI_API_KEY)
python -m uvicorn api.app:app --port 8000     # documentación interactiva: http://localhost:8000/docs
python -m api.test_api                        # pruebas sin proveedores pagos (también corren en la CI)
```
La primera consulta tarda unos 15–20 s porque carga e5-small, BM25 y spaCy. Después, un turno tarda alrededor de 1,5 s.

| Variable | Por defecto | Para qué |
|---|---|---|
| `LLM_PROVEEDOR` | `deepseek` | `deepseek` (medido) u `openai` (armado, sin medir) |
| `LLM_MODELO` | `deepseek-flash` | modelo que redacta y juzga (con OpenAI es obligatorio, o `OPENAI_MODEL_JUEZ`) |
| `PROMPT_JUEZ` | `p1` | prompt del juez de suficiencia (`p2` acepta mejor las preguntas con premisa falsa) |
| `CORS_ORIGENES` | `http://localhost:5173` | orígenes del frontend, separados por coma (Vite usa el 5173) |
| `REGISTRO_PRUEBAS` | `_raw/pruebas` | dónde se escribe el registro de la prueba (no versionado) |

## Endpoints
| Método y ruta | Uso en el panel |
|---|---|
| `GET /api/salud` | Indicador de estado: corpus, recuperador cargado, LLM listo, variables que faltan (nunca valores) |
| `POST /api/sesiones` | Abre un chat. Devuelve `aviso_inicio` (asistente virtual, no persona) y `texto_consentimiento`. Se muestran **una vez** al inicio |
| `POST /api/sesiones/{id}/consentimiento` `{acepta}` | Sin `acepta: true`, el chat y la búsqueda responden 403 |
| `POST /api/chat` `{sesion_id, mensaje}` | Turno: `accion` (`responder`/`abstenerse`/`escalar`/`aclarar`), `respuesta`, `citas[]` (URL, título, página, fragmento, vigencia, aviso), `avisos[]`, `traza` (vía, puntaje, segundos, tipos de datos enmascarados) y `turno_id` |
| `POST /api/buscar` `{sesion_id, consulta, k}` | Solo recuperación (sin LLM): los fragmentos más relevantes con su puntaje y su vigencia. Sirve para explorar las fuentes |
| `GET /api/documentos?q=&segmento=&area=&estado=&tipo=&incluir_historicos=&desde=&limite=` | Catálogo de documentos (búsqueda por título, sin costo). Por defecto oculta las versiones históricas |
| `GET /api/documentos/filtros` | Valores de los filtros, con conteos |
| `GET /api/documentos/{id}` | Visor: metadatos, `texto` en Markdown (los PDF llevan `<!-- página N -->`), `aviso` y `versiones[]` |
| `GET /api/documentos/{id}/fragmentos/{n}` | El fragmento citado (`fragmento` = `"<id>#<n>"`), para resaltarlo dentro del documento |
| `POST /api/valoraciones` `{sesion_id, turno_id, util, correcta, comentario}` | Valoración del usuario de prueba sobre cada respuesta |

Los tipos de TypeScript se generan del contrato con `npx openapi-typescript http://localhost:8000/openapi.json -o src/api/tipos.ts`.

Errores que el panel debe mostrar:
| Código | Causa |
|---|---|
| 503 | LLM sin saldo (402), clave rechazada o límite del proveedor (429). El mensaje va en `detail` |
| 502 | Otro fallo del proveedor |
| 500 | Falta una dependencia en el servidor |
| 429 / 422 | Búsqueda rechazada por los límites anti-abuso |
| 404 | Sesión, documento o fragmento inexistente |

En el chat, los límites no devuelven error: responden `accion: "abstenerse"` con `traza.via = "limites"`.

## Reglas que garantiza la API
- Todo texto del usuario pasa por los límites anti-abuso (600 caracteres, 10 por minuto, 60 por sesión) y por el enmascaramiento **antes** de llegar a Voyage o al LLM.
- El registro de la prueba (`turnos.jsonl`, `busquedas.jsonl`, `valoraciones.jsonl`, `sesiones.jsonl`, `errores.jsonl`) guarda **solo texto enmascarado**, nunca el mensaje original.
- Solo se sirven documentos indexables: el doc 806, con datos personales, no aparece.
- Las URL, títulos y avisos de vigencia los pone el código desde el corpus; el modelo nunca los escribe.

## Límites para la prueba
- Las sesiones, los contadores y la lista de turnos viven **en memoria**: se pierden al reiniciar y valen para un solo proceso. Antes de abrir la prueba a más usuarios hay que llevarlos a PostgreSQL o Redis.
- Atiende un turno a la vez (candado): basta para un usuario de prueba, no para carga.
- Sin autenticación: se sirve en local o detrás de una red de confianza; no se expone a internet tal como está.
- El enlace a cada fuente es la URL pública del banco. Los PDF originales no se sirven desde aquí: viven en `_raw/`, que no está versionado.
