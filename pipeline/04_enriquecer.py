import json, re, os, hashlib, shutil, collections, csv, random, unicodedata, zlib
from urllib.parse import urlparse, unquote

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
R = B + '_raw/'
OUT = B + 'rag-bocc/'
HOY = '2026-10-01'
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
pst = {int(k): v for k, v in json.load(open(R + 'f1_pdfstats.json')).items()}
shutil.copy(OUT + 'corpus.jsonl', R + 'corpus.pre-fase1.jsonl')
by_id = {r['id']: r for r in rows}

MES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6, 'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12,
       'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6, 'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12}
def norm(s):
    return unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode()
def slugify(s, n=60):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return (s[:n].strip('-')) or 'doc'
def eomonth(y, m):
    d = {1: 31, 2: 29 if y % 4 == 0 else 28, 3: 31, 4: 30, 5: 31, 6: 30, 7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31}[m]
    return f'{y:04d}-{m:02d}-{d:02d}'

ES = set('de la el en y los las que del con por para una un se su al es lo como más sus este esta son entre'.split())
EN = set('the of and to in for is on that by with as are this be or from at an its which'.split())
def idioma(t):
    w = re.findall(r"[a-záéíóúñ]+", t[:6000].lower())
    if len(w) < 15: return 'indeterminado'
    e = sum(1 for x in w if x in ES); n = sum(1 for x in w if x in EN)
    if n > e * 1.3: return 'en'
    if e > n * 1.3: return 'es'
    return 'mixto'

