"""Fase 2 · paso 2: ingiere los pares pregunta-respuesta-fuente y construye el golden set versionado.

Entrada : rag-bocc/golden/fuentes/qa_*.jsonl + bloques.json  (una línea por par; ver formato abajo)
Salida  : rag-bocc/golden/golden-v0.jsonl, rag-bocc/golden/rechazados.jsonl, rag-bocc/golden/README.md

Formato de entrada (clave corta):
  b      id del bloque (B012) -> doc se toma de _raw/golden_bloques.json            [una fuente]
  docs   lista de ids de documento (multi-salto / comparativas)                     [varias fuentes]
  q, v   pregunta y variantes coloquiales        a  respuesta de referencia
  t      tipo (factual, numerica_tabla, multi_salto, comparativa, temporal, ambigua, sin_respuesta,
         premisa_falsa, fuera_alcance, datos_personales, adversarial, regulatoria)
  cita   cadena literal (o lista, una por doc) que debe aparecer EXACTAMENTE en el documento
  prod   producto/tema                     ausente  términos que NO deben aparecer en el corpus (sin_respuesta)
  vig    nota de vigencia (opcional)       dif      dificultad 1-3 (opcional)
  accion accion esperada: responder | aclarar | abstenerse | escalar | corregir_premisa (por defecto según el tipo)
  seg    segmento cuando no hay documentos (personas | empresas | transversal)

Filtros automáticos: la cita existe en el documento; sin preguntas duplicadas (Jaccard >= 0,8); términos «ausentes» realmente ausentes.
Partición dev/test por DOCUMENTO (30 % de los documentos, estratificado por segmento y tipo_doc): la pregunta es `test` si alguna de sus fuentes es un documento de prueba.
"""
import glob, hashlib, json, os, re, collections, unicodedata

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
R = B + '_raw/'
rows = {r['id']: r for r in (json.loads(l) for l in open(OUT + 'corpus.jsonl'))}
bloques = {x['bid']: x for x in json.load(open(OUT + 'golden/fuentes/bloques.json'))}
FECHA = '2026-10-01'


def nws(s): return re.sub(r'\s+', ' ', s).strip()
def nacc(s): return unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode()


def localizar(doc_text, cita):
    """Devuelve (pagina|None) si la cita aparece (tolerando saltos de línea), o False."""
    palabras = cita.split()
    if not palabras: return False
    rx = r'\s+'.join(re.escape(w) for w in palabras)
    m = re.search(rx, doc_text)
    if not m: return False
    marcas = [(mm.start(), int(mm.group(1))) for mm in re.finditer(r'<!-- página (\d+) -->', doc_text[:m.start()])]
    return marcas[-1][1] if marcas else None


def toks(s): return set(re.findall(r'\w+', nacc(s)))


entradas = []
for f in sorted(glob.glob(OUT + 'golden/fuentes/qa_*.jsonl')):
    for n, l in enumerate(open(f, encoding='utf8'), 1):
        l = l.strip()
        if l and not l.startswith('#'):
            try: e = json.loads(l); e['_src'] = f'{os.path.basename(f)}:{n}'; entradas.append(e)
            except Exception as ex: print('JSON inválido', f, n, ex)

