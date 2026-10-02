"""Fase 3a: experimentos de recuperación sobre el set de DESARROLLO del golden set (el test no se usa para decidir).
Compara fragmentación (fijo / estructural / estructural+contexto) con BM25 y, cuando existan los embeddings, denso, híbrido (RRF) y reranker.
Salida: rag-bocc/evaluacion/fase3a/resultados-dev.json
"""
import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25
from evaluar import Evaluador, cargar_golden

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
dev = cargar_golden(B, 'dev')
res = {}
for modo, ctx in (('fijo', False), ('estructural', False), ('estructural', True)):
    t = time.time()
    ch = chunk_corpus(rows, modo)
    textos = [((c['ctx'] + '\n') if ctx else '') + c['texto'] for c in ch]
    bm = BM25(textos)
    ev = Evaluador(ch, dev)
    r = ev.evaluar(lambda q: bm.search(q, 20))
    nombre = f"bm25|{modo}|ctx{int(ctx)}"
    res[nombre] = dict(chunks=len(ch), inalcanzables=len(ev.inalcanzables()), metricas=r)
    m = r['todos|pregunta']; v = r['todos|variante']
    print(nombre, len(ch), 'inalcanzables', len(ev.inalcanzables()), '| preg doc@10', m['doc@10'], 'cita@10', m['cita@10'], 'mrr', m['mrr'], '| var cita@10', v['cita@10'], round(time.time() - t), 's')
os.makedirs(B + 'rag-bocc/evaluacion/fase3a', exist_ok=True)
json.dump(res, open(B + 'rag-bocc/evaluacion/fase3a/resultados-dev-bm25.json', 'w'), ensure_ascii=False, indent=1)
