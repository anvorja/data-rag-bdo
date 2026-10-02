import json, re, os, hashlib, subprocess, html as H, unicodedata, zipfile, glob, shutil
from urllib.parse import urlparse, unquote

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
R = B + '_raw/'
OUT = B + 'rag-bocc/'
FECHA = '2026-10-01'

exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'helpers.py')).read())

old_index = json.load(open(OUT + 'indice.json'))
next_id = max(x['id'] for x in old_index) + 1
old_hashes = {}
for l in open(OUT + 'corpus.jsonl'):
    d = json.loads(l)
    if d['texto']:
        old_hashes[hashlib.sha1(re.sub(r'\s+', ' ', d['texto']).encode()).hexdigest()] = d['id']

new_docs = []

# ---------- paginas nuevas (empresas + resto) ----------
old = json.load(open(R + 'paginas_bocc.json'))
def key(u): return urlparse(u).path.rstrip('/').lower()
oldk = {key(r['url']) for r in old}
emp = json.load(open(R + 'crawl2_empresas.json')); glob_ = json.load(open(R + 'crawl2_global.json'))
pages = {}
for src in (emp, glob_):
    for p in src:
        if p.get('status', 200) != 200: continue
        pages.setdefault(key(p.get('final') or p['url']), p)

def tags_for_path(k):
    parts = [x for x in k.split('/') if x]
    if k.startswith('/en/'): parts = parts[1:]
    if parts[:2] == ['web', 'empresas']:
        return ['EMPRESAS'] + ([parts[2].replace('-', ' ')] if len(parts) > 2 else [])
    if parts and parts[0] in ('seguros', 'seguro-de-vida-vivienda', 'asistencia-vehicular', 'asistencia-de-viajes-internacionales', 'asistencias-en-viajes-nacionales'): return ['PERSONAS', 'seguros']
    if parts and parts[0] == 'tarjetas-credito': return ['PERSONAS', 'tarjetas de crédito']
    if parts and parts[0] == 'creditos': return ['PERSONAS', 'créditos']
    if parts and parts[0] == 'cuentas': return ['PERSONAS', 'cuentas']
    if parts and parts[0] in ('trabaja-con-nosotros', 'home-trabaja-con-nosotros', 'nuestros-beneficios', 'talento-joven'): return ['PERSONAS', 'quienes somos', 'trabaja con nosotros']
    if parts and parts[0] in ('proyectos-de-vivienda', 'proyectos-vivienda-form', 'bienes-para-la-venta'): return ['PERSONAS', 'créditos', 'vivienda']
    return ['PERSONAS', 'otros']

for k, p in sorted(pages.items()):
    if k in oldk or k.startswith('/en/') and k[3:] in pages: continue
    if k in ('/inicio', '/prueba-html', '/formulario-autorizacion', '/referidos1', '/solicitar-credito', '/tienda-rigo', '/winback'):
        pass
    txt = p['text'].strip()
    new_docs.append(dict(url=p.get('final') or p['url'], titulo=p['title'] or k, desc=p.get('description', ''), tipo='pagina_web', texto=txt,
                         rutas=[tags_for_path(k)], enlaces=p.get('links', []), lote='crawl2-paginas', nota='' if len(txt) > 300 else 'Página con poco texto estático.'))

