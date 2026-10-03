"""Fase 3b · verificador de suficiencia: ¿se puede saber, antes de generar, que la documentación no responde la pregunta?
Compara con la línea base de la fase 3a (señales de recuperación, AUROC 0,83: 11_fase3a_abstencion.py).
  1. Puntaje del reranker Voyage rerank-3 (top-1 y media del top-3) sobre el híbrido + vigencia blanda → AUROC y umbrales. Cuesta una llamada por consulta (se guarda en caché).
  2. (opcional) --llm deepseek|openai: un LLM juzga con los mejores fragmentos. Requiere la clave en el entorno (ver fase3b/suficiencia.py y .env.example).
Positivos = sin respuesta (sin fuentes y acción abstenerse/escalar); negativos = respondibles y sus variantes. Calibra SOLO con `dev`.
Uso: set -a; . ./.env; set +a; python pipeline/24_suficiencia.py [--llm deepseek] [--topk 20] [--k-llm 4]
Salida: rag-bocc/evaluacion/fase3b/suficiencia-dev.json; caché en _raw/suficiencia/ (no versionada)."""
import argparse, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a')); sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3b'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from evaluar import cargar_golden
from vigencia import doc_ok_blanda
import almacen, embed_api, suficiencia

ap = argparse.ArgumentParser(); ap.add_argument('--llm', choices=['deepseek', 'openai']); ap.add_argument('--topk', type=int, default=20); ap.add_argument('--k-llm', type=int, default=4)
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(line) for line in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
dev = cargar_golden(B, 'dev')
ch = chunk_corpus(rows, 'estructural')

datos = []                                    # (consulta, sin_respuesta, tipo)
for q in dev:
    if q['tipo'] == 'ambigua': continue       # la acción correcta es aclarar
    sin = (not q['fuentes']) and q['accion_esperada'] in ('abstenerse', 'escalar')
    if not sin and not q['fuentes']: continue
    datos.append((q['pregunta'], sin, q['tipo']))
    if q['fuentes']:
        datos += [(v, False, q['tipo'] + '_variante') for v in q.get('variantes', [])]
consultas = sorted({d[0] for d in datos})
print(len(datos), 'casos ·', sum(d[1] for d in datos), 'sin respuesta ·', len(consultas), 'consultas distintas', flush=True)

os.makedirs(B + '_raw/suficiencia', exist_ok=True)
f_cache = B + '_raw/suficiencia/rerank3-dev.json'
cache = json.load(open(f_cache)) if os.path.exists(f_cache) else {}
falta = [q for q in consultas if q not in cache]
if falta:
    from sentence_transformers import SentenceTransformer
    bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch])
    mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
    Q = dict(zip(falta, mod.encode(['query: ' + q for q in falta], normalize_embeddings=True, batch_size=64)))
    E = almacen.cargar(B, 'e5-small', 'estructural', 1, ch)
    cl = embed_api._clientes()['voyage']

    def una(q):
        s = E @ Q[q]; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]
        den = [(int(i), float(s[i])) for i in top]
        cand = [i for i, _ in rrf([bm1.search(q, 200), den], top=200) if doc_ok_blanda(est[ch[i]['doc']], q)][:args.topk]
        r = embed_api._reintentar(lambda: cl.rerank(q, [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i in cand], model='rerank-3', truncation=True))
        return q, sorted(((cand[x.index], float(x.relevance_score)) for x in r.results), key=lambda z: -z[1]), r.total_tokens
    tok = 0; t = time.time()
    with ThreadPoolExecutor(4) as ex:
        for n, (q, v, k) in enumerate(ex.map(una, falta), 1):
            cache[q] = v; tok += k
            if n % 100 == 0: print(f'  {n}/{len(falta)}', flush=True)
    json.dump(cache, open(f_cache, 'w'))
    uso_f = B + '_raw/emb/api/uso.json'; uso = json.load(open(uso_f)) if os.path.exists(uso_f) else {}
    uso['suficiencia__rerank-3'] = uso.get('suficiencia__rerank-3', 0) + tok; json.dump(uso, open(uso_f, 'w'), indent=1)
    print(f'{len(falta)} consultas con rerank-3: {tok:,} tokens, {time.time() - t:.0f}s', flush=True)


def auroc(pos, neg):                           # P(señal_neg > señal_pos): las respondibles deben tener señal más alta
    pos, neg = np.array(pos), np.array(neg)
    return float(((neg[:, None] > pos[None, :]).sum() + 0.5 * (neg[:, None] == pos[None, :]).sum()) / (len(pos) * len(neg)))


