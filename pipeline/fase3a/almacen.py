"""Almacén de embeddings (no versionado, en _raw/emb/) con actualización incremental.

Disposición:
  _raw/emb/<modelo>/<chunking>__ctx<0|1>.npy         matriz (n_fragmentos × dim), float32, normalizada
  _raw/emb/<modelo>/<chunking>__ctx<0|1>.ids.json    lista de cid (orden de las filas)
  _raw/emb/<modelo>/<chunking>__ctx<0|1>.hashes.json hash del TEXTO que se codificó en cada fila (contexto + fragmento)
  _raw/emb/<modelo>/consultas.npz                    vectores de las consultas del golden (textos, emb)
  _raw/emb/<modelo>/manifiesto.json                  modelo, dimensión, fechas de cálculo
  _raw/emb/api/uso.json                              tokens consumidos por APIs de pago
Nombres de modelo: e5-small, e5-large, bge-m3, voyage-4-lite, voyage-4, voyage-4-large, voyage-context-4, openai-3-small.

Cada mes cambian documentos (tasas, tarifas, campañas): `alinear` reutiliza las filas cuyo (cid, hash) no cambió y devuelve los índices de las que
hay que recalcular. Así solo se codifica lo nuevo o modificado, sin importar el orden ni el tamaño del corpus."""
import hashlib, json, os
import numpy as np

ALIAS = {'e5': 'e5-small', 'multilingual-e5-small': 'e5-small', 'multilingual-e5-large': 'e5-large'}


def nombre(m): return ALIAS.get(m, m)
def hash_texto(t): return hashlib.sha1(t.encode()).hexdigest()[:12]
def texto_indexado(c, ctx): return ((c['ctx'] + '\n') if ctx else '') + c['texto']
def carpeta(B, modelo): return B + f'_raw/emb/{nombre(modelo)}/'
def base(B, modelo, chunking, ctx): return carpeta(B, modelo) + f'{chunking}__ctx{int(ctx)}'


def alinear(B, modelo, chunking, ctx, chunks):
    """Devuelve (E, faltan): E con las filas reutilizables en su sitio (ceros en las demás) y la lista de índices a recalcular."""
    b = base(B, modelo, chunking, ctx); textos = [hash_texto(texto_indexado(c, ctx)) for c in chunks]
    if not (os.path.exists(b + '.npy') and os.path.exists(b + '.hashes.json')): return None, list(range(len(chunks)))
    E0 = np.load(b + '.npy'); ids0 = json.load(open(b + '.ids.json')); h0 = json.load(open(b + '.hashes.json'))
    fila = {(i, h): k for k, (i, h) in enumerate(zip(ids0, h0))}
    E = np.zeros((len(chunks), E0.shape[1]), dtype='float32'); faltan = []
    for k, (c, h) in enumerate(zip(chunks, textos)):
        j = fila.get((c['cid'], h))
        if j is None: faltan.append(k)
        else: E[k] = E0[j]
    return E, faltan


def guardar(B, modelo, chunking, ctx, chunks, E, extra=None):
    os.makedirs(carpeta(B, modelo), exist_ok=True); b = base(B, modelo, chunking, ctx)
    np.save(b + '.npy', E.astype('float32'))
    json.dump([c['cid'] for c in chunks], open(b + '.ids.json', 'w'))
    json.dump([hash_texto(texto_indexado(c, ctx)) for c in chunks], open(b + '.hashes.json', 'w'))
    mf = carpeta(B, modelo) + 'manifiesto.json'
    m = json.load(open(mf)) if os.path.exists(mf) else {}
    m.update(modelo=nombre(modelo), dim=int(E.shape[1])); m.setdefault('calculos', {})[f'{chunking}__ctx{int(ctx)}'] = dict(filas=len(chunks), **(extra or {}))
    json.dump(m, open(mf, 'w'), indent=1)


def cargar(B, modelo, chunking, ctx, chunks):
    """Carga la matriz alineada con `chunks`; falla si falta algo (hay que calcularlo antes con 13_embeddings_api.py o embed.py)."""
    E, faltan = alinear(B, modelo, chunking, ctx, chunks)
    if E is None or faltan: raise SystemExit(f'{nombre(modelo)} ctx{int(ctx)}: faltan {len(faltan)} de {len(chunks)} vectores; recalcúlalos (pipeline/13_embeddings_api.py o pipeline/fase3a/embed.py)')
    return E
