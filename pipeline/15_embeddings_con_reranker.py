"""Fase 3a-bis · paso 3: híbrido + vigencia + reranker bge (top-20, con contexto) para cada modelo de embeddings elegido.
Los pares (consulta, fragmento) puntuados por el reranker se comparten entre modelos (caché), así no se repite trabajo.
Uso: python 15_embeddings_con_reranker.py --modelos voyage-context-4 voyage-4-large e5-small [--split dev] [--dispositivo auto|cpu|cuda] [--fp16] [--lote 16]
En GPU (Colab T4): pipeline/colab/reranker_colab.ipynb
Salida: rag-bocc/evaluacion/fase3a/embeddings-reranker-<split>.json
"""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from evaluar import Evaluador, cargar_golden
from vigencia import doc_ok
import almacen

ap = argparse.ArgumentParser(); ap.add_argument('--modelos', nargs='+', required=True); ap.add_argument('--split', default='dev'); ap.add_argument('--topk', type=int, default=20)
ap.add_argument('--sufijo', default=''); ap.add_argument('--dispositivo', default='auto'); ap.add_argument('--fp16', action='store_true'); ap.add_argument('--lote', type=int, default=16)
args = ap.parse_args(); sufijo = args.sufijo
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
gold = cargar_golden(B, args.split)
ch = chunk_corpus(rows, 'estructural'); ids = [c['cid'] for c in ch]
ev = Evaluador(ch, gold)
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch])
from sentence_transformers import CrossEncoder
import torch
disp = ('cuda' if torch.cuda.is_available() else 'cpu') if args.dispositivo == 'auto' else args.dispositivo
ce = CrossEncoder('BAAI/bge-reranker-v2-m3', device=disp, max_length=512)
if args.fp16 and disp == 'cuda': ce.model.half()
print('reranker bge en', disp, '(fp16)' if args.fp16 and disp == 'cuda' else '', flush=True)
par = {}
def puntuar(q, cand):
    falta = [i for i in cand if (q, i) not in par]
    if falta:
        sc = ce.predict([(q, ch[i]['ctx'] + '\n' + ch[i]['texto']) for i in falta], batch_size=args.lote, show_progress_bar=False)
        for i, s in zip(falta, sc): par[(q, i)] = float(s)
    return sorted(((i, par[(q, i)]) for i in cand), key=lambda x: -x[1])
res = {}
for m in args.modelos:
    m = almacen.nombre(m)
    if m == 'e5-small':    # línea base local: las consultas se codifican al vuelo con «query: »
        from sentence_transformers import SentenceTransformer
        mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
        cons = sorted({t for q in gold if q['fuentes'] for t in [q['pregunta']] + q.get('variantes', [])})
        Q = dict(zip(cons, mod.encode(['query: ' + q for q in cons], normalize_embeddings=True, batch_size=64)))
        E = almacen.cargar(B, m, 'estructural', 1, ch)
    else:
        z = np.load(almacen.carpeta(B, m) + 'consultas.npz', allow_pickle=True); Q = dict(zip(z['textos'].tolist(), z['emb']))
        E = almacen.cargar(B, m, 'estructural', 1, ch)
    cd = {}; cr = {}
    def den(q):
        if q not in cd:
            s = E @ Q[q]; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]; cd[q] = [(int(i), float(s[i])) for i in top]
        return cd[q]
    def f(q):
        if q not in cr:
            base = [(i, s) for i, s in rrf([bm1.search(q, 200), den(q)], top=200) if doc_ok(est[ch[i]['doc']], q)][:args.topk]
            cr[q] = puntuar(q, [i for i, _ in base])
        return cr[q]
    t = time.time(); r = ev.evaluar(f); res[m] = r
    a, v = r['todos|pregunta'], r['todos|variante']
    print(f"{m:20s} +bge top{args.topk}  doc@10 {a['doc@10']:.3f} cita@1 {a['cita@1']:.3f} cita@5 {a['cita@5']:.3f} cita@10 {a['cita@10']:.3f} mrr {a['mrr']:.3f} | var cita@1 {v['cita@1']:.3f} cita@10 {v['cita@10']:.3f} mrr {v['mrr']:.3f} ({time.time()-t:.0f}s)", flush=True)
    json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/embeddings-reranker-{args.split}{sufijo}.json', 'w'), ensure_ascii=False, indent=1)
