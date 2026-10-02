"""Fase 3a-bis · paso 1: calcula los embeddings del corpus (y de las consultas del golden) con modelos por API.

Uso:  set -a; . ./.env; set +a
      python 13_embeddings_api.py --modelos voyage-4 voyage-context-4 --ctx 0 1 [--prueba 300]
Salida (no versionada): _raw/emb/<modelo>__estructural__ctx<0|1>.npy + .ids.json ; _raw/emb/q__<modelo>.npz ; _raw/emb/uso.json
Es reanudable: si el .npy ya existe se omite. --prueba N procesa solo N fragmentos y no guarda (mide tiempo y tokens).
"""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
import embed_api

ap = argparse.ArgumentParser()
ap.add_argument('--modelos', nargs='+', required=True); ap.add_argument('--ctx', nargs='+', type=int, default=[1])
ap.add_argument('--prueba', type=int, default=0); ap.add_argument('--splits', nargs='+', default=['dev'])
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
ch = chunk_corpus(rows, 'estructural')
ids = [c['cid'] for c in ch]
os.makedirs(B + '_raw/emb', exist_ok=True)
gold = [q for q in (json.loads(l) for l in open(B + 'rag-bocc/golden/golden-v0.jsonl')) if q['split'] in args.splits]
consultas = sorted({t for q in gold if q['fuentes'] for t in [q['pregunta']] + q.get('variantes', [])})
print(f'{len(ch)} fragmentos · {len(consultas)} consultas ({"+".join(args.splits)})', flush=True)
uso_f = B + '_raw/emb/uso.json'
uso = json.load(open(uso_f)) if os.path.exists(uso_f) else {}

for m in args.modelos:
    for ctx in args.ctx:
        nombre = f'{m}__estructural__ctx{ctx}'
        f = B + f'_raw/emb/{nombre}.npy'
        if os.path.exists(f) and not args.prueba: print('ya existe', nombre); continue
        sub = ch[:args.prueba] if args.prueba else ch
        textos = [((c['ctx'] + '\n') if ctx else '') + c['texto'] for c in sub]
        antes = embed_api.USO[m]; t = time.time()
        E = embed_api.embed_docs(m, textos, [c['doc'] for c in sub])
        seg, tok = time.time() - t, embed_api.USO[m] - antes
        print(f'{nombre}: {E.shape} {seg:.0f}s {tok:,} tokens', flush=True)
        if args.prueba: print(f'  extrapolado a {len(ch)} fragmentos: ~{tok * len(ch) / len(sub):,.0f} tokens, ~{seg * len(ch) / len(sub) / 60:.1f} min'); continue
        np.save(f, E); json.dump(ids, open(f.replace('.npy', '.ids.json'), 'w'))
        uso[nombre] = tok; json.dump(uso, open(uso_f, 'w'), indent=1)
    fq = B + f'_raw/emb/q__{m}.npz'
    prev = dict(np.load(fq, allow_pickle=True)) if os.path.exists(fq) else None
    if args.prueba: continue
    ya = set(prev['textos'].tolist()) if prev is not None else set()
    nuevas = [c for c in consultas if c not in ya]
    if nuevas:
        Q = embed_api.embed_queries(m, nuevas)
        textos_q = (prev['textos'].tolist() if prev is not None else []) + nuevas
        M = np.vstack([prev['emb'], Q]) if prev is not None else Q
        np.savez(fq, textos=np.array(textos_q, dtype=object), emb=M)
        print(f'consultas {m}: +{len(nuevas)}', flush=True)
json.dump(uso, open(uso_f, 'w'), indent=1)
