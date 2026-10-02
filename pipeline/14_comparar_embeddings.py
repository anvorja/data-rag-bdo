"""Fase 3a-bis · paso 2: compara modelos de embeddings sobre el golden (split dev por defecto).

Para cada modelo evalúa, con y sin contexto de metadatos (ctx1/ctx0): denso solo y híbrido (BM25 + denso, RRF) con filtro de vigencia.
Sin reranker (es ortogonal y se aplica después al ganador). Misma partición de fragmentos y mismas preguntas para todos.
Requiere pipeline/13_embeddings_api.py (y embed.py para la línea base e5). Salida: rag-bocc/evaluacion/fase3a/comparacion-embeddings-<split>.json
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from evaluar import Evaluador, cargar_golden
from vigencia import doc_ok

ap = argparse.ArgumentParser(); ap.add_argument('--split', default='dev', choices=['dev', 'test']); ap.add_argument('--modelos', nargs='*')
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
gold = cargar_golden(B, args.split)
ch = chunk_corpus(rows, 'estructural')
ids = [c['cid'] for c in ch]
ev = Evaluador(ch, gold)
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch]); bm0 = BM25([c['texto'] for c in ch])
consultas = sorted({t for q in gold if q['fuentes'] for t in [q['pregunta']] + q.get('variantes', [])})
cb = {}
def bm(i, q):
    if (i, q) not in cb: cb[(i, q)] = (bm1 if i else bm0).search(q, 200)
    return cb[(i, q)]

ya = {}
def consultas_vec(m):
    if m == 'e5':
        from sentence_transformers import SentenceTransformer
        mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
        return dict(zip(consultas, mod.encode(['query: ' + q for q in consultas], normalize_embeddings=True, batch_size=64)))
    z = np.load(B + f'_raw/emb/q__{m}.npz', allow_pickle=True)
    d = dict(zip(z['textos'].tolist(), z['emb']))
    faltan = [q for q in consultas if q not in d]
    assert not faltan, f'{m}: faltan {len(faltan)} consultas (corre 13_embeddings_api.py con --splits {args.split})'
    return d

def modelos_disponibles():
    ms = ['e5'] if os.path.exists(B + '_raw/emb/multilingual-e5-small__estructural__ctx1.npy') else []
    for f in sorted(os.listdir(B + '_raw/emb')):
        if f.endswith('__estructural__ctx1.npy') and not f.startswith('multilingual-e5'): ms.append(f.split('__')[0])
    return ms

res = {}
for m in args.modelos or modelos_disponibles():
    Q = consultas_vec(m)
    for ctx in (1, 0):
        fn = B + f"_raw/emb/{'multilingual-e5-small' if m == 'e5' else m}__estructural__ctx{ctx}.npy"
        if not os.path.exists(fn): continue
        assert json.load(open(fn.replace('.npy', '.ids.json'))) == ids
        E = np.load(fn); cd = {}
        def den(q):
            if q not in cd:
                s = E @ Q[q]; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]; cd[q] = [(int(i), float(s[i])) for i in top]
            return cd[q]
        sist = {'denso': lambda q: den(q)[:20],
                'híbrido+vigencia': lambda q: [(i, s) for i, s in rrf([bm(ctx, q), den(q)], top=200) if doc_ok(est[ch[i]['doc']], q)][:20]}
        for sn, f in sist.items():
            r = ev.evaluar(f); k = f'{m} ctx{ctx} · {sn}'; res[k] = r
            a, v = r['todos|pregunta'], r['todos|variante']
            print(f"{k:42s} doc@10 {a['doc@10']:.3f} cita@1 {a['cita@1']:.3f} cita@10 {a['cita@10']:.3f} mrr {a['mrr']:.3f} | var cita@10 {v['cita@10']:.3f} mrr {v['mrr']:.3f}", flush=True)
json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/comparacion-embeddings-{args.split}.json', 'w'), ensure_ascii=False, indent=1)
