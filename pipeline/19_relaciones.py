"""Tabla de relaciones página → documentos (y página → página) a partir de los enlaces Markdown que conservó el rastreo.

Salida: rag-bocc/relaciones.jsonl   una fila por (origen, destino, texto del enlace)
        rag-bocc/relaciones-sin-destino.csv   enlaces a documentos que no están en el corpus (para decidir si se descargan)
        rag-bocc/relaciones-resumen.md
Fuentes: (1) enlaces Markdown del texto de cada documento; (2) grafo del rastreo (_raw/docs_universe.json: en qué páginas se encontró cada documento, incluso cuando el
        botón no quedó como enlace en el texto). Campo `fuente`: markdown | rastreo | markdown+rastreo.
Campos: origen_id, destino_id (versión actual), destino_url, texto_enlace, tipo, coincidencia, versiones_destino, estado_destino
Tipos:  ofrece_documento (enlace de contenido a un PDF/Word/Excel)  ·  enlace_pagina (a otra página del banco)  ·
        navegacion (menús y pies de página: el destino lo enlazan muchas páginas)  ·  externo (otro sitio)  ·  fuera_del_corpus (documento sin copia)
La URL que se muestra al cliente sale SIEMPRE de esta tabla o del corpus; el modelo nunca la escribe.
"""
import collections, csv, json, os, re, unicodedata
from urllib.parse import unquote, urlparse

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
UMBRAL_NAV = 25     # un destino enlazado desde tantas páginas distintas se considera navegación (menú, pie de página)
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]


