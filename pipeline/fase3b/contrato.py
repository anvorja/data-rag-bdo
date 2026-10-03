"""Contrato de la fase 3b: formato de la respuesta del asistente y verificaciones DETERMINISTAS posteriores a la generación.
Ver docs/CONTRATO-3B.md. Es independiente del LLM (DeepSeek u OpenAI): el modelo solo devuelve JSON con números de fragmento;
las URL, los títulos, las fechas y los avisos de vigencia los pone este código a partir del corpus, nunca el modelo.

Uso:  python pipeline/fase3b/contrato.py --autoprueba      (comprueba el corpus real y casos sintéticos)
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fase3a'))
from vigencia import aviso, grupos_version, intencion_temporal

WHATSAPP = {'texto': '+57 318 671 4836', 'url': 'https://api.whatsapp.com/send?phone=573186714836'}   # por confirmar que sea el de quejas/fraude/reclamaciones
ACCIONES = {'responder', 'abstenerse', 'escalar', 'aclarar'}


def cargar_corpus(base):
    rows = [json.loads(l) for l in open(base + 'rag-bocc/corpus.jsonl')]
    return {r['id']: r for r in rows}, rows


def construir_citas(usados, corpus):
    """usados: lista de fragmentos presentados al LLM, en orden (dicts con doc, pagina, encabezado, cid). Devuelve las citas numeradas desde 1."""
    citas = []
    for n, c in enumerate(usados, 1):
        d = corpus[c['doc']]
        citas.append(dict(n=n, doc_id=d['id'], url=d['url'], titulo=d.get('titulo_publico') or d['titulo'], pagina=c.get('pagina'),
                          encabezado=c.get('encabezado') or None, fragmento=c['cid'], estado_vigencia=d['estado_vigencia'],
                          vigente_hasta=d.get('vigente_hasta'), aviso=aviso(d)))
    return citas


def _numeros(t):
    """Cifras de un texto como cadenas de dígitos (1.500.000 → 1500000, 2,5 % → 25); heurística para comprobar que no se inventan valores."""
    return {re.sub(r'\D', '', m) for m in re.findall(r'\d[\d.,]*', t)} - {''}


def verificar(resp, citas, fragmentos, corpus, grupos=None, pregunta=''):
    """Revisa una respuesta ya generada. resp: dict con accion, respuesta, citas_usadas (lista de n). fragmentos: {n: texto} de lo presentado al LLM.
    Devuelve lista de problemas (vacía = aprobada). Cada problema es (codigo, detalle)."""
    p = []
    acc = resp.get('accion')
    if acc not in ACCIONES: return [('accion_invalida', str(acc))]
    usadas = resp.get('citas_usadas') or []
    if acc == 'responder':
        if not usadas: p.append(('sin_citas', 'una respuesta debe citar al menos un fragmento'))
        for n in usadas:
            if n not in fragmentos: p.append(('cita_inexistente', f'[{n}] no estaba en el contexto'))
        base = ' '.join(fragmentos.get(n, '') for n in usadas)
        sobran = _numeros(resp.get('respuesta', '')) - _numeros(base) - _numeros(pregunta) - {str(k) for k in range(1, 11)}
        if sobran: p.append(('cifra_no_respaldada', ', '.join(sorted(sobran))))
        if re.search(r'https?://|www\.', resp.get('respuesta', '')):
            ok = {c['url'] for c in citas} | {WHATSAPP['url']}
            for u in re.findall(r'https?://[^\s)>\]]+', resp['respuesta']):
                if u.rstrip('.,;') not in ok: p.append(('url_ajena', u))
        if grupos and not intencion_temporal(pregunta):
            for c in citas:
                if c['n'] in usadas and c['estado_vigencia'] == 'historico':
                    nuevas = [i for i in grupos[c['doc_id']] if corpus[i]['estado_vigencia'] != 'historico']
                    if nuevas: p.append(('version_antigua', f"{c['doc_id']} es histórico; hay versión vigente {nuevas[0]}"))
    elif acc == 'escalar':
        if WHATSAPP['url'] not in resp.get('respuesta', ''): p.append(('escalamiento_sin_whatsapp', ''))
    elif usadas: p.append(('citas_sin_responder', f'acción {acc} no debe traer citas'))
    return p


def autoprueba(base):
    corpus, rows = cargar_corpus(base)
    ind = [r for r in rows if r['indexar']]
    malos = [r['id'] for r in ind if not r['url'].startswith('https://')]
    assert not malos, f'URL sin https: {malos[:5]}'
    ajenos = [r['id'] for r in ind if not re.match(r'https://([\w-]+\.)*bancodeoccidente\.com\.co(/|$)', r['url'])]
    sin_titulo = [r['id'] for r in ind if not (r.get('titulo_publico') or r['titulo'])]
    assert not sin_titulo, sin_titulo[:5]
    print(f'corpus: {len(ind)} documentos indexables, todos con https y título para mostrar; {len(ajenos)} están en dominios de terceros (aliados, entes oficiales): se citan con su URL pero el asistente debe presentarlos como fuente externa')
    g = grupos_version(rows)
    hist = next(r for r in ind if r['estado_vigencia'] == 'historico' and any(corpus[i]['estado_vigencia'] != 'historico' for i in g[r['id']]))
    ven = next(r for r in ind if r['estado_vigencia'] == 'vencido')
    def ch(d, k=1): return dict(doc=d['id'], cid=f"{d['id']}#{k}", pagina=2, encabezado='Tarifas')
    citas = construir_citas([ch(ven), ch(hist)], corpus)
    frag = {1: 'La cuota de manejo es $19.900 mensuales', 2: 'Tasa 2,5 % mensual'}
    casos = [
        ('aprobada', dict(accion='responder', respuesta='La cuota es $19.900 [1].', citas_usadas=[1]), 'cuánto cuesta la cuota', []),
        ('sin citas', dict(accion='responder', respuesta='Cuesta mucho.', citas_usadas=[]), '', ['sin_citas']),
        ('cita inexistente', dict(accion='responder', respuesta='x [9]', citas_usadas=[9]), '', ['cita_inexistente']),
        ('cifra inventada', dict(accion='responder', respuesta='La cuota es $29.900 [1].', citas_usadas=[1]), '', ['cifra_no_respaldada']),
        ('url inventada', dict(accion='responder', respuesta='Mira https://falso.com/x [1] $19.900', citas_usadas=[1]), '', ['url_ajena']),
        ('versión antigua', dict(accion='responder', respuesta='Tasa 2,5 % [2]', citas_usadas=[2]), 'qué tasa tiene', ['version_antigua']),
        ('versión antigua con intención temporal', dict(accion='responder', respuesta='Tasa 2,5 % [2]', citas_usadas=[2]), 'qué tasa tenía en 2024', []),
        ('escalar sin WhatsApp', dict(accion='escalar', respuesta='Contacte al banco.', citas_usadas=[]), '', ['escalamiento_sin_whatsapp']),
        ('acción inválida', dict(accion='inventar'), '', ['accion_invalida']),
    ]
    for nombre, resp, preg, esp in casos:
        got = [c for c, _ in verificar(resp, citas, frag, corpus, g, preg)]
        assert got == esp, f'{nombre}: esperado {esp}, obtenido {got}'
        print(f'  ok · {nombre}')
    print('autoprueba aprobada')


if __name__ == '__main__':
    if '--autoprueba' in sys.argv:
        autoprueba(os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) + '/')
    else: print(__doc__)
