import json, re, os, base64, hashlib, subprocess, html as H, unicodedata, zipfile, shutil, glob
from urllib.parse import urlparse, unquote
from lxml import html as LH

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
R = B + '_raw/'
OUT = B + 'rag-bocc/'
FECHA = '2026-10-01'
shutil.rmtree(OUT, ignore_errors=True)
os.makedirs(OUT + 'documentos')

urls = [l.strip() for l in open(B + 'enlaces-rag-bocc-limpio.txt') if l.strip()]
tags = json.load(open(B + 'enlaces-por-etiquetas.json'))

# ---- URL -> rutas de etiquetas
u2tags = {}
inferred = set()
def walk(n, p):
    for k, v in n.get('subetiquetas', {}).items():
        walk(v, p + [k])
    for u in n.get('enlaces', []):
        if isinstance(u, dict):
            if u.get('etiqueta_inferida'): inferred.add(u['url'])
            u = u['url']
        u2tags.setdefault(u, []).append(p)
walk(tags['etiquetas'], [])

# ---- fuentes
res = json.load(open(R + 'paginas_bocc.json'))
by_url = {r['url']: r for r in res}
spa = {u: json.load(open(R + f'spa_{i}.json')) for i, u in [(104, 'https://www.bancodeoccidente.com.co/libre-inversion-autogestion-flujo-corto/'),
       (113, 'https://www.bancodeoccidente.com.co/occiauto/autogestionado/vehiculo'),
       (119, 'https://www.bancodeoccidente.com.co/vivienda-autogestionado/'),
       (189, 'https://www.bancodeoccidente.com.co/creatucuentaahorros/')]}
pp = json.load(open(R + 'portalpublico.json'))
pp_by_url = {x['url']: (i, x) for i, x in enumerate(pp)}
barb = {'https://www.occidentalbankbarbados.com' + x['url']: x for x in json.load(open(R + 'ext_barbados.json'))}
fp = json.load(open(R + 'ext_fp.json'))

def run(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, **k)

def clean(t):
    t = t.replace('\r', '')
    t = re.sub(r'[ \t]+\n', '\n', t)
    t = re.sub(r'\n{4,}', '\n\n\n', t)
    return t.strip()

def pdf_text(path):
    o = path + '.txt'
    subprocess.run(['pdftotext', '-layout', path, o], stderr=subprocess.DEVNULL, timeout=300)
    t = open(o, errors='ignore').read()
    pages = t.split('\f')
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    if len([p for p in pages if p.strip()]) == 0 or len(t.strip()) < 400:
        ocr = ocr_pdf(path)
        if len(ocr.strip()) > len(t.strip()):
            return clean(ocr), 'pdf (OCR)'
    if len(pages) > 1:
        t = ''.join(f'\n\n<!-- página {i+1} -->\n\n{p}' for i, p in enumerate(pages))
    return clean(t), 'pdf'

def ocr_pdf(path, maxp=40):
    d = path + '_ocr'
    os.makedirs(d, exist_ok=True)
    subprocess.run(['pdftoppm', '-r', '170', '-l', str(maxp), '-png', path, d + '/p'], stderr=subprocess.DEVNULL)
    out = []
    for i, f in enumerate(sorted(glob.glob(d + '/p*.png'))):
        r = run(['tesseract', f, '-', '-l', 'spa'])
        out.append(f'\n\n<!-- página {i+1} -->\n\n' + r.stdout)
    return ''.join(out)

def ocr_img(path):
    return run(['tesseract', path, '-', '-l', 'spa']).stdout

def docx_text(p):
    z = zipfile.ZipFile(p); x = z.read('word/document.xml').decode('utf8')
    x = re.sub(r'</w:p>', '\n', x); x = re.sub(r'<w:tab/>', '\t', x); x = re.sub(r'<[^>]+>', '', x)
    return clean(H.unescape(x))

