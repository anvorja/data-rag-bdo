"""Reconstruye rag-bocc/corpus.jsonl (archivo generado, ignorado por git) a partir de lo que SÍ está versionado:
rag-bocc/indice.json (metadatos de cada documento) y rag-bocc/documentos/**/*.md (cabecera YAML + texto).
Sirve para trabajar desde un clon limpio sin los originales de _raw/. Solo regenera el corpus; no vuelve a extraer ni a clasificar nada.

Uso:  python pipeline/20_reconstruir_corpus.py [--salida rag-bocc/corpus.jsonl] [--comparar]
      --comparar  no escribe; compara con el corpus.jsonl existente y muestra las diferencias (prueba de fidelidad).
Limitación: no recupera lo que solo vivía en _raw/ (descripciones largas del rastreo, etiquetas crudas); el resto de campos vuelve idéntico."""
import argparse, json, os, re, sys

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
OUT = B + 'rag-bocc/'
ap = argparse.ArgumentParser(); ap.add_argument('--salida', default=OUT + 'corpus.jsonl'); ap.add_argument('--comparar', action='store_true'); args = ap.parse_args()


def valor(v):
    v = v.strip()
    if v in ('null', ''): return None
    if v in ('true', 'false'): return v == 'true'
    if v[:1] in '"[{': 
        try: return json.loads(v)
        except Exception:
            if v.startswith('['): return [x.strip() for x in v[1:-1].split(',') if x.strip()]
            return v.strip('"')
    if re.fullmatch(r'-?\d+', v): return int(v)
    if re.fullmatch(r'-?\d+\.\d+', v): return float(v)
    return v


def leer_md(path):
    t = open(path, encoding='utf8').read()
    m = re.match(r'---\n(.*?)\n---\n\n', t, re.S)
    fm, cuerpo = m.group(1), t[m.end():]
    meta, clave = {}, None
    for l in fm.split('\n'):
        if l.startswith('  - ') and clave == 'etiquetas_origen':
            meta['etiquetas_origen'].append([x.strip() for x in json.loads(l[4:]).split(' > ')]); continue
        k, _, v = l.partition(': ') if ': ' in l else (l.rstrip(':'), '', '')
        clave = k
        meta[k] = [] if k == 'etiquetas_origen' else (v.strip() if k == 'hash_contenido' and v.strip() != 'null' else valor(v))   # un hash solo con dígitos o «1e5…» no es un número
    titulo = meta.get('titulo') or ''
    pref = f'# {titulo}\n\n'
    if cuerpo.startswith(pref): cuerpo = cuerpo[len(pref):]
    cuerpo = cuerpo[:-1] if cuerpo.endswith('\n') else cuerpo
    if re.fullmatch(r'_Contenido idéntico al documento \S+; no se repite\._', cuerpo) or cuerpo.startswith('_Sin contenido extraído: '): cuerpo = ''
    return meta, cuerpo


idx = json.load(open(OUT + 'indice.json'))
rows = []
for d in idx:
    meta, texto = leer_md(OUT + d['archivo'])
    r = dict(meta); r.update({k: v for k, v in d.items() if k not in ('caracteres',)})    # indice.json manda en los campos que contiene
    r['texto'] = texto; r.setdefault('etiquetas', r.get('etiquetas_origen', [])); r.setdefault('descripcion', meta.get('descripcion') or '')
    r.pop('caracteres', None)                                                   # se calcula a partir del texto
    for k in ('version_de', 'vigencia_validada', 'lote', 'titulo_publico'):                      # campos opcionales: solo si tienen valor
        if r.get(k) is None: r.pop(k, None)
    r['flags'] = d['flags']; r['motivo_no_indexar'] = d.get('motivo_no_indexar') or []
    rows.append(r)

if args.comparar:
    if not os.path.exists(OUT + 'corpus.jsonl'): sys.exit('no hay corpus.jsonl con el que comparar')
    ant = {r['id']: r for r in map(json.loads, open(OUT + 'corpus.jsonl'))}
    dif = {}; n_txt = 0
    for r in rows:
        a = ant.get(r['id'])
        if not a: dif.setdefault('id_nuevo', []).append(r['id']); continue
        if a['texto'] != r['texto']: n_txt += 1; dif.setdefault('texto', []).append(r['id'])
        for k in a:
            if k != 'texto' and k in r and a[k] != r[k]: dif.setdefault(k, []).append(r['id'])
        for k in a:
            if k not in r: dif.setdefault('falta:' + k, []).append(r['id'])
    print(len(rows), 'documentos reconstruidos;', len(ant), 'en el corpus actual')
    for k, v in sorted(dif.items(), key=lambda x: -len(x[1])): print(f'  {k}: {len(v)} documentos (p. ej. {v[:3]})')
    if not dif: print('  idéntico')
else:
    with open(args.salida, 'w') as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(len(rows), 'documentos →', args.salida)
