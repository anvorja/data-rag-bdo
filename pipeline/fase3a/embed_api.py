"""Embeddings por API (Voyage, OpenAI) para comparar modelos de la fase 3a. Las claves se leen SOLO del entorno
(VOYAGE_API_KEY, OPENAI_API_KEY; ver .env.example); nunca se imprimen ni se guardan.

Modelos: voyage-4-lite | voyage-4 | voyage-4-large | voyage-context-4 | openai-3-small | openai-3-large
Los vectores salen normalizados (producto punto = coseno). Dimensión por defecto: 1024 (Voyage) / nativa (OpenAI).
"""
import collections, json, os, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np

CHARS_POR_TOKEN = 2.0          # estimación conservadora (real ~2,3 en promedio; tablas numéricas pesan más); solo sirve para armar lotes
LIMITE = {'voyage-4-lite': 600_000, 'voyage-4': 250_000, 'voyage-4-large': 90_000, 'voyage-context-4': 90_000,
          'openai-3-small': 250_000, 'openai-3-large': 250_000}
MAX_TEXTOS = 128
CTX_DOC_MAX_TOK = 16_000       # un «documento» contextual: el límite del modelo es 32k tokens y no admite truncar
OPENAI = {'openai-3-small': 'text-embedding-3-small', 'openai-3-large': 'text-embedding-3-large'}
USO = collections.Counter()


def _est(t): return int(len(t) / CHARS_POR_TOKEN) + 1


def _lotes(textos, limite):
    lote, tok = [], 0
    for i, t in enumerate(textos):
        e = _est(t)
        if lote and (tok + e > limite or len(lote) >= MAX_TEXTOS):
            yield lote; lote, tok = [], 0
        lote.append(i); tok += e
    if lote: yield lote


def _reintentar(fn, intentos=12):
    for k in range(intentos):
        try: return fn()
        except Exception as ex:
            msg = str(ex).lower()
            if k == intentos - 1 or any(s in msg for s in ('invalid', 'authentication', 'api key', 'unauthorized')): raise
            time.sleep(min(60, 2 ** k) if '429' not in msg and 'rate' not in msg else 15)


def _norm(m):
    m = np.asarray(m, dtype='float32')
    return m / np.linalg.norm(m, axis=1, keepdims=True).clip(1e-9)


def _clientes():
    c = {}
    if os.environ.get('VOYAGE_API_KEY'):
        import voyageai; c['voyage'] = voyageai.Client(max_retries=3, timeout=120)
    if os.environ.get('OPENAI_API_KEY'):
        import openai; c['openai'] = openai.OpenAI(max_retries=3, timeout=120)
    return c


def _embed_simple(cl, modelo, textos, tipo, hilos=4):
    if modelo.startswith('openai'): hilos = 1      # la cuenta tiene un tope de 1M tokens/min: en serie y con espera
    """tipo: 'document' | 'query'."""
    out = [None] * len(textos)
    lotes = list(_lotes(textos, LIMITE[modelo]))

    def uno(idx):
        lote = [textos[i] for i in idx]
        if modelo.startswith('voyage'):
            r = _reintentar(lambda: cl['voyage'].embed(lote, model=modelo, input_type=tipo))
            USO[modelo] += r.total_tokens; return idx, r.embeddings
        r = _reintentar(lambda: cl['openai'].embeddings.create(model=OPENAI[modelo], input=lote))
        USO[modelo] += r.usage.total_tokens; return idx, [d.embedding for d in r.data]
    with ThreadPoolExecutor(hilos) as ex:
        for n, (idx, embs) in enumerate(ex.map(uno, lotes), 1):
            for i, e in zip(idx, embs): out[i] = e
            if n % 20 == 0: print(f'  {modelo}: {n}/{len(lotes)} lotes', flush=True)
    return _norm(out)


def _embed_contextual(cl, textos, docs, hilos=4):
    """voyage-context-4: cada fragmento se codifica sabiendo qué otros fragmentos tiene su documento.
    Los documentos largos se parten en grupos de fragmentos consecutivos (≤ CTX_DOC_MAX_TOK) que se tratan como un documento."""
    grupos, cur, tok, doc_ant = [], [], 0, None
    for i, (t, d) in enumerate(zip(textos, docs)):
        e = _est(t)
        if cur and (d != doc_ant or tok + e > CTX_DOC_MAX_TOK): grupos.append(cur); cur, tok = [], 0
        cur.append(i); tok += e; doc_ant = d
    if cur: grupos.append(cur)
    # peticiones: varios grupos por llamada sin pasar de ~LIMITE tokens
    peticiones, pet, tp = [], [], 0
    for g in grupos:
        e = sum(_est(textos[i]) for i in g)
        if pet and (tp + e > LIMITE['voyage-context-4'] or len(pet) >= 100 or sum(len(x) for x in pet) + len(g) > 8000):
            peticiones.append(pet); pet, tp = [], 0
        pet.append(g); tp += e
    if pet: peticiones.append(pet)
    out = [None] * len(textos)

    def una(pet):
        r = _reintentar(lambda: cl['voyage'].contextualized_embed(inputs=[[textos[i] for i in g] for g in pet], model='voyage-context-4', input_type='document'))
        USO['voyage-context-4'] += r.total_tokens
        return pet, [res.embeddings for res in r.results]
    with ThreadPoolExecutor(hilos) as ex:
        for n, (pet, embs) in enumerate(ex.map(una, peticiones), 1):
            for g, eg in zip(pet, embs):
                assert len(g) == len(eg)
                for i, e in zip(g, eg): out[i] = e
            if n % 20 == 0: print(f'  voyage-context-4: {n}/{len(peticiones)} peticiones', flush=True)
    return _norm(out)


def embed_docs(modelo, textos, docs):
    cl = _clientes()
    if modelo == 'voyage-context-4': return _embed_contextual(cl, textos, docs)
    return _embed_simple(cl, modelo, textos, 'document')


def embed_queries(modelo, consultas, hilos=4):
    cl = _clientes()
    if modelo == 'voyage-context-4':
        out = [None] * len(consultas)
        def uno(idx):
            r = _reintentar(lambda: cl['voyage'].contextualized_embed(inputs=[[consultas[i]] for i in idx], model=modelo, input_type='query'))
            USO[modelo] += r.total_tokens; return idx, [res.embeddings[0] for res in r.results]
        with ThreadPoolExecutor(hilos) as ex:
            for idx, embs in ex.map(uno, [list(range(i, min(i + 100, len(consultas)))) for i in range(0, len(consultas), 100)]):
                for i, e in zip(idx, embs): out[i] = e
        return _norm(out)
    return _embed_simple(cl, modelo, consultas, 'query')
