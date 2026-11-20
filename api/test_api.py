"""Pruebas de la API del panel sin proveedores pagos: el reranker (Voyage) y el LLM se sustituyen por dobles deterministas.
Si están instalados openai y sentence-transformers, también se prueba el Asistente REAL (contrato, verificación, citas) con un LLM simulado.
Uso: python -m api.test_api          (desde la raíz; necesita rag-bocc/corpus.jsonl: python pipeline/20_reconstruir_corpus.py)"""
import json, os, sys, tempfile, types

os.environ['API_SIN_ARRANQUE'] = '1'
os.environ['REGISTRO_PRUEBAS'] = tempfile.mkdtemp(prefix='pruebas_api_')
from fastapi.testclient import TestClient
from api import app as A


class RecFalso:
    """Recuperador doble: devuelve los fragmentos del documento de tarifas vigente que contienen la comisión Shopify Pasarela (0,8 %)."""
    def __init__(self, svc):
        self.filas = svc.filas; self.corpus = {r['id']: r for r in svc.filas}
        self.ch = list(svc.fragmentos().values()); self.tokens_rerank = 0; self.consultas = []

    def buscar(self, q):
        self.consultas.append(q)
        if 'python' in q.lower(): return [(0, 0.2)]
        idx = [k for k, c in enumerate(self.ch) if 'shopify pasarela' in c['texto'].lower() and '0,8%' in c['texto'] and self.corpus[c['doc']]['estado_vigencia'] == 'vigente']
        return [(k, 0.9 - 0.01 * j) for j, k in enumerate(idx[:5])]


class AsisFalso:
    modelo = 'falso'
    def __init__(self, rec): self.rec = rec

    def responder(self, pregunta, sesion=None, limites=None):
        ok, motivo = limites.revisar(sesion, pregunta)
        if not ok: return dict(accion='abstenerse', respuesta=motivo, citas=[], avisos=[], traza=dict(via='limites'))
        limites.registrar(sesion, 'responder')
        return dict(accion='responder', respuesta='La comisión es 0,8 % [1].', citas=[], avisos=[], traza=dict(via='generador', enmascarado={'DOCUMENTO': 1}))


def _llm_falso(texto_json):
    """Cliente con la interfaz de openai mínima que usa el Asistente: chat.completions.create(...)."""
    msg = types.SimpleNamespace(content=texto_json, reasoning_content=None)
    r = types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)], usage=types.SimpleNamespace(total_tokens=100))
    return types.SimpleNamespace(chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=lambda **kw: r)))


def cliente(fabrica_asis):
    svc = A.Servicio()
    svc.fabrica_recuperador = lambda: RecFalso(svc)
    svc.fabrica_asistente = fabrica_asis
    return svc, TestClient(A.crear_app(svc))


def comprobar(cond, nombre):
    print(('  ok · ' if cond else '  FALLA · ') + nombre)
    if not cond: sys.exit(1)