def xlsx_text(p):
    z = zipfile.ZipFile(p); names = z.namelist(); ss = []
    if 'xl/sharedStrings.xml' in names:
        s = z.read('xl/sharedStrings.xml').decode('utf8')
        for si in re.findall(r'<si>(.*?)</si>', s, re.S):
            ss.append(H.unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>', si, re.S))))
    wb = z.read('xl/workbook.xml').decode('utf8'); sheets = re.findall(r'<sheet [^>]*name="([^"]*)"', wb)
    out = []
    sh = sorted([n for n in names if re.match(r'xl/worksheets/sheet\d+\.xml', n)], key=lambda n: int(re.findall(r'\d+', n)[0]))
    for idx, n in enumerate(sh):
        out.append(f'## Hoja: {H.unescape(sheets[idx]) if idx < len(sheets) else idx}')
        x = z.read(n).decode('utf8')
        for row in re.findall(r'<row[^>]*>(.*?)</row>', x, re.S):
            cells = []
            for m in re.finditer(r'<c ([^>]*?)(?:/>|>(.*?)</c>)', row, re.S):
                at, body = m.group(1), m.group(2) or ''
                v = re.search(r'<v>(.*?)</v>', body, re.S)
                if 't="s"' in at and v: cells.append(ss[int(v.group(1))])
                elif 't="inlineStr"' in at: cells.append(H.unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>', body, re.S))))
                elif v: cells.append(H.unescape(v.group(1)))
            if any(c.strip() for c in cells): out.append(' | '.join(cells))
    return clean('\n'.join(out))

def html_plain(raw):
    t = LH.fromstring(raw)
    for e in t.xpath('//script|//style|//noscript|//svg|//head'):
        e.drop_tree()
    root = (t.xpath('//main') or [t])[0]
    txt = root.text_content()
    txt = re.sub(r'[ \t\xa0]+', ' ', txt)
    txt = re.sub(r'\n\s*\n+', '\n', txt)
    return clean(txt)

def title_html(raw):
    try:
        t = LH.fromstring(raw); x = t.xpath('//title/text()')
        return ' '.join(x[0].split()) if x else ''
    except Exception:
        return ''

def slug_title(u):
    p = unquote(urlparse(u).path.rstrip('/'))
    s = p.split('/')[-1]
    if re.search(r'\.(pdf|docx|xlsx|xlsm)$', s, re.I) is None and re.fullmatch(r'[0-9a-f\-]{36}', s):
        s = p.split('/')[-2]
    s = re.sub(r'\.(pdf|docx|xlsx|xlsm|png)$', '', s, flags=re.I).replace('+', ' ').replace('-', ' ').replace('_', ' ')
    return s.strip() or urlparse(u).netloc

def slugify(s, n=60):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return (s[:n].strip('-')) or 'doc'

# mapas de binarios de bocc por URL -> i
def binpath(u):
    r = by_url.get(u)
    return (R + f"bin/{r['i']:03d}.dat", r) if r and r.get('binary') else (None, None)

SKIP = {  # externos sin contenido util para el RAG
    'api.whatsapp.com': 'Enlace de contacto por WhatsApp (no tiene contenido propio; el número es 573186714836).',
    'www.instagram.com': 'Red social: requiere sesión/JS, sin contenido extraíble.',
    'www.youtube.com': 'Red social: sin contenido textual extraíble.',
    'www.facebook.com': 'Red social: requiere sesión, sin contenido extraíble.',
    'www.linkedin.com': 'Bolsa de empleo con búsqueda dinámica (ofertas cambiantes); requiere sesión.',
    'www.segurosadl.com': 'Cotizador web (aplicación JS), sin contenido textual estático.',
    'www.avalpaycenter.com': 'Portal de pagos (aplicación JS), sin contenido textual estático.',
    'www.suraenlinea.com': 'Cotizador web (aplicación JS), sin contenido textual estático.',
    'www.magneto365.com': 'Bolsa de empleo con ofertas dinámicas; no es información institucional estable.',
    'www.elempleo.com': 'Bolsa de empleo con ofertas dinámicas; solo términos y condiciones del portal.',
}

docs = []
fallos = []
for idx, u in enumerate(urls, 1):
    dom = urlparse(u).netloc
    texto = ''; tipo = ''; titulo = ''; desc = ''; nota = ''; enlaces = []
    try:
        if u in spa:
            d = spa[u]; texto = d['text']
            texto = re.sub(r'^Cargando, por favor espera un momento\n', '', texto)
            titulo = d['title']; tipo = 'pagina_web (renderizada con JS)'
            enlaces = sorted(set(d.get('links', [])))
        elif u in by_url and not by_url[u].get('binary'):
            r = by_url[u]; texto = r['text']; titulo = r['title']; desc = r['description']; tipo = 'pagina_web'
            enlaces = r['links']
        elif u in by_url and by_url[u].get('binary'):
            p, r = binpath(u); ct = r['ct']
            if 'pdf' in ct: texto, tipo = pdf_text(p)
            elif 'wordprocessing' in ct: texto, tipo = docx_text(p), 'word'
            elif 'spreadsheet' in ct or 'ms-excel' in ct: texto, tipo = xlsx_text(p), 'excel'
            elif 'png' in ct: texto, tipo = clean(ocr_img(p)), 'imagen (OCR)'
            titulo = slug_title(u)
        elif u in pp_by_url:
            i, x = pp_by_url[u]; p = R + f'bin/pp{i:02d}.dat'
            raw = open(p, 'rb').read()
            if raw[:4] == b'%PDF':
                texto, tipo = pdf_text(p)
            else:
                texto = html_plain(raw); tipo = 'pagina_web'; titulo = title_html(raw)
            titulo = titulo or slug_title(u)
        elif u in barb:
            texto = barb[u]['text']; titulo = barb[u]['title']; tipo = 'pagina_web (externa)'
        elif 'funcionpublica' in u:
            k = re.search(r'i=(\d+)', u).group(1)
            p = R + f'ext/fp{k}.pdf'; open(p, 'wb').write(base64.b64decode(fp[k]['b64']))
            texto, tipo = pdf_text(p); titulo = f'Norma Función Pública (gestor normativo) i={k}'
        elif 'mastercard.com' in u:
            d = json.load(open(R + 'ext_232.json')); texto = d['text']; titulo = d['title']; tipo = 'pagina_web (externa)'
        elif 'latampass.latam.com/co/es/puntos' in u:
            d = json.load(open(R + 'ext_101.json')); texto = d['text']; titulo = d['title']; tipo = 'pagina_web (externa)'
        else:
            # externos descargados con curl
            f = R + f'ext/{idx-1:03d}.dat'
            raw = open(f, 'rb').read() if os.path.exists(f) else b''
            if dom in SKIP:
                nota = SKIP[dom]
            elif raw[:4] == b'%PDF':
                texto, tipo = pdf_text(f); titulo = slug_title(u)
            elif raw[:2] == b'PK':
                texto, tipo = xlsx_text(f), 'excel'; titulo = slug_title(u)
            elif raw:
                texto = html_plain(raw); titulo = title_html(raw); tipo = 'pagina_web (externa)'
                if len(texto) < 300: nota = 'Página dinámica (JS) con muy poco texto estático.'
            else:
                nota = 'No se pudo descargar.'
    except Exception as e:
        nota = f'Error al procesar: {e}'
    texto = (texto or '').strip()
    if not texto and not nota:
        nota = 'Sin texto extraíble.'
    if 'Z7_' in texto[:400] and '${title}' in texto:
        texto = ''; nota = 'Página con plantilla Liferay sin contenido (el enlace redirige al portal de la línea ética).'
    titulo = titulo or slug_title(u)
    rutas = u2tags.get(u, [])
    primary = rutas[0] if rutas else ['sin-etiqueta']
    docs.append(dict(id=idx, url=u, dominio=dom, titulo=titulo, descripcion=desc, tipo=tipo, rutas=rutas, primary=primary, texto=texto, nota=nota, enlaces=enlaces))

# duplicados por contenido
seen = {}
for d in docs:
    if len(d['texto']) < 200:
        continue
    h = hashlib.sha1(re.sub(r'\s+', ' ', d['texto']).encode()).hexdigest()
    if h in seen:
        d['duplicado_de'] = seen[h]
    else:
        seen[h] = d['id']

# escribir
def yq(s):
    return json.dumps(s, ensure_ascii=False)

index = []
with open(OUT + 'corpus.jsonl', 'w') as jl:
    for d in docs:
        folder = OUT + 'documentos/' + '/'.join(slugify(x, 40) for x in d['primary'])
        os.makedirs(folder, exist_ok=True)
        fn = f"{d['id']:03d}_{slugify(d['titulo'] if d['tipo'].startswith('pagina') else slug_title(d['url']))}.md"
        path = folder + '/' + fn
        etiquetas_txt = [' > '.join(r) for r in d['rutas']]
        fm = ['---', f"id: {d['id']:03d}", f"url: {yq(d['url'])}", f"titulo: {yq(d['titulo'])}"]
        if d['descripcion']: fm.append(f"descripcion: {yq(d['descripcion'])}")
        fm += [f"tipo_contenido: {yq(d['tipo'] or 'sin_contenido')}", f"fuente: {yq(d['dominio'])}",
               'etiquetas:'] + [f'  - {yq(e)}' for e in etiquetas_txt]
        if d['url'] in inferred: fm.append('etiqueta_inferida: true')
        fm += [f"fecha_extraccion: {FECHA}", f"caracteres: {len(d['texto'])}"]
        if d.get('duplicado_de'): fm.append(f"duplicado_de: {d['duplicado_de']:03d}")
        if d['nota']: fm.append(f"nota: {yq(d['nota'])}")
        fm.append('---')
        if d.get('duplicado_de'):
            body = f"# {d['titulo']}\n\n_Contenido idéntico al documento {d['duplicado_de']:03d}; no se repite para no duplicar el corpus._"
            d['texto_corpus'] = ''
        elif d['texto']:
            body = f"# {d['titulo']}\n\n" + d['texto']
            d['texto_corpus'] = d['texto']
        else:
            body = f"# {d['titulo']}\n\n_Sin contenido extraído: {d['nota']}_"
            d['texto_corpus'] = ''
        open(path, 'w').write('\n'.join(fm) + '\n\n' + body + '\n')
        d['archivo'] = os.path.relpath(path, OUT)
        jl.write(json.dumps(dict(id=f"{d['id']:03d}", url=d['url'], titulo=d['titulo'], descripcion=d['descripcion'], tipo_contenido=d['tipo'] or 'sin_contenido',
                                 fuente=d['dominio'], etiquetas=d['rutas'], fecha_extraccion=FECHA, archivo=d['archivo'], nota=d['nota'],
                                 duplicado_de=(f"{d['duplicado_de']:03d}" if d.get('duplicado_de') else None), texto=d['texto_corpus']), ensure_ascii=False) + '\n')
        index.append({k: d[k] for k in ('id', 'url', 'titulo', 'tipo', 'dominio', 'archivo', 'nota')} | {'etiquetas': d['rutas'], 'caracteres': len(d['texto']), 'duplicado_de': d.get('duplicado_de')})

json.dump(index, open(OUT + 'indice.json', 'w'), ensure_ascii=False, indent=1)
print('docs', len(docs), 'con texto', sum(1 for d in docs if d['texto']), 'sin texto', sum(1 for d in docs if not d['texto']),
      'dups', sum(1 for d in docs if d.get('duplicado_de')))
for d in docs:
    if not d['texto']:
        print('SIN', d['id'], d['url'][:90], '|', d['nota'])
