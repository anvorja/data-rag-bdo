"""Calcula y cachea embeddings de los fragmentos. Uso: python embed.py <modelo> <modo_chunk> <con_contexto 0|1>
Guarda _raw/emb/<modelo>__<modo>__ctx<0|1>.npy (no versionado). Para e5 antepone «passage: »."""
import json, os, sys, time, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from chunking import chunk_corpus

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) + '/'
modelo, modo, ctx = sys.argv[1], sys.argv[2], sys.argv[3] == '1'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
ch = chunk_corpus(rows, modo)
os.makedirs(B + '_raw/emb', exist_ok=True)
nombre = f"{modelo.split('/')[-1]}__{modo}__ctx{int(ctx)}"
from sentence_transformers import SentenceTransformer
m = SentenceTransformer(modelo, device='cpu'); m.max_seq_length = 384
pref = 'passage: ' if 'e5' in modelo else ''
textos = [pref + ((c['ctx'] + '\n') if ctx else '') + c['texto'] for c in ch]
t = time.time()
e = m.encode(textos, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
np.save(B + f'_raw/emb/{nombre}.npy', e.astype('float32'))
json.dump([c['cid'] for c in ch], open(B + f'_raw/emb/{nombre}.ids.json', 'w'))
print(nombre, len(ch), round(time.time() - t), 's', e.shape)