# ---------------- clasificacion ----------------
def tipo_doc(r):
    if 'bancodeoccidente' not in r['fuente'] and r['tipo_contenido'] in ('sin_contenido',): return 'externo_sin_contenido'
    u = norm(unquote(urlparse(r['url']).path)); ti = norm(r['titulo']); tx = norm(r['texto'][:600])
    s = u + ' ' + ti
    web = r['tipo_contenido'].startswith('pagina')
    p = urlparse(r['url']).path.lower()
    if web:
        if p.startswith('/b/'): return 'educacion_financiera'
        if '/ayuda' in p or 'preguntas-frecuent' in p or 'corresponsales' in p: return 'faq_ayuda'
        if '/legal-politicas' in p or 'tratamiento-datos' in p: return 'legal_normativa'
        if re.search(r'trabaja|talento-joven|nuestros-beneficios', p): return 'empleo_cultura'
        if 'quienes-somos' in p or 'nuestro-banco' in p or 'transparencia' in p or 'sostenibilidad' in p or 'gestion-sostenible' in p: return 'institucional'
        if 'educacion-financiera' in p: return 'educacion_financiera'
        if re.search(r'occieconomicas|foros', p): return 'estudio_economico'
        return 'producto_pagina'
    if re.search(r'tarifa|tasas[-_ ]|tasas ', s) and 'campana' not in s: return 'tarifas_tasas'
    if re.search(r'instructivo|como[- ]registrarte|perfilamiento|rapport|inscripcion-alertas|configuracion|nuevo-login|multicash', s): return 'instructivo_canales'
    if re.search(r'calendario[- ]tributario|actualizacion[- ]tributaria|foro[s]?[- ]tributario|tributari', s): return 'tributario'
    if re.search(r'pulso-economico|radar-economico|occimpacto|radiografia-economica|tes[- ](?!turismo$)|informe[- ]sectorial|termometro|canonazos|alcorriente|sector-publico|asesoria-127|pib-co|era-de-el-tigre|nos-la-jugamos|rounds-monetarios|descertificacion|halloween', s): return 'estudio_economico'
    if re.search(r'guia[- ]de[- ](uso|producto)|guias[- ]de[- ]uso|guiasdeuso|guia[- ]tc|guia[- ]cuenta', s): return 'guia_de_uso'
    if re.search(r'\btyc\b|tyc[-_ ]|terminos[- ]y[- ]condiciones|campana|bases[- ]de[- ]la', s): return 'terminos_condiciones'
    if re.search(r'calificacion|fitch|brc[- ]ratings|standard[- ]%26|profile[-_ ]', s): return 'calificacion'
    if re.search(r'eeff|estado[s]?[- ]financiero|balance[- ]banco|certificacion[- ]estados', s): return 'estado_financiero'
    if re.search(r'informe[- ](de[- ])?gestion|informe[- ]periodico|periodic[- ]year|year[- ]end|informe[- ]bdeo|contenido[- ]gri|tcfd|progress[- ]statement|carta[- ]del[- ]presidente|aseguramiento|verificacion|emisiones[- ]financiadas|lista[- ]de[- ]exclusion|participacion[- ]en[- ]gremios|responsible', s): return 'informe_gestion_sostenibilidad'
    if re.search(r'asamblea|\baga\b|aga-|convocatoria|citacion|orden[- ]del[- ]dia|\bpdu\b|decisiones|proyecto[- ](de[- ])?distribucion|utilidades|exdividendo|dividendo|poder[- ]para', s): return 'asamblea_accionistas'
    if re.search(r'informe[- ]trimestral|trimestral[- ]\d|informacion[- ]relevante|info[- ]relevante|inforel|\bir[- ]|-ir-|medidas[- ]aga|aviso', s): return 'informacion_relevante'
    if re.search(r'prospecto|macrotitulo|subasta|adend|oferta[- ]publica|offering|tenedores|emision|demanda[- ]en[- ]firme|bonos', s): return 'emision_valores'
    if re.search(r'decreto|\bley[- ]|resolucion|circular|habeas|sentencia|reglamentacion|derechos[- ]de[- ]los[- ]consumidores|deberes[- ]de[- ]las[- ]entidades', s): return 'legal_normativa'
    if re.search(r'reglamento|politica|codigo|estatuto|manual|conflicto|lineamiento|directri|marco[- ]de[- ]referencia|principio|procedimiento|declaracion|manifiesto|plan[- ]de|policy|regulation|guidelines|abac|anticorrup|acoso', s): return 'reglamento_politica'
    if re.search(r'contrato|formato|solicitud|pagare|fto[- ]|vinculacion|poder|prenda|acta[- ]de[- ]entrega|cesion|instruccion|oferta[- ]mercantil|plantilla|afiliacion|convenio|cuestionario|certificacion|certificado|rut|camara[- ]de[- ]comercio', s): return 'contrato_formato'
    if re.search(r'clausulado|brochure|bochure|multiasistencia|asistencia|seguro|cuota[- ]protegida|vive[- ]la[- ]vida|pensionados|fuerzas[- ]armadas', s): return 'seguro_brochure_clausulado'
    if re.search(r'organigrama|about[- ]us|estructura[- ]organizacional|presentacion[- ]general|profile|directorio', s): return 'institucional'
    orig = r['etiquetas'][0][0] if r['etiquetas'] and r['etiquetas'][0] else ''
    if re.search(r'boletin|foro|tulio|ley-crecimiento|regimen-cambiario|juan-guillermo|desafios-banca|precios-de-insumos|decenal|sector', s): return 'estudio_economico'
    if orig == 'SOSTENIBILIDAD':
        if re.search(r'plan|policy|politica|annex|anexo|manifest|decal|lista|exclusion|regulation|reglamento', s): return 'reglamento_politica'
        return 'informe_gestion_sostenibilidad'
    if orig == 'INVERSIONISTAS':
        if re.search(r'rac|novedades|anexo|tabla[- ]de[- ]contenido|informe|reporte|presentacion|certificacion|carta', s + ' ' + ti): return 'informacion_relevante'
        return 'informacion_relevante'
    return 'otro'

