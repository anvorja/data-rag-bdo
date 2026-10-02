"""Fase 2 · paso 3: línea base léxica (BM25) sobre el golden set, solo como prueba de cordura.

No es el RAG final: sirve para (a) detectar pares imposibles o mal formulados, (b) medir la dificultad del set,
(c) tener un punto de comparación para la fase 3 (híbrido + reranker). Mide, por pregunta con fuente:
  - recall@k a nivel de DOCUMENTO (¿algún chunk del top-k pertenece a un documento fuente?)
  - recall@k a nivel de CITA (¿algún chunk del top-k contiene la cita literal, con ≥ 80 % de sus palabras?)
  - MRR de cita.
Salida: rag-bocc/golden/baseline-bm25.json
"""
import json, math, os, re, collections, unicodedata

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
gold = [json.loads(l) for l in open(OUT + 'golden/golden-v0.jsonl')]
STOP = set('de la el en y los las que del con por para una un se su al es lo como mas sus este esta son entre a o u e sin sobre ser tu te mi me si no ni ya hay'.split())


def nacc(s): return unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode()
def toks(s): return [t for t in re.findall(r'\w+', nacc(s)) if len(t) > 1 and t not in STOP]


def chunks(t, size=1100, step=900):
    t = re.sub(r'<!-- página \d+ -->', ' ', t)
    t = re.sub(r'[ \t]+', ' ', t)
    out, i = [], 0
    while i < len(t):
        out.append(t[i:i + size]); i += step
    return out


docs, ctext, cdoc = [], [], []
for r in rows:
    if r['indexar'] and r['texto']:
        for c in chunks(r['texto']):
            ctext.append(c); cdoc.append(r['id'])
tf, df, dl = [], collections.Counter(), []
inv = collections.defaultdict(list)
for i, c in enumerate(ctext):
    t = toks(c); dl.append(len(t)); cnt = collections.Counter(t)
    for w, n in cnt.items(): inv[w].append((i, n)); df[w] += 1
N = len(ctext); avg = sum(dl) / N
K1, BB = 1.5, 0.75


def search(q, k=10):
    sc = collections.defaultdict(float)
    for w in set(toks(q)):
        if w not in inv: continue
        idf = math.log(1 + (N - df[w] + 0.5) / (df[w] + 0.5))
        for i, n in inv[w]:
            sc[i] += idf * n * (K1 + 1) / (n + K1 * (1 - BB + BB * dl[i] / avg))
    return sorted(sc, key=lambda i: -sc[i])[:k]


def cubre(chunk, cita):
    ct = set(toks(cita)); 
    return bool(ct) and len(ct & set(toks(chunk))) / len(ct) >= 0.8


res = collections.defaultdict(lambda: collections.Counter())
fallos = []
for q in gold:
    if not q['fuentes']: continue
    queries = [('pregunta', q['pregunta'])] + [('variante', v) for v in q.get('variantes', [])]
    docs_src = {f['doc_id'] for f in q['fuentes']}
    for kind, text in queries:
        top = search(text, 10)
        rd = next((r for r, i in enumerate(top, 1) if cdoc[i] in docs_src), None)
        # cita: todas las citas deben quedar cubiertas dentro del top-k (por separado cada una)
        def rc(f):
            return next((r for r, i in enumerate(top, 1) if cdoc[i] == f['doc_id'] and cubre(ctext[i], f['cita_literal'])), None)
        rcs = [rc(f) for f in q['fuentes']]
        rcita = None if any(x is None for x in rcs) else max(rcs)
        for key in (('todos', kind), (q['tipo'], kind), (q['split'], kind), (q['segmento'], kind)):
            c = res[key]; c['n'] += 1
            for k in (1, 5, 10):
                c[f'doc@{k}'] += rd is not None and rd <= k
                c[f'cita@{k}'] += rcita is not None and rcita <= k
            c['mrr_cita'] += 1 / rcita if rcita else 0
        if kind == 'pregunta' and rcita is None: fallos.append(dict(id=q['id'], tipo=q['tipo'], pregunta=q['pregunta'], docs=sorted(docs_src)))

tabla = {}
for (g, kind), c in sorted(res.items()):
    n = c['n']
    tabla[f'{g}|{kind}'] = {'n': n, **{k: round(c[k] / n, 3) for k in ('doc@1', 'doc@5', 'doc@10', 'cita@1', 'cita@5', 'cita@10')}, 'mrr_cita': round(c['mrr_cita'] / n, 3)}
json.dump(dict(chunks=N, resumen=tabla, sin_cita_en_top10=fallos), open(OUT + 'golden/baseline-bm25.json', 'w'), ensure_ascii=False, indent=1)
print('chunks', N, 'preguntas con fuente', sum(1 for q in gold if q['fuentes']))
for k in ('todos|pregunta', 'todos|variante', 'dev|pregunta', 'test|pregunta'):
    print(k, tabla[k])
for k in sorted(tabla):
    if k.endswith('|pregunta') and k.split('|')[0] not in ('todos', 'dev', 'test'): print(k, tabla[k]['n'], 'cita@10', tabla[k]['cita@10'], 'doc@10', tabla[k]['doc@10'])
print('sin cita en top10:', len(fallos))