# ---------- documentos descargados ----------
sel = json.load(open(R + 'sel_docs.json'))
selmap = {o['i']: o for o in sel}
def cat_doc(g, name, url):
    n = name.lower()
    if g == 'inversionistas' or g == 'sostenibilidad' and False:
        if re.search(r'eeff|estado|financier|balance|certificacion-eeff|certificados-financieros', n): sub = 'estados financieros'
        elif re.search(r'informe-peri|informe-trim|periodic|quarterly|-ir-|^ir-|informacion-relevante|info-relevante|inforel', n): sub = 'informes periódicos e información relevante'
        elif re.search(r'asamblea|aga|pdu|convocatoria|citacion|orden-del-dia|decisiones|proyecto-distrib|utilidades|poder|accionistas|aviso|exdividendo|dividendo', n): sub = 'asamblea y accionistas'
        elif re.search(r'calificacion|fitch|brc|standard|profile|rating', n): sub = 'calificaciones'
        elif re.search(r'reglamento|estatuto|codigo|gobierno|junta|comite|politica|manual|conflicto|marco|etic|encuesta|revisor|principio|procedimiento|nombramiento|designaci', n): sub = 'gobierno corporativo'
        elif re.search(r'sarlaft|aml|patriot|wolfsberg|fatca|fw8|certificacion', n): sub = 'cumplimiento y certificaciones'
        elif re.search(r'bono|prospecto|oferta|subasta|macrot|adend|demanda|emision|offering|tenedores', n): sub = 'emisiones de bonos'
        else: sub = 'otros'
        return ['INVERSIONISTAS', sub]
    if g == 'sostenibilidad': return ['SOSTENIBILIDAD']
    if g == 'empresas':
        if re.search(r'tarifa|tasa', n): sub = 'tarifas y tasas'
        elif re.search(r'pulso|occimpacto|radar|radiografia|tes-|informe-sectorial|termometro|canonazos|economic|eco-|asesoria|alcorriente|sector-publico|pib|tigre|jugamos|rounds|descertificacion|halloween', n): sub = 'estudios económicos'
        elif re.search(r'calendario-tributario|manual|foro', n): sub = 'tributario'
        elif re.search(r'instructivo|occired|pse|login|app', n): sub = 'instructivos y canales'
        else: sub = 'guías, contratos y formatos'
        return ['EMPRESAS', sub]
    return ['PERSONAS', 'documentos y formatos']

magic_ext = lambda b: 'pdf' if b[:4] == b'%PDF' else 'zip' if b[:2] == b'PK' else 'jpg' if b[:3] == b'\xff\xd8\xff' else 'png' if b[:4] == b'\x89PNG' else 'ole' if b[:4] == b'\xd0\xcf\x11\xe0' else 'html' if b.lstrip()[:5].lower() in (b'<!doc', b'<html') else 'bin'
skipped = []
import signal
def _to(sig, frm): raise TimeoutError('tiempo excedido')
def extract(f):
    signal.signal(signal.SIGALRM, _to); signal.alarm(420)
    i = int(os.path.basename(f)[:4])
    raw = open(f, 'rb').read(); ext = magic_ext(raw)
    try:
        if ext == 'pdf': t, tp = pdf_text(f); return i, ext, t, tp, None
        if ext == 'zip':
            nm = zipfile.ZipFile(f).namelist()
            if 'word/document.xml' in nm: return i, ext, docx_text(f), 'word', None
            if any(n.startswith('xl/') for n in nm): return i, ext, xlsx_text(f), 'excel', None
            return i, ext, '', '', 'zip no soportado'
        if ext in ('jpg', 'png'): return i, ext, clean(ocr_img(f)), 'imagen (OCR)', None
        if ext == 'html': return i, ext, '', '', 'respuesta HTML/404'
        return i, ext, '', '', f'formato {ext} no soportado'
    except BaseException as e:
        return i, ext, '', '', f'error: {e}'
    finally:
        signal.alarm(0)

import multiprocessing as mp
files = sorted(glob.glob(R + 'dl/*.dat'))
with mp.Pool(6) as pool:
    results = pool.map(extract, files, chunksize=4)
EXCLUIR = {318: 'excluido: lista de NIT y nombres (posibles datos personales)', 374: 'excluido del texto: listado masivo de corresponsales; debe ser herramienta/API de consulta'}
for i, ext, texto, tipo, err in results:
    o = selmap[i]
    if i in EXCLUIR: skipped.append((i, 'https://www.bancodeoccidente.com.co' + o['u'], EXCLUIR[i])); continue
    url = 'https://www.bancodeoccidente.com.co' + o['u'] if o['u'].startswith('/') else o['u']
    name = unquote(o['u'].split('?')[0]).split('/')[-1]
    if err: skipped.append((i, url, err)); continue
    texto = texto.strip()
    if o['g'] in ('inversionistas', 'sostenibilidad'):
        yrs = [int(y) for y in re.findall(r'(?<!\d)(20[0-3]\d)(?!\d)', texto[:6000])]
        nm_yrs = [int(y) for y in re.findall(r'(?<!\d)(20[0-3]\d)(?!\d)', name)]
        allyrs = nm_yrs or yrs
        if allyrs and max(allyrs) < 2022:
            skipped.append((i, url, f'fuera de alcance (año máx {max(allyrs)})')); continue
    titulo = re.sub(r'[+_]', ' ', re.sub(r'\.(pdf|docx?|xlsx?|xlsm)$', '', name, flags=re.I)).replace('-', ' ').strip() or f'documento {i}'
    new_docs.append(dict(url=url, titulo=titulo, desc='', tipo=tipo, texto=texto, rutas=[cat_doc(o['g'], name, url)], enlaces=[], lote='crawl2-documentos',
                         nota='' if texto else 'Sin texto extraíble.'))

