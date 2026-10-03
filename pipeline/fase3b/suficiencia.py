"""Verificador de suficiencia (fase 3b, paso 5 del contrato): ¿los fragmentos recuperados contienen la respuesta? Decide `responder` o `abstenerse`.
Dos verificadores intercambiables, que se pueden combinar:

  por_rerank   Puntaje del reranker (Voyage rerank-3) del mejor fragmento. Sin LLM, ~0 costo adicional (el puntaje sale de la misma llamada de reranking).
               Umbral calibrado en `dev` (pipeline/24_suficiencia.py → rag-bocc/evaluacion/fase3b/suficiencia-dev.json).
  por_llm      Un LLM juzga si los fragmentos bastan para responder la pregunta. Proveedores: DeepSeek u OpenAI (cualquier API compatible con OpenAI).

Claves (solo del entorno, nunca en el código; ver .env.example):
  DEEPSEEK_API_KEY   DEEPSEEK_MODEL (por defecto deepseek-flash; también deepseek-v4-pro)   DEEPSEEK_BASE_URL (por defecto https://api.deepseek.com)
  En DeepSeek el modo de razonamiento («thinking») viene ACTIVADO por defecto y se apaga SIEMPRE aquí con extra_body={"thinking": {"type": "disabled"}}
  (documentación oficial: api-docs.deepseek.com/guides/thinking_mode). Con razonamiento activo el modelo ignora `temperature` y es más lento y caro.
  OPENAI_API_KEY     OPENAI_MODEL_JUEZ (obligatoria si se usa OpenAI: nombre del modelo de chat elegido)
En producción el texto de la pregunta debe pasar ANTES por la capa de enmascaramiento de datos personales (docs/CONTRATO-3B.md, paso 2).
"""
import collections, json, os, re

USO = collections.Counter()      # tokens consumidos por el juez en este proceso

_P1 = """Eres un verificador de suficiencia para un asistente de un banco colombiano. Recibes una PREGUNTA de un cliente y unos FRAGMENTOS de documentos oficiales.
Decide si los fragmentos contienen la información necesaria para responder la pregunta SIN inventar nada.
- "suficiente": true solo si la respuesta (o su parte esencial) está dicha en los fragmentos.
- Si los fragmentos tratan el tema pero no contienen el dato pedido, "suficiente": false.
- Si la pregunta no es sobre productos o servicios del banco, "suficiente": false.
Responde SOLO con JSON: {"suficiente": true|false, "motivo": "una frase"}

PREGUNTA: %s

FRAGMENTOS:
%s"""

_P2 = """Eres un verificador de suficiencia para un asistente de un banco colombiano. Recibes una PREGUNTA de un cliente y unos FRAGMENTOS de documentos oficiales.
Decide si los fragmentos contienen la información necesaria para responder la pregunta SIN inventar nada.
- "suficiente": true solo si la respuesta (o su parte esencial) está dicha en los fragmentos.
- Si la pregunta parte de una premisa equivocada (p. ej. pregunta por qué algo cuesta mucho y los fragmentos dicen que no se cobra), los fragmentos que permiten CORREGIR la premisa cuentan como suficientes: "suficiente": true.
- Si los fragmentos tratan el tema pero no contienen el dato pedido, "suficiente": false.
- Si la pregunta no es sobre productos o servicios del banco, "suficiente": false.
Responde SOLO con JSON: {"suficiente": true|false, "motivo": "una frase"}

PREGUNTA: %s

FRAGMENTOS:
%s"""

PROMPTS = {'p1': _P1, 'p2': _P2}
PROMPT_DEFECTO = 'p2'      # p1 = versión inicial (rechazaba las preguntas de premisa falsa); ver docs/CONTRATO-3B.md

PROVEEDORES = {
    'deepseek': dict(clave='DEEPSEEK_API_KEY', modelo=('DEEPSEEK_MODEL', 'deepseek-flash'), url=('DEEPSEEK_BASE_URL', 'https://api.deepseek.com')),
    'openai': dict(clave='OPENAI_API_KEY', modelo=('OPENAI_MODEL_JUEZ', None), url=None),
}


def por_rerank(puntajes, umbral):
    """puntajes: puntajes del reranker de los fragmentos de la consulta (cualquier orden). True = hay evidencia suficiente."""
    return bool(puntajes) and max(puntajes) >= umbral


def cliente(proveedor, modelo=None):
    """Devuelve (cliente OpenAI-compatible, modelo). `modelo` sustituye al de la variable de entorno. Falla con un mensaje claro si falta la clave o el modelo."""
    cfg = PROVEEDORES[proveedor]
    clave = os.environ.get(cfg['clave'])
    if not clave: raise RuntimeError(f"Falta {cfg['clave']} en el entorno (poner en .env y cargar con: set -a; . ./.env; set +a)")
    nom, defecto = cfg['modelo']; modelo = modelo or os.environ.get(nom, defecto)
    if not modelo: raise RuntimeError(f'Falta {nom} en el entorno (nombre del modelo de chat a usar)')
    import openai
    kw = dict(api_key=clave, max_retries=3, timeout=60)
    if cfg['url']: kw['base_url'] = os.environ.get(cfg['url'][0], cfg['url'][1])
    return openai.OpenAI(**kw), modelo


def por_llm(pregunta, textos, proveedor='deepseek', _cl=None, prompt=PROMPT_DEFECTO):  # _cl = (cliente, modelo), para pruebas o para elegir modelo
    """textos: fragmentos (los 3-5 mejores tras el reranker). Devuelve (suficiente: bool, motivo: str). Ante una respuesta ilegible: (False, 'respuesta ilegible')
    (conservador: ante la duda el asistente se abstiene)."""
    cl, modelo = _cl or cliente(proveedor)
    frag = '\n\n'.join(f'[{i}] {t[:1500]}' for i, t in enumerate(textos, 1))
    kw = dict(extra_body={'thinking': {'type': 'disabled'}}) if proveedor == 'deepseek' else dict(temperature=0)
    r = cl.chat.completions.create(model=modelo, messages=[{'role': 'user', 'content': PROMPTS[prompt] % (pregunta, frag)}], **kw)
    if USO is not None and getattr(r, 'usage', None): USO['tokens'] += r.usage.total_tokens
    if proveedor == 'deepseek' and getattr(r.choices[0].message, 'reasoning_content', None): raise RuntimeError('DeepSeek devolvió razonamiento: el modo thinking no quedó desactivado')
    txt = r.choices[0].message.content or ''
    m = re.search(r'\{.*\}', txt, re.S)
    try:
        d = json.loads(m.group(0)); return bool(d['suficiente']), str(d.get('motivo', ''))
    except Exception:
        return False, 'respuesta ilegible'
