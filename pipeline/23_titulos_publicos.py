"""Título público legible para cada documento (se muestra al cliente y se usa en los avisos de vigencia).

Los títulos de origen son a menudo nombres de archivo («tyc ollas y sartenes», «dic 24 sep eeff bocc»). Orden de prioridad:
  1. manual        rag-bocc/titulos/manuales.json  {id: "título"}  (lo que decida una persona manda siempre)
  2. pagina        título HTML sin el sufijo «| Banco de Occidente …»
  3. primera_linea primera línea del documento si parece un título («TÉRMINOS Y CONDICIONES CAMPAÑA “…”»)
  4. estado_financiero  a partir del nombre («dic 24 sep eeff bocc» → «Estados financieros separados a diciembre de 2024»)
  5. nombre_archivo   el título de origen limpiado (guiones, siglas, mayúsculas)
Salida: rag-bocc/titulos/titulos_publicos.json {id: {titulo, fuente}}, que aplica 05_escribir_y_auditar.py (campo `titulo_publico`).
No cambia `titulo` (que sigue en el contexto indexado de los fragmentos, para no recalcular embeddings)."""
import json, os, re, collections, unicodedata
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
man = json.load(open(OUT + 'titulos/manuales.json')) if os.path.exists(OUT + 'titulos/manuales.json') else {}
MES = {'ene': 'enero', 'feb': 'febrero', 'mar': 'marzo', 'abr': 'abril', 'may': 'mayo', 'jun': 'junio', 'jul': 'julio', 'ago': 'agosto', 'sep': 'septiembre', 'sept': 'septiembre', 'oct': 'octubre', 'nov': 'noviembre', 'dic': 'diciembre'}
SIGLAS = {'tyc': 'Términos y condiciones', 'bdo': 'Banco de Occidente', 'tc': 'tarjeta de crédito', 'eeff': 'estados financieros', 'bocc': 'Banco de Occidente', 'pyme': 'Pyme', 'pse': 'PSE', 'nit': 'NIT', 'cdt': 'CDT', 'iva': 'IVA', 'sarlaft': 'SARLAFT', 'pqr': 'PQR', 'ey': 'EY', 'kpmg': 'KPMG', 'vlm': 'VLM', 'qr': 'QR'}


def _acentos():
    """palabra sin tilde → variante con tilde más frecuente en el corpus (solo si domina claramente)."""
    cnt = collections.Counter()
    for r in rows:
        if r['indexar']: cnt.update(re.findall(r'[a-záéíóúñü]{4,}', r['texto'][:20000].lower()))
    sin = lambda w: unicodedata.normalize('NFKD', w).encode('ascii', 'ignore').decode()
    mejor = {}
    for w, n in cnt.items():
        k = sin(w)
        if k != w and n > mejor.get(k, ('', 0))[1]: mejor[k] = (w, n)
    return {k: w for k, (w, n) in mejor.items() if n >= 5 * max(1, cnt.get(k, 0))}
ACENTOS = _acentos()


def con_tildes(t):
    return re.sub(r'[A-Za-zñÑ]{4,}', lambda m: (ACENTOS.get(m.group(0).lower(), m.group(0)) if m.group(0).islower() else m.group(0)), t)


def limpiar(s):
    s = re.sub(r'\.(pdf|docx?|xlsx?|xlsm)$', '', s, flags=re.I)
    s = re.sub(r'(?i)\s*[|–-]\s*banco de occidente( - [\w ]+)?\s*$', '', s)
    s = re.sub(r'[_]+', ' ', s); s = re.sub(r'\s+', ' ', s).strip(' -|')
    s = re.sub(r'(?i)(?<=[a-záéíóú])vf\b', '', s); s = re.sub(r'(?i)\b(vf|v\d|final|copia)\b', '', s); s = re.sub(r'\(\d+\)|\s\d$', '', s); s = re.sub(r'\s+', ' ', s).strip(' -|')
    return s