# ---------- dedupe y escritura ----------
for d in new_docs:
    d['hash'] = hashlib.sha1(re.sub(r'\s+', ' ', d['texto']).encode()).hexdigest() if len(d['texto']) >= 200 else None
seen = dict(old_hashes)
for d in new_docs:
    h = d['hash']
    if h:
        if h in seen: d['dup'] = seen[h]
        else: seen[h] = None  # placeholder, id lo asignamos abajo
# asignar ids
for d in new_docs:
    d['id'] = next_id; next_id += 1
first = {}
for d in new_docs:
    h = d['hash']
    if h and not d.get('dup'):
        first[h] = d['id']
for d in new_docs:
    h = d['hash']
    if h and not d.get('dup') and first.get(h) != d['id']:
        d['dup'] = first[h]
    elif h and isinstance(d.get('dup'), str):
        pass

def yq(s): return json.dumps(s, ensure_ascii=False)
idx_new = []
with open(OUT + 'corpus.jsonl', 'a') as jl:
    for d in new_docs:
        dup = d.get('dup')
        folder = OUT + 'documentos/' + '/'.join(slugify(x, 40) for x in d['rutas'][0])
        os.makedirs(folder, exist_ok=True)
        fn = f"{d['id']:03d}_{slugify(d['titulo'])}.md"
        path = folder + '/' + fn
        dom = urlparse(d['url']).netloc
        fm = ['---', f"id: {d['id']:03d}", f"url: {yq(d['url'])}", f"titulo: {yq(d['titulo'])}"]
        if d['desc']: fm.append(f"descripcion: {yq(d['desc'])}")
        fm += [f"tipo_contenido: {yq(d['tipo'] or 'sin_contenido')}", f"fuente: {yq(dom)}", 'etiquetas:'] + [f"  - {yq(' > '.join(r))}" for r in d['rutas']]
        fm += [f"fecha_extraccion: {FECHA}", f"caracteres: {len(d['texto'])}", f"lote: {yq(d['lote'])}"]
        if dup: fm.append(f"duplicado_de: {dup if isinstance(dup, str) else format(dup, '03d')}")
        if d['nota']: fm.append(f"nota: {yq(d['nota'])}")
        fm.append('---')
        if dup: body = f"# {d['titulo']}\n\n_Contenido idéntico al documento {dup if isinstance(dup, str) else format(dup, '03d')}; no se repite._"; texto_c = ''
        elif d['texto']: body = f"# {d['titulo']}\n\n" + d['texto']; texto_c = d['texto']
        else: body = f"# {d['titulo']}\n\n_Sin contenido extraído: {d['nota']}_"; texto_c = ''
        open(path, 'w').write('\n'.join(fm) + '\n\n' + body + '\n')
        arch = os.path.relpath(path, OUT)
        dups = (dup if isinstance(dup, str) else format(dup, '03d')) if dup else None
        jl.write(json.dumps(dict(id=f"{d['id']:03d}", url=d['url'], titulo=d['titulo'], descripcion=d['desc'], tipo_contenido=d['tipo'] or 'sin_contenido', fuente=dom,
                                 etiquetas=d['rutas'], fecha_extraccion=FECHA, archivo=arch, nota=d['nota'], duplicado_de=dups, lote=d['lote'], texto=texto_c), ensure_ascii=False) + '\n')
        idx_new.append(dict(id=d['id'], url=d['url'], titulo=d['titulo'], tipo=d['tipo'], dominio=dom, archivo=arch, nota=d['nota'], etiquetas=d['rutas'],
                            caracteres=len(d['texto']), duplicado_de=dups, lote=d['lote']))
json.dump(old_index + idx_new, open(OUT + 'indice.json', 'w'), ensure_ascii=False, indent=1)
json.dump([dict(i=i, url=u, motivo=m) for i, u, m in skipped], open(OUT + 'omitidos-lote2.json', 'w'), ensure_ascii=False, indent=1)
import collections
print('nuevos', len(new_docs), collections.Counter(d['lote'] for d in new_docs), 'omitidos', len(skipped))
print(collections.Counter(m.split(' (')[0] for _, _, m in skipped))
print('dups', sum(1 for d in new_docs if d.get('dup')), 'sin texto', sum(1 for d in new_docs if not d['texto']))
