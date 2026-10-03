"""Verificador de suficiencia (fase 3b, paso 5 del contrato): ¿los fragmentos recuperados contienen la respuesta? Decide `responder` o `abstenerse`.
Dos verificadores intercambiables, que se pueden combinar:

  por_rerank   Puntaje del reranker (Voyage rerank-3) del mejor fragmento. Sin LLM, ~0 costo adicional (el puntaje sale de la misma llamada de reranking).
               Umbral calibrado en `dev` (pipeline/24_suficiencia.py → rag-bocc/evaluacion/fase3b/suficiencia-dev.json).
  por_llm      Un LLM juzga si los fragmentos bastan para responder la pregunta. Proveedores: DeepSeek u OpenAI (cualquier API compatible con OpenAI).

Claves (solo del entorno, nunca en el código; ver .env.example):
  DEEPSEEK_API_KEY   DEEPSEEK_MODEL (por defecto deepseek-chat)   DEEPSEEK_BASE_URL (por defecto https://api.deepseek.com)
  OPENAI_API_KEY     OPENAI_MODEL_JUEZ (obligatoria si se usa OpenAI: nombre del modelo de chat elegido)
En producción el texto de la pregunta debe pasar ANTES por la capa de enmascaramiento de datos personales (docs/CONTRATO-3B.md, paso 2).
"""
import json, os, re

PROMPT = """Eres un verificador de suficiencia para un asistente de un banco colombiano. Recibes una PREGUNTA de un cliente y unos FRAGMENTOS de documentos oficiales.
Decide si los fragmentos contienen la información necesaria para responder la pregunta SIN inventar nada.
- "suficiente": true solo si la respuesta (o su parte esencial) está dicha en los fragmentos.
- Si los fragmentos tratan el tema pero no contienen el dato pedido, "suficiente": false.
- Si la pregunta no es sobre productos o servicios del banco, "suficiente": false.
Responde SOLO con JSON: {"suficiente": true|false, "motivo": "una frase"}

PREGUNTA: %s

FRAGMENTOS:
%s"""

PROVEEDORES = {
    'deepseek': dict(clave='DEEPSEEK_API_KEY', modelo=('DEEPSEEK_MODEL', 'deepseek-chat'), url=('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')),
    'openai': dict(clave='OPENAI_API_KEY', modelo=('OPENAI_MODEL_JUEZ', None), url=None),
}


def por_rerank(puntajes, umbral):
    """puntajes: puntajes del reranker de los fragmentos de la consulta (cualquier orden). True = hay evidencia suficiente."""
    return bool(puntajes) and max(puntajes) >= umbral


def cliente(proveedor):
    """Devuelve (cliente OpenAI-compatible, modelo). Falla con un mensaje claro si falta la clave o el modelo."""
    cfg = PROVEEDORES[proveedor]
    clave = os.environ.get(cfg['clave'])
    if not clave: raise RuntimeError(f"Falta {cfg['clave']} en el entorno (poner en .env y cargar con: set -a; . ./.env; set +a)")
    nom, defecto = cfg['modelo']; modelo = os.environ.get(nom, defecto)
    if not modelo: raise RuntimeError(f'Falta {nom} en el entorno (nombre del modelo de chat a usar)')
    import openai
    kw = dict(api_key=clave, max_retries=3, timeout=60)
    if cfg['url']: kw['base_url'] = os.environ.get(cfg['url'][0], cfg['url'][1])
    return openai.OpenAI(**kw), modelo


def por_llm(pregunta, textos, proveedor='deepseek', _cl=None):
    """textos: fragmentos (los 3-5 mejores tras el reranker). Devuelve (suficiente: bool, motivo: str). Ante una respuesta ilegible: (False, 'respuesta ilegible')
    (conservador: ante la duda el asistente se abstiene)."""
    cl, modelo = _cl or cliente(proveedor)
    frag = '\n\n'.join(f'[{i}] {t[:1500]}' for i, t in enumerate(textos, 1))
    r = cl.chat.completions.create(model=modelo, temperature=0, messages=[{'role': 'user', 'content': PROMPT % (pregunta, frag)}])
    txt = r.choices[0].message.content or ''
    m = re.search(r'\{.*\}', txt, re.S)
    try:
        d = json.loads(m.group(0)); return bool(d['suficiente']), str(d.get('motivo', ''))
    except Exception:
        return False, 'respuesta ilegible'
