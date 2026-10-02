"""Recaptura de documentos «vivos» (misma URL, contenido que cambia) con VERSIONAMIENTO.

Exigencia de las directivas del banco: al recapturar, si el contenido cambió, la versión anterior se conserva como histórica con su fecha de fin y nunca se sobrescribe.
Entrada : _raw/recaptura/<slug>.pdf (descargados desde la pestaña del navegador con fetch(); ver pipeline/README.md)
Efecto  : agrega la versión nueva a rag-bocc/corpus.jsonl (campo version_de = id anterior), registra las decisiones de vigencia de la versión
          nueva y de la anterior en rag-bocc/vigencia/decisiones.jsonl y deja la regeneración del árbol a 05_escribir_y_auditar.py.
Es idempotente: si la URL ya tiene una versión con el mismo contenido no hace nada.
Uso: python 17_recaptura.py [--fecha 2026-10-02]   y luego   python 05_escribir_y_auditar.py
"""
import argparse, calendar, copy, datetime, hashlib, json, os, re, sys
sys.path.insert(0, os.path.dirname(__file__))
from helpers import pdf_text

ap = argparse.ArgumentParser(); ap.add_argument('--fecha', default='2026-10-02'); args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
BASE = 'https://www.bancodeoccidente.com.co/documents/d/guest/'
MESES = 'enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre'.split()
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
por_id = {r['id']: r for r in rows}
OBJETIVOS = ['tarifas-persona-bdo', 'tarifas-empresariales-bdo', 'tasas-personas-bdo', 'tasas-empresariales-bdo']


def norm(t): return re.sub(r'\s+', ' ', re.sub(r'<!-- página \d+ -->', ' ', t)).strip()
def h(t): return hashlib.sha256(norm(t).encode()).hexdigest()[:16]


def vigencia(slug, texto):
    """(desde, hasta, nota). Tarifas: hasta el 31-dic-2026 (regla confirmada por los expertos). Tasas: el mes que declara el documento."""
    if slug.startswith('tarifas'): return '2026-10-01', '2026-12-31', 'tarifas: vencen el 31-dic-2026 (expertos del banco)'
    t = re.sub(r'\s+', ' ', texto)
    m = re.search(r'(?i)vigentes? del (\d{1,2}) al (\d{1,2}) de (' + '|'.join(MESES) + r')\w* (?:de|del) (20\d\d)', t)
    if m:
        d1, d2, mes, y = int(m.group(1)), int(m.group(2)), MESES.index(m.group(3).lower()) + 1, int(m.group(4))
    else:
        m = re.search(r'(?i)(' + '|'.join(MESES) + r') (?:de|del) (20\d\d)', t)
        if not m: return None, None, 'sin periodo legible'
        mes, y = MESES.index(m.group(1).lower()) + 1, int(m.group(2)); d1, d2 = 1, calendar.monthrange(y, mes)[1]
    return f'{y}-{mes:02d}-{d1:02d}', f'{y}-{mes:02d}-{d2:02d}', 'tasas mensuales: periodo declarado en el documento'


nuevos, decis, cambios = [], [], []
for slug in OBJETIVOS:
    fn = B + f'_raw/recaptura/{slug}.pdf'
    if not os.path.exists(fn): print('falta', fn); continue
    texto, tipo = pdf_text(fn)
    url = BASE + slug
    mismos = [r for r in rows + nuevos if r['url'] == url]
    if not mismos: print('URL desconocida', url); continue
    if any(r['texto'].strip() and h(r['texto']) == h(texto) for r in mismos): print(slug, ': sin cambios'); continue
    d, hasta, nota = vigencia(slug, texto)
    anterior = next(r for r in mismos)           # fila de esa URL
    if anterior['texto'].strip() or not anterior.get('duplicado_de'):
        viejo = anterior; nuevo = copy.deepcopy(anterior); nuevo['id'] = str(max(int(r['id']) for r in rows + nuevos) + 1)
    else:                                         # la fila de la URL era un duplicado sin texto de otra versión: se reutiliza para la versión nueva
        viejo = por_id[anterior['duplicado_de']]; nuevo = anterior
    seg = 'empresas' if 'empresarial' in slug else 'personas'
    pag = texto.count('\f') or 1
    nuevo.update(texto=texto, tipo_contenido=tipo, hash_contenido=h(texto), paginas=pag, chars_por_pagina=int(len(texto) / pag), fecha_extraccion=args.fecha,
                 lote='recaptura-' + args.fecha, duplicado_de=None, casi_duplicado_de=None, similitud=None, segmento=seg, anio_documento=int(args.fecha[:4]),
                 version_de=viejo['id'], flags=sorted((set(nuevo['flags']) - {'duplicado_exacto', 'casi_duplicado', 'sin_fecha', 'sin_texto', 'muy_corto'}) | {'version_nueva'}))
    if nuevo is not anterior: nuevos.append(nuevo)
    fin_viejo = (datetime.date.fromisoformat(d) - datetime.timedelta(days=1)).isoformat() if d else None
    decis.append(dict(id=viejo['id'], vigente_desde=viejo.get('vigente_desde'), vigente_hasta=fin_viejo or viejo.get('vigente_hasta'), estado='historico',
                      fuente=f'versión anterior de {slug}, reemplazada el {args.fecha} (versionamiento)'))
    decis.append(dict(id=nuevo['id'], vigente_desde=d, vigente_hasta=hasta, estado='vigente' if slug.startswith('tarifas') else 'vigente_hasta_reemplazo',
                      fuente=f'recaptura {args.fecha} de {slug}: {nota}'))
    cambios.append((slug, viejo['id'], nuevo['id'], d, hasta))
    print(f'{slug}: nueva versión {nuevo["id"]} (anterior {viejo["id"]} → histórica) vigencia {d} → {hasta}')

if cambios:
    with open(OUT + 'corpus.jsonl', 'w') as f:
        for r in rows + nuevos: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    with open(OUT + 'vigencia/decisiones.jsonl', 'a') as f:
        for x in decis: f.write(json.dumps(dict(x, validado_por='anvorja', fecha_validacion=args.fecha), ensure_ascii=False) + '\n')
    print(len(cambios), 'versiones nuevas; ahora ejecuta 05_escribir_y_auditar.py')