def umbrales(ps, ns):
    mejor, cons = None, None
    for t in sorted(set(ps + ns)):
        tpr = sum(x < t for x in ps) / len(ps); fpr = sum(x < t for x in ns) / len(ns)
        bal = (tpr + 1 - fpr) / 2
        if mejor is None or bal > mejor[0]: mejor = (bal, t, tpr, fpr)
        if fpr <= 0.10: cons = (t, tpr, fpr)
    return mejor, cons


sig = {'top1': lambda q: cache[q][0][1] if cache[q] else 0.0,
       'media_top3': lambda q: float(np.mean([s for _, s in cache[q][:3]])) if cache[q] else 0.0}
pos = [d for d in datos if d[1]]; neg = [d for d in datos if not d[1]]
out = dict(n_sin_respuesta=len(pos), n_respondibles=len(neg), linea_base_3a='coseno AUROC 0,83 (abstencion-dev.json)', rerank3={})
for nom, f in sig.items():
    ps, ns = [f(d[0]) for d in pos], [f(d[0]) for d in neg]
    mejor, cons = umbrales(ps, ns)
    out['rerank3'][nom] = dict(auroc=round(auroc(ps, ns), 3), umbral_balanceado=round(mejor[1], 4), abstencion_correcta=round(mejor[2], 3), rechazo_falso=round(mejor[3], 3),
                               umbral_rechazo_falso_10=dict(umbral=round(cons[0], 4), abstencion_correcta=round(cons[1], 3), rechazo_falso=round(cons[2], 3)) if cons else None)
    print(nom, out['rerank3'][nom], flush=True)
# detalle por tipo de pregunta sin respuesta con el umbral conservador de top1
u = out['rerank3']['top1']['umbral_rechazo_falso_10']
if u:
    det = {}
    for q, sin, tipo in pos: det.setdefault(tipo, []).append(sig['top1'](q) < u['umbral'])
    out['rerank3']['detalle_por_tipo_top1_conservador'] = {t: dict(n=len(v), abstencion_correcta=round(sum(v) / len(v), 3)) for t, v in det.items()}
    print('por tipo:', out['rerank3']['detalle_por_tipo_top1_conservador'])

if args.llm:
    f_llm = B + f'_raw/suficiencia/llm-{args.llm}-dev.json'
    cl_llm = suficiencia.cliente(args.llm)
    cl_cache = json.load(open(f_llm)) if os.path.exists(f_llm) else {}

    def juzgar(q):
        if q in cl_cache: return q, cl_cache[q]
        textos = [ch[i]['ctx'] + '\n' + ch[i]['texto'] for i, _ in cache[q][:args.k_llm]]
        ok, motivo = suficiencia.por_llm(q, textos, args.llm, _cl=cl_llm)
        return q, [ok, motivo]
    with ThreadPoolExecutor(4) as ex:
        for q, v in ex.map(juzgar, consultas): cl_cache[q] = v
    json.dump(cl_cache, open(f_llm, 'w'), ensure_ascii=False)
    ab = [not cl_cache[d[0]][0] for d in pos]; rf = [not cl_cache[d[0]][0] for d in neg]
    out['llm_' + args.llm] = dict(k_fragmentos=args.k_llm, abstencion_correcta=round(sum(ab) / len(ab), 3), rechazo_falso=round(sum(rf) / len(rf), 3))
    # combinación: abstenerse si CUALQUIERA de los dos lo pide / solo si ambos
    t = u['umbral'] if u else 0.0
    for nombre, f in (('cualquiera', any), ('ambos', all)):
        ab2 = [f([sig['top1'](d[0]) < t, not cl_cache[d[0]][0]]) for d in pos]; rf2 = [f([sig['top1'](d[0]) < t, not cl_cache[d[0]][0]]) for d in neg]
        out[f'combinado_{nombre}'] = dict(abstencion_correcta=round(sum(ab2) / len(ab2), 3), rechazo_falso=round(sum(rf2) / len(rf2), 3))
    print({k: v for k, v in out.items() if k.startswith(('llm_', 'combinado'))})
os.makedirs(B + 'rag-bocc/evaluacion/fase3b', exist_ok=True)
json.dump(out, open(B + 'rag-bocc/evaluacion/fase3b/suficiencia-dev.json', 'w'), ensure_ascii=False, indent=1)