def bonito(s):
    s = limpiar(s)
    if not s: return s
    s = re.sub(r'^\d{1,2}[ .)-]+(?=[A-Za-zÁÉÍÓÚáéíóú])', '', s)
    if s == s.upper() and any(c.isalpha() for c in s): s = s.lower()
    pal = []
    for w in s.split(' '):
        k = w.lower()
        pal.append(SIGLAS.get(k, w if (w != w.lower() and w != w.upper()) or len(w) <= 2 else w.lower()))
    t = con_tildes(' '.join(pal)); t = re.sub(r'(?i)\bde de\b', 'de', t)
    return t[:1].upper() + t[1:]


def primera_linea(r):
    for l in re.sub(r'<!-- página \d+ -->', '\n', r['texto'][:1500]).split('\n'):
        l = re.sub(r'\s+', ' ', l).strip(' *#_-•·|')
        if not l: continue
        if 10 <= len(l) <= 130 and sum(c.isalpha() for c in l) / len(l) >= 0.65 and not re.match(r'(?i)(índice|indice|tabla de contenido|página|pagina|hoja|\d)', l):
            return l
        if len(l) > 130 or len(l) < 10: continue
    return None


def estado_fin(t):
    m = re.search(r'(?i)(?:^|\s)(ene|feb|mar|abr|may|jun|jul|ago|sept?|oct|nov|dic)\s*(\d{2})\s*(sep|con)?\s*eeff', t)
    if not m: return None
    mes, a, tipo = MES[m.group(1).lower()], '20' + m.group(2), m.group(3)
    return f"Estados financieros {'separados' if tipo == 'sep' else 'consolidados' if tipo == 'con' else ''} a {mes} de {a}".replace('  ', ' ')


def titulo_pub(r):
    if r['id'] in man: return man[r['id']], 'manual'
    t0 = r['titulo']
    if r['tipo_contenido'].startswith('pagina'):
        t = limpiar(t0); return (t or t0), 'pagina'
    tipo = r['tipo_doc']; mal = (t0 == t0.lower()) or bool(re.search(r'(?i)\b(tyc|vf|bdo|eeff)\b|_', t0))
    ef = estado_fin(t0)
    if ef: return ef, 'estado_financiero'
    if mal and tipo == 'terminos_condiciones':
        cab = re.sub(r'\s+', ' ', re.sub(r'<!-- página \d+ -->', ' ', r['texto'][:900]))
        m = re.search(r'(?i)(campa[ñn]a|beneficio|programa|convenio|servicio)\s*[“"«]([^”"»]{5,90})[”"»]', cab)
        if m:
            nom = re.split(r'\.\s|\s(?=El |La |Los |Las |Esta |Este )', m.group(2).strip())[0].strip(' .,;')
            if nom == nom.upper(): nom = nom.lower().capitalize()
            return f"Términos y condiciones: {m.group(1).lower()} «{nom}»", 'primera_linea'
        l = primera_linea(r)
        if l and re.search(r'(?i)t[ée]rminos|condiciones|campa[ñn]a|billetera', l) and len(l) >= 25:
            l = re.sub(r'(?i)\s*[–-]\s*banco de occidente( s\.?a\.?)?$', '', l)
            return (l[:1].upper() + l[1:]) if l != l.upper() else l.capitalize(), 'primera_linea'
    if mal and tipo == 'guia_de_uso':
        l = primera_linea(r)
        if l and re.search(r'(?i)gu[ií]a|manual|instruct|uso', l) and len(l) >= 15:
            l = re.sub(r'(?i)^versi[oó]n:?\s*\d+\s*', '', l)
            return (l[:1].upper() + l[1:]) if l != l.upper() else l.capitalize(), 'primera_linea'
    return bonito(t0), 'nombre_archivo' if mal else 'titulo_original'


res = {r['id']: dict(zip(('titulo', 'fuente'), titulo_pub(r))) for r in rows if r['indexar']}
json.dump(res, open(OUT + 'titulos/titulos_publicos.json', 'w'), ensure_ascii=False, indent=0)
print(len(res), 'títulos;', collections.Counter(x['fuente'] for x in res.values()))
