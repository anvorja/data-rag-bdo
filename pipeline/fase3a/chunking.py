"""Fragmentación (chunking) del corpus para la fase 3a.

Modos:
  fijo        ventanas de 1.100 caracteres con paso 900 (línea base de la fase 2)
  estructural respeta encabezados Markdown, marcas de página y párrafos; máx. 1.500 caracteres; fusiona fragmentos muy cortos
Cada fragmento lleva: doc, pagina, encabezado, texto (limpio, sirve para verificar citas) y ctx (prefijo de contexto derivado de
los metadatos del documento: título, tipo, área, segmento, vigencia). El contexto NO usa un LLM: es la versión «barata» del
contextual retrieval de Anthropic; la versión con LLM queda para la fase 3b.
"""
import re

MAXC, MINC = 1500, 350


def _limpiar(t):
    t = re.sub(r'[ \t]+', ' ', t)
    return t.strip()


def contexto(r):
    """Prefijo de contexto a partir de metadatos (se antepone al texto solo para indexar, no para verificar citas)."""
    partes = [r['titulo'], r['tipo_doc'].replace('_', ' '), r['area'].replace('_', ' '), r['segmento']]
    if r.get('periodo_fin'): partes.append('periodo ' + r['periodo_fin'])
    elif r.get('anio_documento'): partes.append(str(r['anio_documento']))
    if r['estado_vigencia'] in ('vencido', 'historico'): partes.append(r['estado_vigencia'])
    return ' | '.join(p for p in partes if p)


def fijo(t, size=1100, step=900):
    t = re.sub(r'<!-- página \d+ -->', ' ', t)
    t = re.sub(r'[ \t]+', ' ', t)
    return [dict(pagina=None, encabezado='', texto=t[i:i + size]) for i in range(0, len(t), step) if t[i:i + size].strip()]


def estructural(t):
    pagina, enc = None, ''
    bloques = []                      # (pagina, encabezado, texto)
    for par in re.split(r'\n\s*\n', t):
        m = re.match(r'\s*<!-- página (\d+) -->', par)
        if m:
            pagina = int(m.group(1)); par = par[m.end():]
        for sub in re.split(r'(?m)^(?=#{1,4} )', par):
            if not sub.strip(): continue
            h = re.match(r'#{1,4} +(.+)', sub)
            if h: enc = h.group(1).strip()[:100]
            bloques.append((pagina, enc, _limpiar(sub)))
    out, cur, cp, ce = [], '', None, ''
    for p, e, b in bloques:
        if cur and len(cur) + len(b) + 1 > MAXC:
            out.append(dict(pagina=cp, encabezado=ce, texto=cur)); cur, cp, ce = '', None, ''
        if not cur: cp, ce = p, e
        cur = (cur + '\n' + b).strip()
        while len(cur) > MAXC:               # bloque enorme (p. ej. tablas): trocear
            out.append(dict(pagina=cp, encabezado=ce, texto=cur[:MAXC])); cur = cur[MAXC - 150:]
    if cur.strip(): out.append(dict(pagina=cp, encabezado=ce, texto=cur))
    # fusionar fragmentos cortos con el anterior
    res = []
    for c in out:
        if res and len(c['texto']) < MINC and len(res[-1]['texto']) + len(c['texto']) < MAXC + 300:
            res[-1]['texto'] += '\n' + c['texto']
        else:
            res.append(c)
    return res


def chunk_corpus(rows, modo):
    out, vistos = [], set()
    for r in rows:
        if not (r['indexar'] and r['texto']): continue
        piezas = fijo(r['texto']) if modo == 'fijo' else estructural(r['texto'])
        ctx = contexto(r)
        for k, c in enumerate(piezas):
            h = (r['id'], c['texto'][:200])
            if h in vistos or len(c['texto']) < 40: continue     # repetidos dentro del mismo documento (carruseles del CMS)
            vistos.add(h)
            out.append(dict(cid=f"{r['id']}#{k}", doc=r['id'], pagina=c['pagina'], encabezado=c['encabezado'], texto=c['texto'], ctx=ctx))
    return out
