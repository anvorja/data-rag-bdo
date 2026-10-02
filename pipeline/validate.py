"""Validaciones del repositorio (se ejecutan en CI como «Calidad de datos y secretos»).

1. Consistencia del corpus: indice.json <-> archivos .md, campos obligatorios en el frontmatter.
2. Golden set (si existe): esquema y que la `cita_literal` aparezca en el documento citado.
3. Secretos: patrones de claves/tokens en el código y los datos versionados.
4. Tamaño: ningún archivo versionado > 50 MB (GitHub rechaza > 100 MB).
Sale con código 1 si hay errores.
"""
import json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CORPUS = os.path.join(ROOT, 'rag-bocc')
errores, avisos = [], []

# ---------- 1. corpus ----------
REQ = ['id', 'url', 'titulo', 'tipo_doc', 'area', 'segmento', 'idioma', 'estado_vigencia', 'clasificacion_acceso', 'indexar', 'flags']
idx_path = os.path.join(CORPUS, 'indice.json')
n_md = 0
if os.path.exists(idx_path):
    idx = json.load(open(idx_path))
    ids = [r['id'] for r in idx]
    if len(ids) != len(set(ids)): errores.append('indice.json: ids duplicados')
    for r in idx:
        p = os.path.join(CORPUS, r['archivo'])
        if not os.path.exists(p): errores.append(f"falta el archivo {r['archivo']}"); continue
        head = open(p, encoding='utf8').read(4000).split('---')
        fm = head[1] if len(head) > 2 else ''
        for k in REQ:
            if not re.search(rf'^{k}:', fm, re.M): errores.append(f"{r['archivo']}: falta «{k}» en el frontmatter")
        if r.get('clasificacion_acceso') not in (None, 'publico') and 'clasificacion_acceso' in r: avisos.append(f"{r['id']}: clasificación distinta de público")
    for root, _, files in os.walk(os.path.join(CORPUS, 'documentos')):
        n_md += sum(1 for f in files if f.endswith('.md'))
    if n_md != len(idx): errores.append(f'documentos/*.md ({n_md}) != entradas en indice.json ({len(idx)})')
else:
    avisos.append('no hay rag-bocc/indice.json (corpus no versionado en esta rama)')

# ---------- 2. golden set (opcional) ----------
g = os.path.join(CORPUS, 'golden')
if os.path.isdir(g):
    docs = {}
    for r in json.load(open(idx_path)): docs[r['id']] = os.path.join(CORPUS, r['archivo'])
    for fn in sorted(os.listdir(g)):
        if not fn.endswith('.jsonl'): continue
        for n, line in enumerate(open(os.path.join(g, fn), encoding='utf8'), 1):
            try: q = json.loads(line)
            except Exception: errores.append(f'{fn}:{n}: JSON inválido'); continue
            for k in ('id', 'pregunta', 'tipo', 'split', 'fuentes', 'debe_abstenerse'):
                if k not in q: errores.append(f"{fn}:{n}: falta «{k}»")
            if q.get('split') not in ('dev', 'test'): errores.append(f'{fn}:{n}: split inválido')
            for f in q.get('fuentes', []):
                p = docs.get(f.get('doc_id'))
                if not p: errores.append(f"{fn}:{n}: doc_id {f.get('doc_id')} no existe"); continue
                cita = re.sub(r'\s+', ' ', f.get('cita_literal', '')).strip()
                if cita and cita not in re.sub(r'\s+', ' ', open(p, encoding='utf8').read()): errores.append(f"{fn}:{n}: la cita_literal no aparece en {f.get('doc_id')}")

# ---------- 3. secretos y 4. tamaño ----------
PATS = {'aws': r'AKIA[0-9A-Z]{16}', 'google_api': r'AIza[0-9A-Za-z\-_]{35}', 'openai_like': r'sk-[A-Za-z0-9]{20,}', 'github': r'gh[pousr]_[A-Za-z0-9]{30,}',
        'slack': r'xox[baprs]-[A-Za-z0-9-]{10,}', 'private_key': r'-----BEGIN [A-Z ]*PRIVATE KEY-----', 'jwt': r'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}',
        'asignacion': r'(?i)\b(api[_-]?key|secret|passwd|password|client_secret|access[_-]?token)\b\s*[:=]\s*["\'][^"\'\s]{8,}["\']', 'bearer': r'(?i)bearer\s+[A-Za-z0-9\-._~+/]{20,}'}
try:
    tracked = subprocess.run(['git', 'ls-files'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.split('\n')
except Exception:
    tracked = [os.path.relpath(os.path.join(r, f), ROOT) for r, _, fs in os.walk(ROOT) for f in fs if '.git' not in r]
for rel in filter(None, tracked):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p): continue
    if os.path.getsize(p) > 50 * 1024 * 1024: errores.append(f'{rel}: > 50 MB')
    if rel.endswith(('.png', '.jpg', '.pdf', '.dat')): continue
    t = open(p, errors='ignore').read()
    for k, rx in PATS.items():
        if re.search(rx, t) and not rel.endswith('validate.py'): errores.append(f'{rel}: posible secreto ({k})')
    if os.path.basename(rel) == '.env': errores.append('.env versionado')

print(f'corpus: {n_md} documentos .md · errores: {len(errores)} · avisos: {len(avisos)}')
for a in avisos: print('AVISO', a)
for e in errores[:50]: print('ERROR', e)
sys.exit(1 if errores else 0)
