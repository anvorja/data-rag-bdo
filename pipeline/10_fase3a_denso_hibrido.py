"""Fase 3a (paso 2): denso, híbrido (RRF), reranker, filtro de vigencia y abstención, sobre el set de DESARROLLO.
Requiere los embeddings de pipeline/fase3a/embed.py (en _raw/emb). Uso: python 10_fase3a_denso_hibrido.py [--reranker mmarco|bge|ninguno]
Salida: rag-bocc/evaluacion/fase3a/resultados-<split>-denso-hibrido[-<reranker>].json
"""
import json, os, sys, time, argparse
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, Densa, rrf
from evaluar import Evaluador, cargar_golden
from vigencia import doc_ok

ap = argparse.ArgumentParser(); ap.add_argument('--reranker', default='mmarco'); ap.add_argument('--topk', type=int, default=30); ap.add_argument('--solo-ctx', action='store_true'); ap.add_argument('--sin-variantes', action='store_true'); ap.add_argument('--omitir-base', action='store_true'); ap.add_argument('--split', default='dev', choices=['dev', 'test'])
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
dev = cargar_golden(B, args.split)
ch = chunk_corpus(rows, 'estructural')
ev = Evaluador(ch, dev)
assert [c['cid'] for c in ch] == json.load(open(B + '_raw/emb/multilingual-e5-small__estructural__ctx0.ids.json'))
from sentence_transformers import SentenceTransformer
modelo = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu'); modelo._nombre = 'e5'
E0 = np.load(B + '_raw/emb/multilingual-e5-small__estructural__ctx0.npy')
E1 = np.load(B + '_raw/emb/multilingual-e5-small__estructural__ctx1.npy')
bm0 = BM25([c['texto'] for c in ch]); bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch])
d0, d1 = Densa(E0, modelo), Densa(E1, modelo)
cache = {}
def memo(nombre, fn):
    def g(q):
        k = (nombre, q)
        if k not in cache: cache[k] = fn(q)
        return cache[k]
    return g
bm0s, bm1s = memo('bm0', lambda q: bm0.search(q, 200)), memo('bm1', lambda q: bm1.search(q, 200))
d0s, d1s = memo('d0', lambda q: d0.search(q, 200)), memo('d1', lambda q: d1.search(q, 200))
def vig(f):
    return lambda q: [(i, s) for i, s in f(q) if doc_ok(est[ch[i]['doc']], q)]
sistemas = {
    'bm25 ctx1 (base)': lambda q: bm1s(q)[:20],
    'denso ctx0': lambda q: d0s(q)[:20],
    'denso ctx1': lambda q: d1s(q)[:20],
    'híbrido ctx0 (bm25+denso)': lambda q: rrf([bm0s(q), d0s(q)])[:20],
    'híbrido ctx1 (bm25+denso)': lambda q: rrf([bm1s(q), d1s(q)])[:20],
    'híbrido ctx1 + vigencia': vig(lambda q: rrf([bm1s(q), d1s(q)], top=200))
}
res = {}
for n, f in ([] if args.omitir_base else sistemas.items()):
    t = time.time(); r = ev.evaluar(lambda q: f(q)[:20]); res[n] = r
    m, v = r['todos|pregunta'], r['todos|variante']
    print(f"{n:32s} preg doc@10 {m['doc@10']} cita@5 {m['cita@5']} cita@10 {m['cita@10']} mrr {m['mrr']} | var cita@10 {v['cita@10']} mrr {v['mrr']} ({time.time()-t:.0f}s)", flush=True)
os.makedirs(B + 'rag-bocc/evaluacion/fase3a', exist_ok=True)
json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/resultados-{args.split}-denso-hibrido.json', 'w'), ensure_ascii=False, indent=1)

if args.reranker != 'ninguno':
    from sentence_transformers import CrossEncoder
    nombre = {'mmarco': 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1', 'bge': 'BAAI/bge-reranker-v2-m3'}[args.reranker]
    ce = CrossEncoder(nombre, device='cpu', max_length=512)
    base = vig(lambda q: rrf([bm1s(q), d1s(q)], top=200))
    rc = {}
    def reranked(q, usar_ctx):
        k = (q, usar_ctx)
        if k not in rc:
            cand = base(q)[:args.topk]
            pares = [(q, ((ch[i]['ctx'] + '\n') if usar_ctx else '') + ch[i]['texto']) for i, _ in cand]
            sc = ce.predict(pares, batch_size=16, show_progress_bar=False)
            rc[k] = sorted(((i, float(s)) for (i, _), s in zip(cand, sc)), key=lambda x: -x[1])
        return rc[k]
    for usar_ctx in ((True,) if args.solo_ctx else (False, True)):
        n = f"híbrido+vigencia+reranker {args.reranker} (top{args.topk}{', ctx' if usar_ctx else ''})"
        t = time.time(); r = ev.evaluar(lambda q: reranked(q, usar_ctx), con_variantes=not args.sin_variantes); res[n] = r
        m = r['todos|pregunta']; v = r.get('todos|variante', {'cita@10': '-', 'mrr': '-'})
        print(f"{n:55s} preg doc@10 {m['doc@10']} cita@1 {m['cita@1']} cita@5 {m['cita@5']} cita@10 {m['cita@10']} mrr {m['mrr']} | var cita@10 {v['cita@10']} mrr {v['mrr']} ({time.time()-t:.0f}s)", flush=True)
    json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/resultados-{args.split}-denso-hibrido-{args.reranker}.json', 'w'), ensure_ascii=False, indent=1)