AREAS = [
 ('seguros', r'seguro|asistencia[s]?[- ]|cuota[- ]protegida|vive[- ]la[- ]vida|clausulado|multiasistencia|autoprotegido'),
 ('tarjetas_credito', r'tarjeta[s]?[- ]?(de[- ])?credito|credencial|latam|visa|mastercard|occiflex|santa[- ]?fe|unicef|platinum|infinite|black|mastercard-joven|click[- ]to[- ]pay|priority|tc[- ]|\btc\b|gold'),
 ('tarjeta_debito_digital', r'tarjeta[- ]debito|apple[- ]pay|google[- ](pay|wallet)|billetera'),
 ('cuentas', r'cuenta[s]?|nomina|ahorro|afc|corriente|pension|activa|kubo|occidia|bre-?b|fogafin|maestras'),
 ('creditos_consumo', r'libre[- ]inversion|libranza|prestamo|rotativo|cartera[- ]ordinaria|compra[- ]de[- ]cartera|credito[- ]personal|pensiones[- ]voluntarias'),
 ('creditos_vehiculo', r'vehicul|moto|carros|occiauto|autoprotegido'),
 ('creditos_vivienda', r'vivienda|hipotecari|leasing[- ]habitacional|mejora|remodelacion|constructor|proyectos[- ]de[- ]vivienda'),
 ('leasing_empresas', r'leasing|renting'),
 ('factoring', r'factoring|confirming|unidirecto'),
 ('seguros', r'seguro|asistencia|cuota[- ]protegida|vive[- ]la[- ]vida|clausulado'),
 ('inversion', r'cdt|inversion|fondos|offshore|fiduciar|portafolio'),
 ('comercio_exterior_tesoreria', r'moneda[- ]extranjera|importad|exportad|mesa[- ]de[- ]dinero|mesa-dinero|cambiari|divisas|tasas[- ]de[- ](cambio|interes)|credito[- ]de[- ]tesoreria|carta[- ]de[- ]credito|datos[- ]aduaneros'),
 ('pagos_recaudos_canales', r'pago|recaudo|pse|occired|canales|portal[- ]transaccional|banca[- ]movil|token|transferencia|pila|facilpass|prepago|multicash|debito[- ]automatico|corresponsal|aval[- ]?pay|cheque'),
 ('gobierno_corporativo', r'junta|comite|estatuto|gobierno|asamblea|accionista|revisor|codigo[- ]de[- ]etica|conflicto|nombramiento|reglamento'),
 ('sostenibilidad', r'sostenib|gri|tcfd|ambiental|climat|carbono|derechos[- ]humanos|inversion[- ]social|dei|inclusion|huella'),
 ('cumplimiento_riesgos', r'sarlaft|aml|patriot|wolfsberg|fatca|anticorrup|abac|conocimiento|seguridad[- ]de[- ]la[- ]informacion|red[- ]team|plan[- ]de[- ]respuesta|drp|fraude'),
 ('datos_personales', r'datos[- ]personales|habeas|privacidad|tratamiento[- ]de[- ]datos'),
 ('estados_financieros_inversionistas', r'eeff|estado[s]?[- ]financiero|calificacion|fitch|informe[- ]periodico|informacion[- ]relevante|bonos|prospecto'),
 ('estudios_economicos', r'pulso|radar|occimpacto|radiografia|informe[- ]sectorial|termometro|tes-|canonazos|economic'),
 ('tributario', r'tributari|calendario|renta|impuesto'),
 ('educacion_financiera', r'educacion[- ]financiera|/b/'),
 ('institucional', r'quienes[- ]somos|nuestro[- ]banco|historia|organigrama|about[- ]us|filiales|transparencia|trabaja|talento|beneficios'),
]
def area(r, td):
    if 'bancodeoccidente' not in r['fuente'] or td == 'externo_sin_contenido': return 'externo'
    s = norm(unquote(urlparse(r['url']).path)) + ' ' + norm(r['titulo'])
    if td in ('estado_financiero', 'informacion_relevante', 'calificacion', 'emision_valores'): return 'estados_financieros_inversionistas'
    if td == 'asamblea_accionistas': return 'gobierno_corporativo'
    if td == 'informe_gestion_sostenibilidad': return 'sostenibilidad'
    if td == 'estudio_economico': return 'estudios_economicos'
    if td == 'tributario': return 'tributario'
    if td == 'educacion_financiera': return 'educacion_financiera'
    if td == 'empleo_cultura': return 'institucional'
    for a, rx in AREAS:
        if re.search(rx, s): return a
    txt = norm(r['texto'][:2500]) if r['texto'] else ''
    best = None; bs = 0
    for a, rx in AREAS:
        c = len(re.findall(rx, txt))
        if c > bs: best, bs = a, c
    if best and bs >= 3: return best
    et = norm(' '.join(' '.join(e) for e in r['etiquetas']))
    for a, rx in AREAS:
        if re.search(rx, et): return a
    if td in ('contrato_formato', 'reglamento_politica', 'legal_normativa'): return 'transversal_formatos_politicas'
    return 'otros'

