import json, re, os, shutil, collections, csv, random, unicodedata
from urllib.parse import urlparse

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
HOY = '2026-10-01'

def slugify(s, n=60):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return (s[:n].strip('-')) or 'doc'
def yq(x): return json.dumps(x, ensure_ascii=False)

# ---- indexar por defecto ----
for r in rows:
    mot = []
    fl = r['flags']
    if 'duplicado_exacto' in fl: mot.append('duplicado_exacto')
    if 'casi_duplicado' in fl and (r.get('similitud') or 0) >= 0.95: mot.append('casi_duplicado')
    if 'sin_texto' in fl or 'muy_corto' in fl or r['tipo_doc'] == 'externo_sin_contenido': mot.append('sin_contenido_util')
    if r['idioma'] == 'en': mot.append('ingles')
    r['indexar'] = not mot; r['motivo_no_indexar'] = mot

# ---- decisiones de vigencia validadas por una persona (rag-bocc/vigencia/decisiones.jsonl); si un id aparece varias veces manda la última ----
dec = {}
if os.path.exists(OUT + 'vigencia/decisiones.jsonl'):
    for l in open(OUT + 'vigencia/decisiones.jsonl'):
        x = json.loads(l); dec[x['id']] = x
for r in rows:
    x = dec.get(r['id'])
    if not x: continue
    r['estado_vigencia'] = x['estado']; r['vigente_desde'] = x.get('vigente_desde'); r['vigente_hasta'] = x.get('vigente_hasta'); r['vigencia_validada'] = True
    if x.get('accion') == 'no_indexar': r['indexar'] = False; r['motivo_no_indexar'] = list(r['motivo_no_indexar']) + ['contenido_sensible']

# ---- títulos públicos legibles (pipeline/23_titulos_publicos.py; los manuales de rag-bocc/titulos/manuales.json mandan) ----
tp = json.load(open(OUT + 'titulos/titulos_publicos.json')) if os.path.exists(OUT + 'titulos/titulos_publicos.json') else {}
for r in rows:
    if r['id'] in tp: r['titulo_publico'] = tp[r['id']]['titulo']

# ---- reorganizar arbol: documentos/<segmento>/<area>/NNN_slug.md ----
shutil.rmtree(OUT + 'documentos', ignore_errors=True)
for r in rows:
    folder = OUT + f"documentos/{r['segmento']}/{r['area']}"
    os.makedirs(folder, exist_ok=True)
    base = r['titulo'] if r['tipo_contenido'].startswith('pagina') else (urlparse(r['url']).path.split('/')[-1] if not re.fullmatch(r'[0-9a-f\-]{36}', urlparse(r['url']).path.split('/')[-1]) else r['titulo'])
    fn = f"{r['id']}_{slugify(re.sub(r'\.(pdf|docx?|xlsx?|xlsm)$', '', base, flags=re.I))}.md"
    r['archivo'] = f"documentos/{r['segmento']}/{r['area']}/{fn}"
    fm = ['---', f"id: {r['id']}", f"url: {yq(r['url'])}", f"titulo: {yq(r['titulo'])}"]
    if r.get('titulo_original'): fm.append(f"titulo_original: {yq(r['titulo_original'])}")
    if r.get('descripcion'): fm.append(f"descripcion: {yq(r['descripcion'])}")
    fm += [f"tipo_doc: {r['tipo_doc']}", f"area: {r['area']}", f"segmento: {r['segmento']}", f"idioma: {r['idioma']}",
           f"estado_vigencia: {r['estado_vigencia']}", f"anio_documento: {r['anio_documento'] if r['anio_documento'] else 'null'}"]
    for k in ('periodo_fin', 'vigente_desde', 'vigente_hasta'):
        fm.append(f"{k}: {r[k] if r[k] else 'null'}")
    fm += [f"clasificacion_acceso: {r['clasificacion_acceso']}", f"tipo_contenido: {yq(r['tipo_contenido'])}", f"fuente: {yq(r['fuente'])}",
           'etiquetas_origen:'] + [f"  - {yq(' > '.join(e))}" for e in r['etiquetas_origen']]
    fm += [f"fecha_extraccion: {r['fecha_extraccion']}", f"caracteres: {len(r['texto'])}", f"paginas: {r['paginas'] if r['paginas'] else 'null'}",
           f"hash_contenido: {r['hash_contenido'] or 'null'}", f"lote: {yq(r.get('lote', 'lote1'))}"]
    if r['duplicado_de']: fm.append(f"duplicado_de: {r['duplicado_de']}")
    if r['casi_duplicado_de']: fm += [f"casi_duplicado_de: {r['casi_duplicado_de']}", f"similitud: {r['similitud']}"]
    if r.get('titulo_publico'): fm.append(f"titulo_publico: {yq(r['titulo_publico'])}")
    if r.get('vigencia_validada'): fm.append('vigencia_validada: true')
    if r.get('version_de'): fm.append(f"version_de: {r['version_de']}")
    fm.append(f"indexar: {str(r['indexar']).lower()}")
    if r['motivo_no_indexar']: fm.append('motivo_no_indexar: [' + ', '.join(r['motivo_no_indexar']) + ']')
    fm.append('flags: [' + ', '.join(r['flags']) + ']')
    if r.get('nota'): fm.append(f"nota: {yq(r['nota'])}")
    fm.append('---')
    if r['duplicado_de']: body = f"# {r['titulo']}\n\n_Contenido idéntico al documento {r['duplicado_de']}; no se repite._"
    elif r['texto']: body = f"# {r['titulo']}\n\n" + r['texto']
    else: body = f"# {r['titulo']}\n\n_Sin contenido extraído: {r.get('nota') or 'sin texto'}_"
    open(OUT + r['archivo'], 'w').write('\n'.join(fm) + '\n\n' + body + '\n')

