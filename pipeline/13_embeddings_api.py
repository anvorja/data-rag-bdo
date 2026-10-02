"""Embeddings del corpus y de las consultas del golden con modelos por API (Voyage, OpenAI), de forma INCREMENTAL: solo se codifica lo nuevo o modificado.

Uso:  set -a; . ./.env; set +a
      python 13_embeddings_api.py --modelos voyage-4 voyage-context-4 --ctx 1 0 [--splits dev test] [--prueba 300]
Salida (no versionada): _raw/emb/<modelo>/ (ver fase3a/almacen.py) y _raw/emb/api/uso.json (tokens consumidos).
voyage-context-4 codifica cada fragmento con el contexto de TODO su documento: si cambia un fragmento se recalculan todos los de ese documento.
--prueba N procesa solo N fragmentos y no guarda (mide tiempo y tokens).
"""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
import almacen, embed_api

ap = argparse.ArgumentParser()
ap.add_argument('--modelos', nargs='+', required=True); ap.add_argument('--ctx', nargs='+', type=int, default=[1])
ap.add_argument('--prueba', type=int, default=0); ap.add_argument('--splits', nargs='+', default=['dev'])
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
ch = chunk_corpus([json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')], 'estructural')
gold = [q for q in (json.loads(l) for l in open(B + 'rag-bocc/golden/golden-v0.jsonl')) if q['split'] in args.splits]
consultas = sorted({t for q in gold if q['fuentes'] for t in [q['pregunta']] + q.get('variantes', [])})
print(f'{len(ch)} fragmentos · {len(consultas)} consultas ({"+".join(args.splits)})', flush=True)
os.makedirs(B + '_raw/emb/api', exist_ok=True)
uso_f = B + '_raw/emb/api/uso.json'
uso = json.load(open(uso_f)) if os.path.exists(uso_f) else {}

for m in args.modelos:
    m = almacen.nombre(m)
    for ctx in args.ctx:
        if args.prueba:
            sub = ch[:args.prueba]; antes = embed_api.USO[m]; t = time.time()
            E = embed_api.embed_docs(m, [almacen.texto_indexado(c, ctx) for c in sub], [c['doc'] for c in sub]); seg, tok = time.time() - t, embed_api.USO[m] - antes
            print(f'{m} ctx{ctx}: {E.shape} {seg:.0f}s {tok:,} tokens · extrapolado a {len(ch)}: ~{tok * len(ch) / len(sub):,.0f} tokens, ~{seg * len(ch) / len(sub) / 60:.1f} min'); continue
        E, faltan = almacen.alinear(B, m, 'estructural', ctx, ch)
        if faltan and m == 'voyage-context-4':          # el contexto es el documento completo
            docs = {ch[k]['doc'] for k in faltan}; faltan = [k for k, c in enumerate(ch) if c['doc'] in docs]
        print(f'{m} ctx{ctx}: {len(faltan)} de {len(ch)} fragmentos por codificar', flush=True)
        if not faltan: continue
        sub = [ch[k] for k in faltan]; antes = embed_api.USO[m]; t = time.time()
        nuevos = embed_api.embed_docs(m, [almacen.texto_indexado(c, ctx) for c in sub], [c['doc'] for c in sub])
        tok = embed_api.USO[m] - antes
        if E is None: E = np.zeros((len(ch), nuevos.shape[1]), dtype='float32')
        E[faltan] = nuevos
        almacen.guardar(B, m, 'estructural', ctx, ch, E, dict(recalculados=len(faltan), tokens=tok, segundos=round(time.time() - t)))
        uso[f'{m}__ctx{ctx}'] = uso.get(f'{m}__ctx{ctx}', 0) + tok; json.dump(uso, open(uso_f, 'w'), indent=1)
        print(f'  {len(faltan)} fragmentos, {tok:,} tokens, {time.time() - t:.0f}s', flush=True)
    if args.prueba: continue
    fq = almacen.carpeta(B, m) + 'consultas.npz'
    prev = dict(np.load(fq, allow_pickle=True)) if os.path.exists(fq) else None
    ya = set(prev['textos'].tolist()) if prev is not None else set()
    nuevas = [c for c in consultas if c not in ya]
    if nuevas:
        Q = embed_api.embed_queries(m, nuevas)
        np.savez(fq, textos=np.array((prev['textos'].tolist() if prev is not None else []) + nuevas, dtype=object), emb=np.vstack([prev['emb'], Q]) if prev is not None else Q)
        print(f'consultas {m}: +{len(nuevas)}', flush=True)
json.dump(uso, open(uso_f, 'w'), indent=1)