def segmento(r):
    p = urlparse(r['url']).path.lower()
    et = r['etiquetas'][0][0] if r['etiquetas'] and r['etiquetas'][0] else ''
    if '/web/empresas' in p or et == 'EMPRESAS' or '/documents/d/empresas/' in p or '/documents/43377/' in p: return 'empresas'
    if et == 'INVERSIONISTAS' or 'informacion-inversionistas' in p or 'informacion-accionistas' in p: return 'inversionistas'
    return 'personas'

# ---------------- vigencia ----------------
def fecha_re(txt):
    out = []
    for m in re.finditer(r'(\d{1,2})\s+de\s+([a-záéíóú]+)\s+(?:de\s+|del\s+)?(20\d\d)', txt, re.I):
        mm = MES.get(norm(m.group(2)))
        if mm: out.append((int(m.group(3)), mm, int(m.group(1)), m.start()))
    return out
def vigencia(r, td):
    txt = r['texto'][:60000] if r['texto'] else ''
    low = norm(txt)
    vd = vh = None
    # hasta el DD de mes de YYYY
    for m in re.finditer(r'(vigenc\w+|valid\w+|promocion\w*|campana)[^.\n]{0,120}?hasta\s+(?:el\s+)?(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+|del\s+)?(20\d\d)', low):
        mm = MES.get(m.group(3))
        if mm:
            try: vh = f'{int(m.group(4)):04d}-{mm:02d}-{int(m.group(2)):02d}'
            except Exception: pass
            break
    if not vh:
        for m in re.finditer(r'del\s+(\d{1,2})\s+(?:de\s+[a-z]+\s+)?al\s+(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+|del\s+)?(20\d\d)', low):
            mm = MES.get(m.group(3))
            if mm and re.search(r'vigenc|campana|promocion|bases', low[max(0, m.start() - 200):m.end() + 100]):
                vh = f'{int(m.group(4)):04d}-{mm:02d}-{int(m.group(2)):02d}'; break
    for m in re.finditer(r'(a\s+partir\s+del|vigente\s+desde(?:\s+el)?|desde\s+el)\s+(\d{1,2})\s+de\s+([a-z]+)\s+(?:de\s+|del\s+)?(20\d\d)', low):
        mm = MES.get(m.group(3))
        if mm: vd = f'{int(m.group(4)):04d}-{mm:02d}-{int(m.group(2)):02d}'; break
    # periodo para informes periodicos
    name = norm(unquote(urlparse(r['url']).path.split('?')[0]))
    per = None
    m = re.search(r'(?:^|[^a-z])(mar|jun|sep|dic)[-_ ](\d{2})(?:[^0-9]|$)', name)
    if m and td in ('estado_financiero', 'informacion_relevante'):
        mm = {'mar': 3, 'jun': 6, 'sep': 9, 'dic': 12}[m.group(1)]; per = eomonth(2000 + int(m.group(2)), mm)
    if not per:
        m = re.search(r'(?:a\s+)?(?:diciembre|junio|septiembre|marzo)[- ]31?[- ]?(?:de[- ])?(20\d\d)', name) or re.search(r'diciembre[- ]31[- ]de[- ](20\d\d)', name)
        if m and td == 'estado_financiero':
            y = int(m.group(1)); mon = 'diciembre' if 'diciembre' in name else 'junio' if 'junio' in name else 'septiembre' if 'septiembre' in name else 'marzo'
            per = eomonth(y, MES[mon])
    if not per:
        m = re.search(r'(enero[- ]marzo|abril[- ]junio|julio[- ]septiembre|octubre[- ]diciembre)[- ](20\d\d)', name)
        if m: per = eomonth(int(m.group(2)), {'enero-marzo': 3, 'abril-junio': 6, 'julio-septiembre': 9, 'octubre-diciembre': 12}[m.group(1).replace(' ', '-')])
    if not per and td in ('estado_financiero', 'informacion_relevante', 'informe_gestion_sostenibilidad', 'calificacion'):
        m = re.search(r'(?:al|a|de)\s+(\d{1,2})\s+de\s+([a-z]+)\s+de\s+(20\d\d)', norm(r['texto'][:3000]))
        if m and MES.get(m.group(2)): per = eomonth(int(m.group(3)), MES[m.group(2)])
    # anio del documento
    yrs = [int(y) for y in re.findall(r'(?<!\d)(20[12]\d)(?!\d)', name + ' ' + norm(r['titulo']))]
    if not yrs: yrs = [int(y) for y in re.findall(r'(?<!\d)(20[12]\d)(?!\d)', norm(r['texto'][:3000]))]
    yrs = [y for y in yrs if y <= 2027]
    anio = max(yrs) if yrs else None
    if per: anio = int(per[:4])
    return vd, vh, per, anio