def pruebas_basicas():
    svc, c = cliente(lambda rec: AsisFalso(rec))
    s = c.get('/api/salud').json(); comprobar(s['documentos_indexables'] > 900 and not s['recuperador_cargado'], 'salud sin cargar modelos')
    comprobar('806' not in svc.docs and c.get('/api/documentos/806').status_code == 404, 'el doc 806 (datos personales) no se sirve')
    sid = c.post('/api/sesiones').json()['sesion_id']
    comprobar(c.post('/api/chat', json=dict(sesion_id=sid, mensaje='hola')).status_code == 403, 'sin consentimiento no hay chat')
    comprobar(c.post('/api/chat', json=dict(sesion_id='nope', mensaje='hola')).status_code == 404, 'sesión inexistente')
    c.post(f'/api/sesiones/{sid}/consentimiento', json=dict(acepta=True))
    r = c.post('/api/chat', json=dict(sesion_id=sid, mensaje='Soy Pedro Pérez, cédula 1098765432, ¿cuánto cobra Shopify?')).json()
    comprobar(r['accion'] == 'responder' and r['turno_id'], 'turno de chat')
    reg = open(svc.registro + 'turnos.jsonl').read()
    comprobar('1098765432' not in reg and '[DOCUMENTO]' in reg, 'el registro guarda solo texto enmascarado')
    comprobar(c.post('/api/chat', json=dict(sesion_id=sid, mensaje='x' * 700)).json()['traza']['via'] == 'limites', 'límite de longitud')
    b = c.post('/api/buscar', json=dict(sesion_id=sid, consulta='comisión Shopify, mi cuenta 123456789012', k=2)).json()
    comprobar(len(b['resultados']) == 2 and all(x['estado_vigencia'] == 'vigente' for x in b['resultados']), 'búsqueda solo recuperación')
    comprobar('123456789012' not in svc.rec.consultas[-1], 'la consulta llega enmascarada al reranker')
    l = c.get('/api/documentos', params=dict(q='tarifas persona')).json()
    comprobar(l['total'] >= 1 and all(d['estado_vigencia'] != 'historico' for d in l['documentos']), 'catálogo oculta históricos por defecto')
    vig = next(d for d in l['documentos'] if 'tarifas persona' in d['titulo'].lower())
    d = c.get(f"/api/documentos/{vig['id']}").json()
    comprobar(len(d['versiones']) >= 2 and d['versiones'][0]['id'] == vig['id'] and d['n_fragmentos'] > 0, 'documento con su cadena de versiones')
    f = c.get(f"/api/documentos/{vig['id']}/fragmentos/0")
    comprobar(f.status_code == 200 and f.json()['texto'], 'fragmento citado')
    comprobar(c.post('/api/valoraciones', json=dict(sesion_id=sid, turno_id=r['turno_id'], util=True, correcta='si', comentario='bien, mi cédula 1098765432')).status_code == 200, 'valoración')
    comprobar('1098765432' not in open(svc.registro + 'valoraciones.jsonl').read(), 'el comentario se enmascara')
    comprobar(c.post('/api/valoraciones', json=dict(sesion_id=sid, turno_id='otro')).status_code == 404, 'valoración de un turno ajeno')
    comprobar(set(c.get('/api/documentos/filtros').json()) == {'segmento', 'area', 'estado', 'tipo'}, 'filtros')

    class Sin402(Exception): status_code = 402
    def falla(rec): raise Sin402()
    svc2, c2 = cliente(falla)
    sid2 = c2.post('/api/sesiones').json()['sesion_id']; c2.post(f'/api/sesiones/{sid2}/consentimiento', json=dict(acepta=True))
    e = c2.post('/api/chat', json=dict(sesion_id=sid2, mensaje='¿Cuánto cobra Shopify?'))
    comprobar(e.status_code == 503 and 'saldo' in e.json()['detail'], 'sin saldo del LLM → 503 con mensaje claro')
    comprobar(c2.get('/api/salud').json()['estado'] == 'degradado', 'salud degradada tras el fallo')


def prueba_asistente_real():
    try:
        import openai, sentence_transformers  # noqa: F401  (dependencias del Asistente real)
    except ImportError:
        print('  (omitida) prueba con el Asistente real: faltan openai o sentence-transformers'); return
    os.environ.setdefault('DEEPSEEK_API_KEY', 'prueba-sin-red')
    from asistente import Asistente
    def fab(rec):
        a = Asistente(A.B, recuperador=rec)
        a.cl = (_llm_falso(json.dumps(dict(accion='responder', respuesta='La comisión Shopify Pasarela es del 0,8 % más IVA [1].', citas_usadas=[1]))), 'falso')
        return a
    svc, c = cliente(fab)
    sid = c.post('/api/sesiones').json()['sesion_id']; c.post(f'/api/sesiones/{sid}/consentimiento', json=dict(acepta=True))
    r = c.post('/api/chat', json=dict(sesion_id=sid, mensaje='¿Cuánto cobra la pasarela Shopify?')).json()
    comprobar(r['accion'] == 'responder' and r['citas'] and r['citas'][0]['url'].startswith('https://'), 'Asistente real: citas puestas por el código')
    comprobar(r['traza']['via'] == 'generador' and not r['traza']['reintento'], 'Asistente real: la cifra 0,8 está respaldada')
    e = c.post('/api/chat', json=dict(sesion_id=sid, mensaje='Me robaron la tarjeta, quiero poner una queja')).json()
    comprobar(e['accion'] == 'escalar' and 'whatsapp' in e['respuesta'].lower(), 'Asistente real: escalamiento por reglas')
    k = c.post('/api/chat', json=dict(sesion_id=sid, mensaje='Mi cédula es 1098765432, ¿cuánto debo en mi tarjeta de crédito?')).json()
    comprobar(k['accion'] == 'escalar' and k['traza']['via'] == 'cuenta_propia' and '320 11 77' in k['respuesta'] and k['citas'] and k['citas'][0]['doc_id'] == '083',
              'Asistente real: cuenta propia → app, portal y líneas de atención, con cita al doc 083')
    g = c.post('/api/chat', json=dict(sesion_id=sid, mensaje='¿Cuánto cobra la pasarela Shopify si consulto mi saldo?')).json()
    comprobar(g['traza']['via'] != 'cuenta_propia', 'Asistente real: una pregunta general con «mi saldo» no entra en la regla')


if __name__ == '__main__':
    print('API del panel:'); pruebas_basicas(); prueba_asistente_real(); print('pruebas de la API aprobadas')
