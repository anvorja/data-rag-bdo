"""Fase 3a (paso 3): abstención por umbral de evidencia, calibrada en `dev`.

Pregunta clave: ¿se puede detectar, ANTES de generar, que la documentación no contiene la respuesta?
Señales por consulta (sobre el híbrido con contexto + vigencia): coseno denso del mejor fragmento, cobertura léxica de la consulta en el
top-3 y su combinación. Positivos = preguntas sin respuesta / fuera de alcance / datos personales / adversariales (sin fuentes);
negativos = preguntas respondibles. Se informa AUROC y, con el umbral que maximiza la exactitud balanceada, la tasa de abstención
correcta y la de rechazo falso. Salida: rag-bocc/evaluacion/fase3a/abstencion-dev.json
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, Densa, rrf, toks
from evaluar import cargar_golden
from vigencia import doc_ok

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
est = {r['id']: r['estado_vigencia'] for r in rows}
dev = cargar_golden(B, 'dev')
ch = chunk_corpus(rows, 'estructural')
from sentence_transformers import SentenceTransformer
m = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu'); m._nombre = 'e5'
import almacen
E1 = almacen.cargar(B, 'e5-small', 'estructural', 1, ch)
bm1 = BM25([c['ctx'] + '\n' + c['texto'] for c in ch]); d1 = Densa(E1, m)

def senales(q):
    den = d1.search(q, 200); lex = bm1.search(q, 200)
    fus = [(i, s) for i, s in rrf([lex, den], top=200) if doc_ok(est[ch[i]['doc']], q)][:10]
    top3 = [i for i, _ in fus[:3]]
    qt = set(toks(q))
    cob = len(qt & set(t for i in top3 for t in toks(ch[i]['texto']))) / max(1, len(qt))
    dmax = max((s for i, s in den if doc_ok(est[ch[i]['doc']], q)), default=0.0)
    return dict(coseno=dmax, cobertura=cob)

def auroc(pos, neg):   # P(señal_pos > señal_neg), empates 0,5
    pos, neg = np.array(pos), np.array(neg)
    return float(((pos[:, None] > neg[None, :]).sum() + 0.5 * (pos[:, None] == neg[None, :]).sum()) / (len(pos) * len(neg)))

datos = []
for q in dev:
    if q['tipo'] == 'ambigua': continue            # la acción correcta es aclarar, no abstenerse
    sin = (not q['fuentes']) and q['accion_esperada'] in ('abstenerse', 'escalar')
    if not sin and not q['fuentes']: continue
    s = senales(q['pregunta']); s['sin_respuesta'] = sin; s['tipo'] = q['tipo']; datos.append(s)
for q in dev:                                       # reformulaciones de las respondibles (más realistas)
    if q['fuentes'] and q['tipo'] != 'ambigua':
        for v in q.get('variantes', []):
            s = senales(v); s['sin_respuesta'] = False; s['tipo'] = q['tipo'] + '_variante'; datos.append(s)
pos = [d for d in datos if d['sin_respuesta']]; neg = [d for d in datos if not d['sin_respuesta']]
for d in datos: d['combinada'] = d['coseno'] + d['cobertura']
out = dict(n_sin_respuesta=len(pos), n_respondibles=len(neg), senales={})
print('sin respuesta:', len(pos), '| respondibles (incl. variantes):', len(neg))
for nom in ('coseno', 'cobertura', 'combinada'):
    ps, ns = [d[nom] for d in pos], [d[nom] for d in neg]
    au = auroc(ns, ps)       # las respondibles deberían tener señal más alta
    mejor = None
    for t in sorted(set(ps + ns)):
        tpr = sum(x < t for x in ps) / len(ps)          # abstención correcta
        fpr = sum(x < t for x in ns) / len(ns)          # rechazo falso
        bal = (tpr + (1 - fpr)) / 2
        if mejor is None or bal > mejor[0]: mejor = (bal, t, tpr, fpr)
    # umbral conservador: rechazo falso <= 10 %
    cons = None
    for t in sorted(set(ps + ns)):
        tpr = sum(x < t for x in ps) / len(ps); fpr = sum(x < t for x in ns) / len(ns)
        if fpr <= 0.10: cons = (t, tpr, fpr)
    out['senales'][nom] = dict(auroc=round(au, 3), umbral_balanceado=round(mejor[1], 4), abstencion_correcta=round(mejor[2], 3), rechazo_falso=round(mejor[3], 3),
                               umbral_rechazo_falso_10=(round(cons[0], 4), round(cons[1], 3), round(cons[2], 3)) if cons else None)
    print(nom, out['senales'][nom])
os.makedirs(B + 'rag-bocc/evaluacion/fase3a', exist_ok=True)
json.dump(out, open(B + 'rag-bocc/evaluacion/fase3a/abstencion-dev.json', 'w'), ensure_ascii=False, indent=1)