PERIODICOS = {'estado_financiero', 'informacion_relevante', 'asamblea_accionistas', 'calificacion', 'informe_gestion_sostenibilidad', 'estudio_economico', 'tributario', 'emision_valores'}
def estado(r, td, vh, per, anio):
    if vh: return 'vencido' if vh < HOY else 'vigente'
    if td in PERIODICOS:
        ref = per or (str(anio) if anio else None)
        if ref and ref[:4] < '2026': return 'historico'
        if ref: return 'vigente' if td not in ('estado_financiero', 'informe_gestion_sostenibilidad') else 'periodo_reciente'
        return 'por_verificar'
    if r['tipo_contenido'].startswith('pagina'): return 'vigente'
    if td in ('tarifas_tasas', 'terminos_condiciones', 'contrato_formato', 'guia_de_uso'):
        return 'por_verificar'
    return 'vigente'

# ---------------- features / flags ----------------
def feats(r):
    t = r['texto']; n = len(t); fl = []
    st = pst.get(int(r['id']))
    pages = None
    if st: pages = st['pages']
    else:
        mk = [int(x) for x in re.findall(r'<!-- página (\d+) -->', t)]
        pages = max(mk) if mk else (1 if r['tipo_contenido'] in ('pdf', 'pdf (OCR)') else None)
    cpp = round(n / pages) if (pages and n) else None
    if r['duplicado_de']: fl.append('duplicado_exacto')
    if n == 0 and not r['duplicado_de']: fl.append('sin_texto')
    if 0 < n < 200 and not r['duplicado_de']: fl.append('muy_corto')
    if n > 1_500_000: fl.append('muy_largo')
    if cpp is not None and cpp < 300 and r['tipo_contenido'] in ('pdf', 'pdf (OCR)') and n: fl.append('poco_texto_por_pagina')
    if 'OCR' in r['tipo_contenido']: fl.append('ocr')
    if st and st['imgs_big'] >= 3 and cpp is not None and (cpp < 600 or (st['pages'] and st['imgs_big'] / st['pages'] >= 0.8 and cpp < 2000)): fl.append('candidato_vlm')
    moj = len(re.findall(r'Ã[\x80-\xbf¡-¿]|�|â€|\(cid:\d+\)', t))
    if moj > 5: fl.append('mojibake')
    lines = [l for l in t.split('\n') if l.strip()]
    if lines:
        numcols = sum(1 for l in lines if len(re.findall(r'\s{3,}', l)) >= 3 and re.search(r'\d', l))
        if numcols / len(lines) > 0.25 and numcols > 40: fl.append('tablas_numericas')
        webt = sum(1 for l in lines if l.startswith('| '))
        if webt > 5: fl.append('tablas_markdown')
    if r['tipo_contenido'].startswith('pagina') and re.search(r'^1\. Inicio', t) is None and n > 0 and r['tipo_contenido'] == 'pagina_web' and '/web/empresas' not in r['url'] and False: pass
    return dict(chars=n, paginas=pages, chars_por_pagina=cpp, imgs_grandes=(st or {}).get('imgs_big'), flags=fl)

def titulo_dudoso(r):
    if not r['tipo_contenido'].startswith('pagina'): return False
    slug = [w for w in re.split(r'[^a-z0-9]+', norm(unquote(urlparse(r['url']).path))) if len(w) > 3 and w not in ('web', 'empresas', 'guest', 'documents')]
    tt = set(re.split(r'[^a-z0-9]+', norm(r['titulo'])))
    if not slug: return False
    tnos = re.sub(r'[^a-z0-9]', '', norm(r['titulo']))
    if any(w in tnos for w in slug): return False
    return not any(w in tt or any(w[:5] == x[:5] for x in tt if len(x) > 4) for w in slug)

# ---------------- casi-duplicados (minhash) ----------------
def shingles(t, k=5, cap=30000):
    w = re.findall(r'\w+', t.lower())[:cap]
    return {zlib.crc32(' '.join(w[i:i + k]).encode()) for i in range(0, max(0, len(w) - k + 1))}
