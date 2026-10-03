"""Vigencia · paso 1: propone fechas de vigencia explícitas a partir del TEXTO de los documentos «por_verificar».
No modifica el corpus: escribe rag-bocc/vigencia/propuesta.jsonl para revisión humana (una decisión por documento).
Reconoce rangos como «desde el día 01 de agosto de 2026 … hasta el día 31 de octubre de 2026», «del 1 al 31 de julio de 2026»,
«vigencia: 1 de junio de 2026 al 30 de junio de 2026». Fecha de referencia: la de hoy (--hoy)."""
import argparse, datetime, json, os, re
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
ap = argparse.ArgumentParser(); ap.add_argument('--hoy', default='2026-10-02'); args = ap.parse_args()
HOY = datetime.date.fromisoformat(args.hoy)
M = {m: i for i, m in enumerate('enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split(), 1)}; M['setiembre'] = 9
F = r'(\d{1,2})\s+de\s+(' + '|'.join(M) + r')(?:\s+(?:de|del)\s+(20\d\d))?'
FD = lambda g: (int(g[2]) if g[2] else None, M[g[1].lower()], int(g[0]))
PATS = [
    re.compile(r'(?is)(?:desde|a partir d[el]+|entre)\s+(?:el\s+)?(?:d[ií]a\s+)?' + F + r'.{0,120}?(?:hasta|al|y)\s+(?:el\s+)?(?:d[ií]a\s+)?' + F),
    re.compile(r'(?is)del\s+(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(' + '|'.join(M) + r')(?:\s+(?:de|del)\s+(20\d\d))?'),
]
def rangos(t):
    t = re.sub(r'\s+', ' ', t); out = []
    for m in PATS[0].finditer(t):
        a, b = FD(m.groups()[:3]), FD(m.groups()[3:])
        y2 = b[0] or a[0]; y1 = a[0] or y2
        if y1 and y2: out.append((datetime.date(y1, a[1], a[2]), datetime.date(y2, b[1], b[2]), m.group(0)[:160]))
    for m in PATS[1].finditer(t):
        d1, d2, mes, y = m.groups()
        if y: out.append((datetime.date(int(y), M[mes.lower()], int(d1)), datetime.date(int(y), M[mes.lower()], int(d2)), m.group(0)))
    return [(a, b, s) for a, b, s in out if a <= b and (b - a).days < 800]
# Segunda pasada: rangos cerca de la palabra «vigencia» con formatos más libres
# («del día 4 de mayo del 2026 a las 8:00 … al día …», «entre el quince (15) Enero y el treinta y uno (31) diciembre de 2026»).
G = r'(?:[a-záéíóú\- ]{2,30}\()?(\d{1,2})\)?(?:\s+de)?\s+(' + '|'.join(M) + r')(?:\s+(?:de|del)\s+(20\d\d))?'
P2 = re.compile(r'(?is)(?:del|desde|a partir d[el]+|entre)\s+(?:el\s+)?(?:d[ií]a\s+)?' + G + r'.{0,110}?(?:\bal\b|hasta|\by\b)\s+(?:el\s+)?(?:d[ií]a\s+)?' + G)
def rangos2(t):
    t = re.sub(r'\s+', ' ', t); out = []
    for v in re.finditer(r'(?i)vigencia', t):
        for m in P2.finditer(t[v.start(): v.start() + 450]):
            a, b = FD(m.groups()[:3]), FD(m.groups()[3:])
            y2 = b[0] or a[0]; y1 = a[0] or y2
            if y1 and y2:
                try: out.append((datetime.date(y1, a[1], a[2]), datetime.date(y2, b[1], b[2]), m.group(0)[:160]))
                except ValueError: pass
    return [(a, b, s) for a, b, s in out if a <= b and (b - a).days < 800]
rows = [json.loads(l) for l in open(B + 'rag-bocc/corpus.jsonl')]
os.makedirs(B + 'rag-bocc/vigencia', exist_ok=True)
n = 0; res = {}
with open(B + 'rag-bocc/vigencia/propuesta.jsonl', 'w') as f:
    for r in rows:
        if not (r['indexar'] and r['estado_vigencia'] == 'por_verificar'): continue
        rs = rangos(r['texto'][:12000]) or rangos2(r['texto'][:20000])
        prop = None
        if rs:
            a, b, s = max(rs, key=lambda x: x[1])   # el rango que termina más tarde
            prop = dict(vigente_desde=a.isoformat(), vigente_hasta=b.isoformat(), evidencia=s, estado=('vencido' if b < HOY else 'vigente' if a <= HOY else 'futuro'))
        res[r['id']] = prop
        f.write(json.dumps(dict(id=r['id'], titulo=r['titulo'], tipo_doc=r['tipo_doc'], url=r['url'], propuesta=prop), ensure_ascii=False) + '\n')
con = [k for k, v in res.items() if v]
print(len(res), 'por verificar ·', len(con), 'con fechas explícitas en el texto')
import collections; print(collections.Counter(v['estado'] for v in res.values() if v))
