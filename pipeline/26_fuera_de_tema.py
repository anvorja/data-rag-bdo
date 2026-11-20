"""Fase 3b · ¿qué tan bien se frena el uso del asistente para temas ajenos al banco (código, ciencia, tareas, mezclas banca+código, inyección de instrucciones)?
Sondas escritas por el proyecto (rag-bocc/evaluacion/fase3b/fuera-de-tema.jsonl). Mide la compuerta de suficiencia ANTES de generar: puntaje de rerank-3 < umbral (0,7617) y, opcional, el juez DeepSeek.
Una sonda «frenada» = la compuerta pide abstenerse (el LLM redactor ni se llama). Uso: set -a; . ./.env; set +a; python pipeline/26_fuera_de_tema.py [--llm deepseek-flash]
Salida: rag-bocc/evaluacion/fase3b/fuera-de-tema-resultado.json"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a')); sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3b'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from vigencia import doc_ok_blanda
import almacen, embed_api, suficiencia

ap = argparse.ArgumentParser(); ap.add_argument('--llm'); ap.add_argument('--umbral', type=float, default=0.7617)
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(line) for line in open(B + 'rag-bocc/corpus.jsonl')]; est = {r['id']: r['estado_vigencia'] for r in rows}
ch = chunk_corpus(rows, 'estructural'); bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch]); E = almacen.cargar(B, 'e5-small', 'estructural', 1, ch)
sondas = [json.loads(line) for line in open(B + 'rag-bocc/evaluacion/fase3b/fuera-de-tema.jsonl')]
from sentence_transformers import SentenceTransformer
mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
Q = mod.encode(['query: ' + s['pregunta'] for s in sondas], normalize_embeddings=True)
cl = embed_api._clientes()['voyage']; juez = suficiencia.cliente('deepseek', args.llm) if args.llm else None
res = []
for s, qv in zip(sondas, Q):
    q = s['pregunta']; sc = E @ qv; top = np.argpartition(-sc, 199)[:200]; top = top[np.argsort(-sc[top])]
    cand = [i for i, _ in rrf([bm1.search(q, 200), [(int(i), float(sc[i])) for i in top]], top=200) if doc_ok_blanda(est[ch[i]['doc']], q)][:20]
    r = embed_api._reintentar(lambda: cl.rerank(q, [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i in cand], model='rerank-3', truncation=True))
    rr = sorted(((cand[x.index], float(x.relevance_score)) for x in r.results), key=lambda z: -z[1])
    d = dict(grupo=s['grupo'], pregunta=q, top1=round(rr[0][1], 3), frena_rerank=rr[0][1] < args.umbral)
    if juez:
        ok, motivo = suficiencia.por_llm(q, [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i, _ in rr[:4]], 'deepseek', _cl=juez, prompt='p1')
        d['frena_llm'] = not ok; d['motivo_llm'] = motivo
    d['frena_ambos'] = d['frena_rerank'] and d.get('frena_llm', True); d['frena_alguno'] = d['frena_rerank'] or d.get('frena_llm', False)
    res.append(d)
out = {}
for g in sorted({d['grupo'] for d in res}):
    xs = [d for d in res if d['grupo'] == g]
    out[g] = dict(n=len(xs), frena_rerank=sum(d['frena_rerank'] for d in xs), **({'frena_llm': sum(d['frena_llm'] for d in xs)} if juez else {}), frena_ambos=sum(d['frena_ambos'] for d in xs), frena_alguno=sum(d['frena_alguno'] for d in xs))
    print(g, out[g])
print('PASAN la compuerta con el criterio «ambos»:'); [print('  ', d['grupo'], d['top1'], d['pregunta'][:90]) for d in res if not d['frena_ambos']]
json.dump(dict(umbral=args.umbral, juez=args.llm, resumen=out, detalle=res), open(B + 'rag-bocc/evaluacion/fase3b/fuera-de-tema-resultado.json', 'w'), ensure_ascii=False, indent=1)