NP = 64
SEEDS = [random.Random(i).getrandbits(32) | 1 for i in range(NP)]
def sig(s):
    if not s: return None
    return [min(((x * a) ^ (x >> 7)) & 0xFFFFFFFF for x in s) for a in SEEDS]
cand = [r for r in rows if r['texto'] and not r['duplicado_de'] and len(r['texto']) > 800]
sigs = {r['id']: sig(shingles(r['texto'])) for r in cand}
buckets = collections.defaultdict(list)
for i, s in sigs.items():
    if s:
        for b in range(0, NP, 4): buckets[(b, tuple(s[b:b + 4]))].append(i)
pairs = collections.Counter()
for ids in buckets.values():
    if 1 < len(ids) < 40:
        for a in range(len(ids)):
            for b in range(a + 1, len(ids)): pairs[(ids[a], ids[b])] += 1
near = {}
neardet = []
for (a, b), c in pairs.items():
    sa, sb = sigs[a], sigs[b]
    j = sum(1 for x, y in zip(sa, sb) if x == y) / NP
    if j >= 0.8:
        neardet.append((a, b, round(j, 2)))
        lo, hi = (a, b) if int(a) < int(b) else (b, a)
        if hi not in near: near[hi] = (lo, round(j, 2))

# ---------------- aplicar ----------------
for r in rows:
    if 'titulo_original' in r: r['titulo'] = r.pop('titulo_original')
    td = tipo_doc(r); ar = area(r, td); sg = segmento(r)
    vd, vh, per, anio = vigencia(r, td)
    f = feats(r)
    r['tipo_doc'] = td; r['area'] = ar; r['segmento'] = sg
    r['idioma'] = idioma(r['texto']) if r['texto'] else (by_id[r['duplicado_de']] and idioma(by_id[r['duplicado_de']]['texto']) if r['duplicado_de'] and r['duplicado_de'] in by_id else 'indeterminado')
    r['anio_documento'] = anio; r['periodo_fin'] = per; r['vigente_desde'] = vd; r['vigente_hasta'] = vh
    r['estado_vigencia'] = estado(r, td, vh, per, anio)
    r['clasificacion_acceso'] = 'publico'
    r['hash_contenido'] = hashlib.sha256(re.sub(r'\s+', ' ', r['texto']).encode()).hexdigest()[:16] if r['texto'] else None
    r['paginas'] = f['paginas']; r['chars_por_pagina'] = f['chars_por_pagina']; r['imgs_grandes'] = f['imgs_grandes']
    fl = f['flags']
    if r['id'] in near: r['casi_duplicado_de'] = near[r['id']][0]; r['similitud'] = near[r['id']][1]; fl.append('casi_duplicado')
    else: r['casi_duplicado_de'] = None; r['similitud'] = None
    if r['idioma'] == 'en': fl.append('ingles')
    if titulo_dudoso(r):
        fl.append('titulo_dudoso')
        m = re.search(r'^#{1,3}\s+\*{0,2}(.{6,90}?)\*{0,2}\s*$', r['texto'], re.M)
        sug = re.sub(r'\*+', '', m.group(1)).strip() if m else ''
        if m and len(sug) >= 12 and not sug.lower().startswith('título') and 'titulo_original' not in r:
            r['titulo_original'] = r['titulo']; r['titulo'] = re.sub(r'\*+', '', m.group(1)).strip()
    if r['anio_documento'] is None and td in ('tarifas_tasas', 'terminos_condiciones', 'guia_de_uso', 'informe_gestion_sostenibilidad'): fl.append('sin_fecha')
    if r['estado_vigencia'] == 'vencido': fl.append('vigencia_vencida')
    r['flags'] = fl
    r['etiquetas_origen'] = r['etiquetas']

json.dump(neardet, open(R + 'f1_neardups.json', 'w'))
with open(OUT + 'corpus.jsonl', 'w') as jl:
    for r in rows: jl.write(json.dumps(r, ensure_ascii=False) + '\n')
print('ok', len(rows), 'near', len(near))
print(collections.Counter(r['tipo_doc'] for r in rows).most_common())
print(collections.Counter(r['area'] for r in rows).most_common())
print(collections.Counter(r['segmento'] for r in rows))
print(collections.Counter(r['estado_vigencia'] for r in rows))
print(collections.Counter(f for r in rows for f in r['flags']).most_common())