aceptados, rechazados, vistos = [], [], []
corpus_norm = None
for e in entradas:
    motivo = None
    docs = [bloques[e['b']]['doc']] if 'b' in e else list(e.get('docs', []))
    citas = e.get('cita', [])
    if isinstance(citas, str): citas = [citas]
    fuentes = []
    if e['t'] in ('sin_respuesta', 'premisa_falsa', 'fuera_alcance', 'datos_personales', 'adversarial', 'ambigua') and not docs:
        pass
    else:
        if not docs: motivo = 'sin documentos'
        elif len(docs) > 1 and len(citas) not in (len(docs), 1): motivo = 'número de citas distinto del de documentos'
        else:
            if len(docs) == 1 and len(citas) > 1: docs = docs * len(citas)   # varias citas del mismo documento
            for k, d in enumerate(docs):
                r = rows.get(d)
                if not r: motivo = f'doc {d} no existe'; break
                if not r['indexar']: motivo = f'doc {d} no indexable'; break
                c = citas[k] if len(citas) == len(docs) else citas[0]
                pg = localizar(r['texto'], c)
                if pg is False: motivo = f'cita no encontrada en doc {d}: «{c[:60]}»'; break
                fuentes.append(dict(doc_id=d, url=r['url'], titulo=r['titulo'], pagina=pg, cita_literal=c))
    if not motivo and e['t'] in ('sin_respuesta', 'premisa_falsa') and e.get('ausente'):
        if corpus_norm is None: corpus_norm = nacc(' '.join(r['texto'] for r in rows.values() if r['indexar']))
        for term in e['ausente']:
            if nacc(term) in corpus_norm: motivo = f'el término «{term}» SÍ aparece en el corpus'; break
    if not motivo:
        tq = toks(e['q'])
        for tv, qv in vistos:
            if len(tq & tv) / max(1, len(tq | tv)) >= 0.8: motivo = f'pregunta casi duplicada de: {qv[:50]}'; break
    if motivo: rechazados.append(dict(motivo=motivo, **{k: v for k, v in e.items() if k != '_src'}, origen_linea=e['_src'])); continue
    vistos.append((toks(e['q']), e['q']))
    accion = e.get('accion') or ('abstenerse' if (e['t'] in ('sin_respuesta', 'fuera_alcance', 'datos_personales', 'adversarial') and not fuentes) else 'aclarar' if e['t'] == 'ambigua' else 'corregir_premisa' if e['t'] == 'premisa_falsa' else 'responder')
    seg = rows[docs[0]]['segmento'] if docs else e.get('seg', 'transversal')
    prod = e.get('prod') or (rows[docs[0]]['area'] if docs else 'transversal')
    aceptados.append(dict(
        nivel='plata', pregunta=e['q'], variantes=e.get('v', []), tipo=e['t'], segmento=seg, producto=prod,
        respuesta_referencia=e['a'], accion_esperada=accion, debe_abstenerse=accion in ('abstenerse', 'escalar'),
        fuentes=fuentes, fecha_referencia=FECHA, vigencia_nota=e.get('vig'), dificultad=e.get('dif', 1),
        origen='sintetico_claude', validado_por=None, tipos_doc=sorted({rows[d]['tipo_doc'] for d in docs}), notas=e.get('notas', '')))

# ---- partición por documento (30 % test), estratificada por (segmento, tipo_doc) ----
usados = sorted({f['doc_id'] for q in aceptados for f in q['fuentes']})
grupos = collections.defaultdict(list)
for d in usados: grupos[(rows[d]['segmento'], rows[d]['tipo_doc'])].append(d)
test_docs = set()
for g, ds in grupos.items():
    ds.sort(key=lambda d: hashlib.md5(d.encode()).hexdigest())
    n = max(1, round(len(ds) * 0.3)) if len(ds) > 1 else 0
    test_docs |= set(ds[:n])
for q in aceptados:
    ds = [f['doc_id'] for f in q['fuentes']]
    if ds: q['split'] = 'test' if any(d in test_docs for d in ds) else 'dev'
    else: q['split'] = 'test' if int(hashlib.md5(q['pregunta'].encode()).hexdigest(), 16) % 10 < 3 else 'dev'
aceptados.sort(key=lambda q: (q['segmento'], q['tipo'], q['pregunta']))
for q in aceptados: q['id'] = 'G-' + hashlib.sha1(nacc(nws(q['pregunta'])).encode()).hexdigest()[:8]   # id estable: depende solo de la pregunta
assert len({q['id'] for q in aceptados}) == len(aceptados), 'ids duplicados'
aceptados = [dict(id=q['id'], **{k: v for k, v in q.items() if k != 'id'}) for q in aceptados]

os.makedirs(OUT + 'golden', exist_ok=True)
with open(OUT + 'golden/golden-v0.jsonl', 'w') as f:
    for q in aceptados: f.write(json.dumps(q, ensure_ascii=False) + '\n')
with open(OUT + 'golden/rechazados.jsonl', 'w') as f:
    for q in rechazados: f.write(json.dumps(q, ensure_ascii=False) + '\n')
json.dump(sorted(test_docs), open(OUT + 'golden/docs-test.json', 'w'))

c = collections.Counter
print(f'entradas {len(entradas)} · aceptadas {len(aceptados)} · rechazadas {len(rechazados)}')
print('split', c(q['split'] for q in aceptados))
print('tipo', c(q['tipo'] for q in aceptados).most_common())
print('segmento', c(q['segmento'] for q in aceptados))
print('test por tipo', c(q['tipo'] for q in aceptados if q['split'] == 'test').most_common())
print('docs usados', len(usados), 'docs test', len(test_docs))
for r in rechazados[:40]: print('RECHAZADA', r['origen_linea'], '|', r['motivo'])
