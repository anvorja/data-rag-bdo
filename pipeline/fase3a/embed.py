"""Calcula embeddings LOCALES (sentence-transformers) de forma incremental: solo codifica los fragmentos nuevos o modificados.
Uso: python embed.py <modelo> [--chunking estructural] [--ctx 1 0] [--dispositivo auto|cpu|cuda]
Modelos: e5-small (384 d), e5-large (1024 d), bge-m3 (1024 d). Guarda en _raw/emb/<modelo>/ (ver almacen.py). Para e5 antepone «passage: ».
Con GPU (p. ej. Colab T4) hay un cuaderno equivalente: pipeline/colab/embeddings_colab.ipynb."""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from chunking import chunk_corpus
import almacen

HF = {'e5-small': 'intfloat/multilingual-e5-small', 'e5-large': 'intfloat/multilingual-e5-large', 'bge-m3': 'BAAI/bge-m3'}
ap = argparse.ArgumentParser(); ap.add_argument('modelo'); ap.add_argument('--chunking', default='estructural'); ap.add_argument('--ctx', nargs='+', type=int, default=[1, 0])
ap.add_argument('--dispositivo', default='auto'); args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) + '/'
modelo = almacen.nombre(args.modelo)
ch = chunk_corpus([json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')], args.chunking)
m = None
for ctx in args.ctx:
    E, faltan = almacen.alinear(B, modelo, args.chunking, ctx, ch)
    print(f'{modelo} ctx{ctx}: {len(faltan)} de {len(ch)} fragmentos por codificar', flush=True)
    if not faltan: continue
    if m is None:
        from sentence_transformers import SentenceTransformer
        import torch
        disp = ('cuda' if torch.cuda.is_available() else 'cpu') if args.dispositivo == 'auto' else args.dispositivo
        m = SentenceTransformer(HF[modelo], device=disp); m.max_seq_length = 384
    pref = 'passage: ' if modelo.startswith('e5') else ''
    t = time.time()
    nuevos = m.encode([pref + almacen.texto_indexado(ch[k], ctx) for k in faltan], batch_size=64, normalize_embeddings=True, show_progress_bar=False)
    if E is None: E = np.zeros((len(ch), nuevos.shape[1]), dtype='float32')
    E[faltan] = nuevos
    almacen.guardar(B, modelo, args.chunking, ctx, ch, E, dict(recalculados=len(faltan), segundos=round(time.time() - t), dispositivo=str(m.device)))
    print(f'  guardado ({round(time.time() - t)} s, {m.device})', flush=True)
