"""Migra los embeddings del formato plano (_raw/emb/<modelo>__<chunking>__ctx<N>.npy) a subcarpetas por modelo y les calcula el hash
del texto codificado, para poder actualizar de forma incremental. Idempotente.
Uso: python 18_organizar_embeddings.py --corpus-origen _raw/corpus.pre-vigencia.jsonl   (corpus con el que se calcularon los vectores)"""
import argparse, glob, json, os, re, shutil, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
import almacen
ap = argparse.ArgumentParser(); ap.add_argument('--corpus-origen', required=True); args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
ch = {m: chunk_corpus([json.loads(l) for l in open(args.corpus_origen)], m) for m in ('estructural',)}
os.makedirs(B + '_raw/emb/api', exist_ok=True)
if os.path.exists(B + '_raw/emb/uso.json'): shutil.move(B + '_raw/emb/uso.json', B + '_raw/emb/api/uso.json')
for f in sorted(glob.glob(B + '_raw/emb/*__*__ctx[01].npy')):
    m = re.match(r'(.+?)__(estructural|fijo)__ctx([01])\.npy', os.path.basename(f))
    if not m: continue
    modelo, chunking, ctx = almacen.nombre(m.group(1)), m.group(2), int(m.group(3))
    ids = json.load(open(f.replace('.npy', '.ids.json')))
    assert ids == [c['cid'] for c in ch[chunking]], f'{f}: los ids no coinciden con el corpus de origen'
    os.makedirs(almacen.carpeta(B, modelo), exist_ok=True); dst = almacen.base(B, modelo, chunking, ctx)
    shutil.move(f, dst + '.npy'); shutil.move(f.replace('.npy', '.ids.json'), dst + '.ids.json')
    json.dump([almacen.hash_texto(almacen.texto_indexado(c, ctx)) for c in ch[chunking]], open(dst + '.hashes.json', 'w'))
    mf = almacen.carpeta(B, modelo) + 'manifiesto.json'; mm = json.load(open(mf)) if os.path.exists(mf) else dict(modelo=modelo)
    mm.setdefault('calculos', {})[f'{chunking}__ctx{ctx}'] = dict(filas=len(ids), origen='migrado'); json.dump(mm, open(mf, 'w'), indent=1)
    print('migrado', modelo, chunking, ctx)
for f in sorted(glob.glob(B + '_raw/emb/q__*.npz')):
    modelo = almacen.nombre(os.path.basename(f)[3:-4]); os.makedirs(almacen.carpeta(B, modelo), exist_ok=True)
    shutil.move(f, almacen.carpeta(B, modelo) + 'consultas.npz'); print('consultas', modelo)
