"""Fase 3a-bis · paso 4: reranker por API (Voyage rerank-3 / rerank-3-lite) sobre los mismos candidatos que el reranker abierto bge:
híbrido (BM25 + e5-small) + filtro de vigencia → top-20 → reranker. Compara con `15_embeddings_con_reranker.py --modelos e5-small` (misma métrica y mismo corpus).
Uso: set -a; . ./.env; set +a; python 21_reranker_voyage.py --modelos rerank-3 rerank-3-lite [--split dev]
Salida: rag-bocc/evaluacion/fase3a/reranker-voyage-<split>.json y consumo en _raw/emb/api/uso.json. La clave solo se lee del entorno (VOYAGE_API_KEY)."""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from evaluar import Evaluador, cargar_golden
from vigencia import doc_ok
import almacen, embed_api

ap = argparse.ArgumentParser(); ap.add_argument('--modelos', nargs='+', default=['rerank-3', 'rerank-3-lite']); ap.add_argument('--split', default='dev'); ap.add_argument('--topk', type=int, default=20)
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
gold = cargar_golden(B, args.split)
ch = chunk_corpus(rows, 'estructural')
ev = Evaluador(ch, gold)
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch])
from sentence_transformers import SentenceTransformer
mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
cons = sorted({t for q in gold if q['fuentes'] for t in [q['pregunta']] + q.get('variantes', [])})
Q = dict(zip(cons, mod.encode(['query: ' + q for q in cons], normalize_embeddings=True, batch_size=64)))
E = almacen.cargar(B, 'e5-small', 'estructural', 1, ch)
cl = embed_api._clientes()['voyage']
cand = {}
for q in cons:
    s = E @ Q[q]; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]
    den = [(int(i), float(s[i])) for i in top]
    cand[q] = [i for i, _ in [(i, x) for i, x in rrf([bm1.search(q, 200), den], top=200) if doc_ok(est[ch[i]['doc']], q)][:args.topk]]
print(len(cons), 'consultas con candidatos', flush=True)
uso_f = B + '_raw/emb/api/uso.json'; uso = json.load(open(uso_f)) if os.path.exists(uso_f) else {}
res = {}
for m in args.modelos:
    cache = {}; tok = [0]
    def una(q):
        docs = [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i in cand[q]]
        r = embed_api._reintentar(lambda: cl.rerank(q, docs, model=m, truncation=True)); tok[0] += r.total_tokens
        return q, sorted(((cand[q][x.index], float(x.relevance_score)) for x in r.results), key=lambda z: -z[1])
    t = time.time()
    with ThreadPoolExecutor(4) as ex:
        for n, (q, v) in enumerate(ex.map(una, cons), 1):
            cache[q] = v
            if n % 100 == 0: print(f'  {m}: {n}/{len(cons)}', flush=True)
    r = ev.evaluar(lambda q: cache[q]); res[m] = r
    a, v = r['todos|pregunta'], r['todos|variante']
    print(f"{m:14s} +{args.topk}  doc@10 {a['doc@10']:.3f} cita@1 {a['cita@1']:.3f} cita@5 {a['cita@5']:.3f} cita@10 {a['cita@10']:.3f} mrr {a['mrr']:.3f} | var cita@1 {v['cita@1']:.3f} cita@10 {v['cita@10']:.3f} mrr {v['mrr']:.3f} | {tok[0]:,} tokens, {time.time()-t:.0f}s", flush=True)
    uso[f'reranker__{m}'] = uso.get(f'reranker__{m}', 0) + tok[0]; json.dump(uso, open(uso_f, 'w'), indent=1)
    res[m]['_consumo'] = dict(tokens=tok[0], consultas=len(cons), segundos=round(time.time() - t))
    json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/reranker-voyage-{args.split}.json', 'w'), ensure_ascii=False, indent=1)