def slug(s):
    s = unicodedata.normalize('NFKD', unquote(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')
def norm(u):
    p = urlparse(unquote(u.strip())); host = p.netloc.lower(); path = p.path.rstrip('/')
    return f'https://{host}{path}'.lower()
def clave_doc(u):
    p = urlparse(unquote(u)); parts = [x for x in p.path.split('/') if x]
    if 'documents' not in parts: return None
    rest = parts[parts.index('documents') + 1:]
    if rest and rest[0] == 'd' and len(rest) >= 3: return slug(rest[2])
    if len(rest) >= 3:                                   # /documents/<grupo>/<carpeta>/<archivo>[/<uuid>]
        archivo = rest[2]; return slug(re.sub(r'\.(pdf|docx?|xlsx?|xlsm|pptx?)$', '', archivo, flags=re.I))
    return None
def es_doc(u): return bool(re.search(r'/documents/|\.(pdf|docx?|xlsx?|xlsm|pptx?)(\?|$)', u, re.I))


por_url, por_clave = collections.defaultdict(list), collections.defaultdict(list)
for r in rows:
    por_url[norm(r['url'])].append(r['id'])
    k = clave_doc(r['url'])
    if k: por_clave[k].append(r['id'])
by = {r['id']: r for r in rows}


def actual(ids):
    """De varias versiones de la misma URL, la vigente: no histórica y con mayor id."""
    vivos = [i for i in ids if by[i]['estado_vigencia'] != 'historico' and by[i]['indexar']] or [i for i in ids if by[i]['indexar']] or ids
    return max(vivos, key=int)


enlaces = []
for r in rows:
    if r['duplicado_de']: continue
    for m in re.finditer(r'\[([^\]]*)\]\((https?://[^)\s]+)\)', r['texto']):
        enlaces.append((r['id'], re.sub(r'\s+', ' ', m.group(1)).strip()[:120], m.group(2)))
cnt_origenes = collections.defaultdict(set)
for o, t, u in enlaces: cnt_origenes[norm(u)].add(o)

res, sin = [], collections.OrderedDict()
vistos = set()
for o, t, u in enlaces:
    n = norm(u); ids = por_url.get(n); how = 'url'
    if not ids:
        k = clave_doc(u); ids = por_clave.get(k) if k else None; how = 'nombre_de_archivo'
    if ids and all(i == o for i in ids): continue          # enlace a sí mismo
    ids = [i for i in (ids or []) if i != o]
    clave = (o, n, t)
    if clave in vistos: continue
    vistos.add(clave)
    if ids:
        d = actual(ids); tipo = 'navegacion' if len(cnt_origenes[n]) >= UMBRAL_NAV else ('ofrece_documento' if es_doc(u) or by[d]['tipo_contenido'].startswith(('pdf', 'word', 'excel')) else 'enlace_pagina')
        res.append(dict(origen_id=o, origen_url=by[o]['url'], destino_id=d, destino_url=by[d]['url'], texto_enlace=t, tipo=tipo, coincidencia=how, versiones_destino=sorted(ids, key=int), estado_destino=by[d]['estado_vigencia'], fuente='markdown'))
    else:
        host = urlparse(u).netloc.lower(); propio = host.endswith('bancodeoccidente.com.co')
        tipo = ('fuera_del_corpus' if es_doc(u) else 'externo') if propio or es_doc(u) else 'externo'
        res.append(dict(origen_id=o, origen_url=by[o]['url'], destino_id=None, destino_url=u, texto_enlace=t, tipo='navegacion' if len(cnt_origenes[n]) >= UMBRAL_NAV else tipo, coincidencia=None, versiones_destino=[], estado_destino=None, fuente='markdown'))
        if tipo == 'fuera_del_corpus': sin.setdefault(n, [u, t, set()])[2].add(o)

# ---- grafo del rastreo: documento → páginas donde se encontró ----
DU = B + '_raw/docs_universe.json'
if os.path.exists(DU):
    par = {(x['origen_id'], x['destino_id']): x for x in res if x['destino_id']}
    for k, (u, paginas) in json.load(open(DU)).items():
        n = norm(u); ids = por_url.get(n) or (por_clave.get(clave_doc(u)) if clave_doc(u) else None)
        paginas = sorted(set(paginas)); nav = len(paginas) >= UMBRAL_NAV
        if not ids:
            if es_doc(u): sin.setdefault(n, [u, '', set()])[2].update(i for p in paginas for i in (por_url.get(norm('https://www.bancodeoccidente.com.co' + p)) or [])[:1])
            continue
        d = actual(ids)
        for pth in paginas:
            oi = por_url.get(norm('https://www.bancodeoccidente.com.co' + pth))
            if not oi or actual(oi) == d: continue
            o = actual(oi); x = par.get((o, d))
            if x: x['fuente'] = 'markdown+rastreo'; continue
            nuevo = dict(origen_id=o, origen_url=by[o]['url'], destino_id=d, destino_url=by[d]['url'], texto_enlace=by[d]['titulo'][:120], tipo='navegacion' if nav else 'ofrece_documento',
                         coincidencia='url', versiones_destino=sorted(ids, key=int), estado_destino=by[d]['estado_vigencia'], fuente='rastreo')
            res.append(nuevo); par[(o, d)] = nuevo

with open(OUT + 'relaciones.jsonl', 'w') as f:
    for x in res: f.write(json.dumps(x, ensure_ascii=False) + '\n')
with open(OUT + 'relaciones-sin-destino.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['url', 'texto_enlace', 'paginas_origen'])
    for n, (u, t, os_) in sin.items(): w.writerow([u, t, ';'.join(sorted(os_, key=int))])
c = collections.Counter(x['tipo'] for x in res); fc = collections.Counter(x['fuente'] for x in res)
orig = {x['origen_id'] for x in res if x['tipo'] == 'ofrece_documento'}
md = ['# Relaciones página → documentos', '', f'{len(res)} enlaces únicos (origen, destino, texto) desde {len({x["origen_id"] for x in res})} documentos.', '', '| tipo | enlaces |', '|---|---|'] + [f'| {k} | {v} |' for k, v in c.most_common()] + ['', '| fuente | enlaces |', '|---|---|'] + [f'| {k} | {v} |' for k, v in fc.most_common()]
md += ['', f'Páginas/documentos que ofrecen al menos un documento: {len(orig)}. Documentos del banco enlazados pero sin copia en el corpus: {len(sin)} (ver `relaciones-sin-destino.csv`).',
       '', 'Los destinos con varias versiones (URL «viva») apuntan a la versión vigente; todas quedan en `versiones_destino`.', '', f'Un destino enlazado desde ≥ {UMBRAL_NAV} páginas distintas se clasifica como `navegacion` (menús y pies de página).']
open(OUT + 'relaciones-resumen.md', 'w').write('\n'.join(md) + '\n')
print(len(res), dict(c), '| orígenes que ofrecen docs:', len(orig), '| docs sin copia:', len(sin))