with open(OUT + 'corpus.jsonl', 'w') as jl:
    for r in rows: jl.write(json.dumps(r, ensure_ascii=False) + '\n')
idx = []
for r in rows:
    idx.append({k: r.get(k) for k in ('id', 'url', 'titulo', 'tipo_contenido', 'fuente', 'archivo', 'nota', 'tipo_doc', 'area', 'segmento', 'idioma', 'estado_vigencia', 'anio_documento',
                                         'periodo_fin', 'vigente_desde', 'vigente_hasta', 'paginas', 'chars_por_pagina', 'imgs_grandes', 'duplicado_de', 'casi_duplicado_de', 'similitud', 'flags', 'lote', 'indexar', 'motivo_no_indexar', 'vigencia_validada', 'version_de', 'titulo_publico')}
               | {'caracteres': len(r['texto']), 'etiquetas_origen': r['etiquetas_origen']})
json.dump(idx, open(OUT + 'indice.json', 'w'), ensure_ascii=False, indent=1)

# ---- auditoria ----
os.makedirs(OUT + 'auditoria', exist_ok=True)
cols = ['indexar', 'id', 'segmento', 'area', 'tipo_doc', 'tipo_contenido', 'idioma', 'estado_vigencia', 'anio_documento', 'periodo_fin', 'vigente_hasta', 'paginas', 'caracteres', 'chars_por_pagina', 'imgs_grandes', 'flags', 'titulo', 'url']
with open(OUT + 'auditoria/auditoria.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(cols)
    for r in idx:
        w.writerow([(';'.join(r[c]) if c == 'flags' else r.get(c, '')) if c != 'caracteres' else r['caracteres'] for c in cols])
nd = json.load(open(B + '_raw/f1_neardups.json'))
with open(OUT + 'auditoria/casi-duplicados.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['id_a', 'id_b', 'similitud', 'titulo_a', 'titulo_b'])
    ti = {r['id']: r['titulo'] for r in rows}
    for a, b, j in sorted(nd, key=lambda x: -x[2]): w.writerow([a, b, j, ti[a][:70], ti[b][:70]])

# muestra estratificada (~10%) para revision humana
random.seed(42)
cand = [r for r in idx if not r['duplicado_de'] and r['caracteres'] > 0]
groups = collections.defaultdict(list)
for r in cand: groups[(r['segmento'], r['tipo_doc'])].append(r)
muestra = []
for k, g in groups.items():
    n = max(1, round(len(g) * 0.10)); muestra += random.sample(g, min(n, len(g)))
flagged = [r for r in cand if set(r['flags']) & {'mojibake', 'tablas_numericas', 'poco_texto_por_pagina', 'titulo_dudoso', 'sin_fecha'}]
ids = {r['id'] for r in muestra}
for r in random.sample(flagged, min(30, len(flagged))):
    if r['id'] not in ids: muestra.append(r); ids.add(r['id'])
muestra.sort(key=lambda r: (r['segmento'], r['tipo_doc'], r['id']))
L = ['# Muestra de revisión humana (≈10 % estratificada + 30 con alertas)', '',
     f'{len(muestra)} documentos. Para cada uno, abrir el `.md` y el original (URL) y responder: **A** ¿el texto coincide con el original? · **B** ¿las tablas conservan filas/columnas y encabezados? · **C** ¿faltan secciones (acordeones, pestañas, anexos)? · **D** ¿hay cifras o pasos solo en imágenes? · **E** ¿etiquetas (`tipo_doc`, `area`, `segmento`) y vigencia correctas? · **F** ¿título correcto?', '',
     '| ✓ | id | segmento | tipo_doc | área | páginas | alertas | título | archivo |', '|---|---|---|---|---|---|---|---|---|']
for r in muestra:
    L.append(f"| ☐ | {r['id']} | {r['segmento']} | {r['tipo_doc']} | {r['area']} | {r['paginas'] or ''} | {', '.join(r['flags'])} | {r['titulo'][:50].replace('|', '/')} | `{r['archivo']}` |")
open(OUT + 'auditoria/muestra-revision.md', 'w').write('\n'.join(L) + '\n')

# reporte
def cnt(f): return collections.Counter(f(r) for r in idx)
fl = collections.Counter(x for r in idx for x in r['flags'])
rep = ['# Auditoría automática del corpus (Fase 1) — 2026-10-01', '',
       f'Documentos: **{len(idx)}** · con texto propio: **{sum(1 for r in idx if r["caracteres"] and not r["duplicado_de"])}** · duplicados exactos: {sum(1 for r in idx if r["duplicado_de"])} · casi-duplicados (Jaccard ≥ 0,8): {sum(1 for r in idx if r["casi_duplicado_de"])} · sin texto: {fl["sin_texto"]}', '',
       '## Distribución', '', '| segmento | docs |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cnt(lambda r: r['segmento']).most_common()] + ['', '| tipo_doc | docs |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cnt(lambda r: r['tipo_doc']).most_common()] + ['', '| área | docs |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cnt(lambda r: r['area']).most_common()] + ['', '| idioma | docs |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cnt(lambda r: r['idioma']).most_common()] + ['', '| estado_vigencia | docs |', '|---|---|'] + [f'| {k} | {v} |' for k, v in cnt(lambda r: r['estado_vigencia']).most_common()]
rep += ['', '## Alertas', '', '| alerta | docs | qué significa / acción |', '|---|---|---|']
expl = {'candidato_vlm': 'PDF con ≥3 imágenes grandes y poco texto por página → candidatos a descripción con VLM / OCR reforzado (sección 3 de la guía v2)',
        'duplicado_exacto': 'mismo texto que otro documento; se conserva solo el primero',
        'ingles': 'documento en inglés; excluir del índice por defecto del asesor en español (o enlazar con su equivalente)',
        'tablas_numericas': 'muchas líneas con columnas numéricas (estados financieros): validar tablas con un parser de layout',
        'sin_fecha': 'tarifa/T&C/guía/informe sin año detectable → no se puede gobernar su vigencia',
        'poco_texto_por_pagina': '< 300 caracteres por página → probable escaneado o capturas; revisar OCR',
        'casi_duplicado': 'versión casi idéntica de otro documento (Jaccard ≥ 0,8); decidir cuál se indexa',
        'ocr': 'texto obtenido por OCR (puede tener errores en cifras y nombres)',
        'titulo_dudoso': 'el título HTML no coincide con la ruta (p. ej. título copiado de otra página)',
        'tablas_markdown': 'página con tablas serializadas a Markdown',
        'sin_texto': 'sin contenido extraíble (redes, cotizadores JS…)',
        'mojibake': 'caracteres rotos (codificación) → revisar',
        'muy_largo': '> 1,5 M de caracteres; requiere chunking jerárquico por capítulo',
        'vigencia_vencida': 'el propio documento declara una vigencia ya terminada',
        'muy_corto': '< 200 caracteres'}
for k, v in fl.most_common(): rep.append(f'| {k} | {v} | {expl.get(k, "")} |')
ni = [r for r in idx if r['indexar']]
rep += ['', f'**Indexables por defecto: {len(ni)} de {len(idx)}** (excluidos: duplicados, casi-duplicados ≥ 0,95, sin contenido útil, inglés). Motivos: ' + ', '.join(f'{k}={v}' for k, v in collections.Counter(m for r in idx for m in r['motivo_no_indexar']).most_common()) + '.']
rep += ['', '## Hallazgos con impacto en el diseño', '']
ven = [r for r in idx if r['estado_vigencia'] == 'vencido']
for r in ven: rep.append(f"- **Vigencia vencida:** id {r['id']} «{r['titulo']}» declara vigencia hasta {r['vigente_hasta']} (hoy {HOY}). Las **tasas se publican por mes**: un PDF de tasas queda obsoleto a fin de mes → las tasas deben venir de una fuente estructurada, no del índice documental.")
sf = [r for r in idx if 'sin_fecha' in r['flags']]
rep.append(f"- **Sin fecha detectable:** {len(sf)} documentos de tarifas/T&C/guías/informes (lista en `auditoria.csv`, filtrar alerta `sin_fecha`).")
rep += ['', '## Archivos', '', '- `auditoria.csv`: una fila por documento con métricas y alertas.', '- `casi-duplicados.csv`: pares con similitud.', '- `muestra-revision.md`: lista para la revisión humana del ~10 %.']
open(OUT + 'auditoria/reporte.md', 'w').write('\n'.join(rep) + '\n')
print('ok', len(muestra), dict(fl))
