"""Vigencia · paso 2: política DURA (oculta lo vencido) frente a BLANDA (recupera lo vencido y lo marca), con y sin reranker de Voyage.
Equivalencia de versiones: una pregunta cuya fuente fue reemplazada por una versión nueva del mismo documento se considera acertada con cualquiera de las versiones.
Uso: set -a; . ./.env; set +a; python 22_vigencia_blanda.py [--split dev] [--reranker rerank-3]
Salida: rag-bocc/evaluacion/fase3a/vigencia-blanda-<split>.json"""
import argparse, collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from evaluar import Evaluador, cargar_golden
import vigencia, almacen, embed_api

ap = argparse.ArgumentParser(); ap.add_argument('--split', default='dev'); ap.add_argument('--reranker', default='rerank-3'); args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
equiv = vigencia.grupos_version(rows)
gold = cargar_golden(B, args.split)
ch = chunk_corpus(rows, 'estructural')
NV = {'vencido', 'historico'}
g_vig = [q for q in gold if q['fuentes'] and all(est[f['doc_id']] not in NV for f in q['fuentes'])]
g_nov = [q for q in gold if q['fuentes'] and any(est[f['doc_id']] in NV for f in q['fuentes'])]
evs = {'todas': Evaluador(ch, gold, equiv), 'fuente vigente': Evaluador(ch, g_vig, equiv), 'fuente vencida/histórica': Evaluador(ch, g_nov, equiv)}
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch])
from sentence_transformers import SentenceTransformer
mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
cons = sorted({t for q in gold for t in [q['pregunta']] + q.get('variantes', [])})
Q = dict(zip(cons, mod.encode(['query: ' + q for q in cons], normalize_embeddings=True, batch_size=64)))
E = almacen.cargar(B, 'e5-small', 'estructural', 1, ch)
fus = {}
for q in cons:
    s = E @ Q[q]; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]
    fus[q] = rrf([bm1.search(q, 200), [(int(i), float(s[i])) for i in top]], top=200)
POL = {'dura': lambda e, q: vigencia.doc_ok(e, q), 'blanda': lambda e, q: vigencia.doc_ok_blanda(e, q)}
def cand(q, pol, k=20): return [i for i, _ in fus[q] if POL[pol](est[ch[i]['doc']], q)][:k]
cl = embed_api._clientes()['voyage']; cache = {}
def rerank(q, ids):
    k = (q, tuple(ids))
    if k not in cache:
        r = embed_api._reintentar(lambda: cl.rerank(q, [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i in ids], model=args.reranker, truncation=True))
        cache[k] = sorted(((ids[x.index], float(x.relevance_score)) for x in r.results), key=lambda z: -z[1])
    return cache[k]
res = {}
print(f"{'sistema':34s} {'subconjunto':26s} {'n':>4s} {'cita@1':>7s} {'cita@10':>8s} {'MRR':>6s} | {'var cita@1':>10s} {'var cita@10':>11s} {'var MRR':>8s}")
for pol in ('dura', 'blanda'):
    for sis in ('híbrido', 'híbrido + ' + args.reranker):
        f = (lambda q, p=pol: [(i, 0) for i in cand(q, p)]) if sis == 'híbrido' else (lambda q, p=pol: rerank(q, cand(q, p)))
        for sub, ev in evs.items():
            r = ev.evaluar(f); res[f'{pol} | {sis} | {sub}'] = r; a, v = r['todos|pregunta'], r['todos|variante']
            print(f"{pol + ' · ' + sis:34s} {sub:26s} {a['n']:4d} {a['cita@1']:7.3f} {a['cita@10']:8.3f} {a['mrr']:6.3f} | {v['cita@1']:10.3f} {v['cita@10']:11.3f} {v['mrr']:8.3f}", flush=True)
# contaminación: en consultas SIN intención temporal, ¿cuántas veces aparece un documento vencido entre los 5 primeros?
sin_t = [q for q in cons if not vigencia.intencion_temporal(q)]
for pol in ('dura', 'blanda'):
    top5 = [cand(q, pol, 5) for q in sin_t]
    c5 = sum(any(est[ch[i]['doc']] == 'vencido' for i in t) for t in top5) / len(sin_t); c1 = sum(bool(t) and est[ch[t[0]]['doc']] == 'vencido' for t in top5) / len(sin_t)
    res[f'contaminacion {pol}'] = dict(consultas=len(sin_t), vencido_en_top5=round(c5, 3), vencido_en_top1=round(c1, 3)); print(f'consultas sin intención temporal ({len(sin_t)}), política {pol}: vencido en el top-5 {c5:.1%}, en el top-1 {c1:.1%}')
json.dump(res, open(B + f'rag-bocc/evaluacion/fase3a/vigencia-blanda-{args.split}.json', 'w'), ensure_ascii=False, indent=1)
