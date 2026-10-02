"""Fase 2 · paso 1: selecciona bloques de conocimiento para generar preguntas del golden set.

Divide los documentos indexables en bloques (secciones o ~1.500 caracteres), puntúa su utilidad
(cifras, requisitos, plazos, beneficios, pasos) y elige una muestra estratificada por (segmento, tipo_doc).
Salida: rag-bocc/golden/fuentes/bloques.json (versionado: los pares lo referencian por id de bloque) y _raw/golden_bloques_leer.txt.
"""
import json, os, random, re, collections, unicodedata

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
R = B + '_raw/'
random.seed(7)
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
cand = [r for r in rows if r['indexar'] and r['texto'] and not ('ocr' in r['flags'] and r['tipo_doc'] not in ('instructivo_canales',))]

QUOTA = {  # (segmento, tipo_doc) -> n bloques  (None = cualquier segmento)
    ('personas', 'producto_pagina'): 55, ('empresas', 'producto_pagina'): 35, (None, 'guia_de_uso'): 12, (None, 'terminos_condiciones'): 12,
    (None, 'tarifas_tasas'): 8, (None, 'faq_ayuda'): 8, (None, 'seguro_brochure_clausulado'): 12, (None, 'instructivo_canales'): 20,
    (None, 'educacion_financiera'): 10, (None, 'legal_normativa'): 8, (None, 'institucional'): 6, (None, 'empleo_cultura'): 3,
    (None, 'reglamento_politica'): 8, (None, 'contrato_formato'): 6, (None, 'estado_financiero'): 10, (None, 'informe_gestion_sostenibilidad'): 8,
    (None, 'informacion_relevante'): 4, (None, 'asamblea_accionistas'): 4, (None, 'estudio_economico'): 6, (None, 'tributario'): 4, (None, 'calificacion'): 3,
}
KW = re.compile(r'(?i)\b(requisito|plazo|cuota|tasa|comisi[oó]n|horario|beneficio|costo|tarifa|l[ií]mite|monto|desde|hasta|m[ií]nimo|m[aá]ximo|vigencia|paso|c[oó]mo|qui[eé]n|cu[aá]ndo|d[oó]nde|cobertura|exclusi[oó]n|pol[ií]tica|derecho|deber)\b')


def bloques(r):
    t = r['texto']
    parts = re.split(r'(?m)^(?=#{1,4} )|(?=<!-- página \d+ -->)', t)
    out, cur = [], ''
    for p in parts:
        if len(cur) + len(p) <= 1700: cur += p
        else:
            if cur.strip(): out.append(cur)
            cur = p
    if cur.strip(): out.append(cur)
    res = []
    for b in out:
        for i in range(0, len(b), 2600):  # trocear bloques enormes
            s = b[i:i + 2600].strip()
            if len(s) >= 350: res.append(s)
    return res


def score(b):
    digits = len(re.findall(r'\d', b))
    words = len(re.findall(r'\w+', b))
    if words < 40: return 0
    alpha = sum(c.isalpha() for c in b) / max(1, len(b))
    if alpha < 0.55 and digits < 40: return 0   # tablas de relleno / numeraciones
    if re.search(r'(?i)cookies|aceptar todas|pol[ií]tica de privacidad del sitio', b[:300]): return 0
    if re.search(r'(?i)selecciona (una|un) |acepto la ley de protecci[oó]n|nombres y apellidos|n[uú]mero de celular|te puede interesar', b): return 0   # formularios y carruseles
    return len(KW.findall(b)) * 2 + min(digits, 40) / 5 + min(words, 250) / 50


por_grupo = collections.defaultdict(list)
for r in cand:
    for i, b in enumerate(bloques(r)):
        s = score(b)
        if s > 3: por_grupo[(r['segmento'], r['tipo_doc'])].append((s, r['id'], i, b))

sel = []
usados_doc = collections.Counter()
for (seg, td), n in QUOTA.items():
    pool = []
    for (s2, t2), items in por_grupo.items():
        if t2 == td and (seg is None or s2 == seg): pool += items
    random.shuffle(pool)
    pool.sort(key=lambda x: -x[0] + random.random() * 4)   # puntaje con ruido: variedad
    tomados = 0
    for s, did, i, b in pool:
        if tomados >= n: break
        if usados_doc[did] >= (3 if td in ('guia_de_uso', 'estado_financiero', 'informe_gestion_sostenibilidad') else 2): continue
        sel.append(dict(doc=did, i=i, tipo_doc=td, texto=b)); usados_doc[did] += 1; tomados += 1
by = {r['id']: r for r in rows}
random.shuffle(sel)
for k, x in enumerate(sel, 1):
    x['bid'] = f'B{k:03d}'
    r = by[x['doc']]
    x['segmento'], x['area'], x['titulo'], x['estado'] = r['segmento'], r['area'], r['titulo'], r['estado_vigencia']
os.makedirs(OUT + 'golden/fuentes', exist_ok=True)
json.dump(sel, open(OUT + 'golden/fuentes/bloques.json', 'w'), ensure_ascii=False)
with open(R + 'golden_bloques_leer.txt', 'w') as f:
    for x in sel:
        f.write(f"\n=== {x['bid']} | doc {x['doc']} | {x['segmento']}/{x['area']}/{x['tipo_doc']} | {x['estado']} | {x['titulo'][:60]}\n{x['texto'][:1500]}\n")
print(len(sel), collections.Counter(x['tipo_doc'] for x in sel).most_common(8), len({x['doc'] for x in sel}), 'docs distintos')
