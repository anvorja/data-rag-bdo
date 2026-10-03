"""Fase 3a (paso 4): análisis de fallos de recuperación en `dev` (híbrido + contexto + vigencia, antes del reranker).
Clasifica, por pregunta con fuente, dónde aparece el primer fragmento relevante: top-10, 11-30 (lo puede arreglar el reranker),
31-200 o fuera de los 200 candidatos (fallo de recuperación). Salida: rag-bocc/evaluacion/fase3a/fallos-dev.json
"""
import collections, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, Densa, rrf
from evaluar import Evaluador, cargar_golden
from vigencia import doc_ok

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
dev = cargar_golden(B, 'dev'); ch = chunk_corpus(rows, 'estructural'); ev = Evaluador(ch, dev)
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu'); m._nombre = 'e5'
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch]); d1 = Densa(__import__('almacen').cargar(B, 'e5-small', 'estructural', 1, ch), m)
cat = collections.defaultdict(collections.Counter); fallos = []
for q in dev:
    if not q['fuentes']: continue
    for kind, t in [('pregunta', q['pregunta'])] + [('variante', v) for v in q.get('variantes', [])]:
        fus = [i for i, _ in rrf([bm1.search(t, 200), d1.search(t, 200)], top=200) if doc_ok(est[ch[i]['doc']], t)]
        rk = [next((r for r, i in enumerate(fus, 1) if i in s), None) for s in ev._rel[q['id']]]
        peor = None if any(x is None for x in rk) else max(rk)
        c = 'top10' if peor and peor <= 10 else '11-30' if peor and peor <= 30 else '31-200' if peor else 'fuera_de_200'
        cat[(q['tipo'], kind)][c] += 1; cat[('todos', kind)][c] += 1
        if c != 'top10' and kind == 'pregunta': fallos.append(dict(id=q['id'], tipo=q['tipo'], categoria=c, pregunta=q['pregunta'], rangos=rk, docs=[f['doc_id'] for f in q['fuentes']]))
res = {f'{a}|{b}': dict(c) for (a, b), c in sorted(cat.items())}
json.dump(dict(resumen=res, fallos_pregunta=fallos), open(B + 'rag-bocc/evaluacion/fase3a/fallos-dev.json', 'w'), ensure_ascii=False, indent=1)
for k in ('todos|pregunta', 'todos|variante'): print(k, res[k])
for k, v in res.items():
    if k.endswith('|pregunta') and not k.startswith('todos'): print(k, v)
for f in fallos: print(f['categoria'], f['tipo'], f['id'], f['pregunta'][:90], f['rangos'])
