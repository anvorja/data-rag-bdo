"""Fase 2 · paso 0: elimina texto de plantilla del CMS (placeholders de diseño) de las páginas web del corpus.

Ejemplos: «## Título máximo de caracteres 60», «Por favor digitar máximo 240 caracteres…»,
«- ### Maximo 60 caracteres  Aquí va la descripción del mensaje…», «## Texto de pruebas para el accordeon».
Actualiza corpus.jsonl (texto, flags) y regenera los .md afectados con 05_escribir_y_auditar.py.
Registra en `flags` la alerta `plantilla_cms_limpiada` y en `nota` cuántas líneas se quitaron.
"""
import json, os, re

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
PLANT = re.compile(r'(?i)(t[ií]tulo m[aá]ximo de caracteres|texto de pruebas|m[aá]ximo? \d+ caracteres|digitar m[aá]ximo 240|lorem ipsum|aqu[ií] va la descripci[oó]n|este apartado no contiene limitaci[oó]n de caracteres|agregue una imagen tama[nñ]o aproximado|verifique la version mobile|^featured title$|^texto del bot[oó]n$|t[ií]tulo de maximo 240)')
rows = [json.loads(l) for l in open(OUT + 'corpus.jsonl')]
tot = 0

def arreglar_mojibake(t):
    """Reparte texto UTF-8 que fue decodificado como latin-1 (p. ej. «CrÃ©dito» -> «Crédito»)."""
    if len(re.findall(r'Ã[\x80-\xbf¡-¿]', t)) < 5: return t, False
    try: return t.encode('latin-1').decode('utf-8'), True
    except Exception: return t, False

for r in rows:
    r['texto'], fixed = arreglar_mojibake(r['texto'])
    if fixed: r['nota'] = ((r.get('nota') or '') + ' Se corrigió la codificación (mojibake).').strip()
    if not r['tipo_contenido'].startswith('pagina') or not any(PLANT.search(l) for l in r['texto'].split('\n')): continue
    out, quitadas = [], 0
    for l in r['texto'].split('\n'):
        if PLANT.search(l.strip()): quitadas += 1; continue
        out.append(l)
    t = re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip()
    # encabezados huérfanos (título seguido de otro encabezado o del final) tras quitar placeholders
    t = re.sub(r'(?m)^#{1,6} *\n+(?=#|\Z)', '', t)
    r['texto'] = t
    if 'plantilla_cms_limpiada' not in r['flags']: r['flags'].append('plantilla_cms_limpiada')
    r['nota'] = ((r.get('nota') or '') + f' Se quitaron {quitadas} líneas de plantilla del CMS.').strip()
    tot += 1
with open(OUT + 'corpus.jsonl', 'w') as f:
    for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
print('páginas limpiadas:', tot)
