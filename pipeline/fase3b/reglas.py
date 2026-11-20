"""Reglas deterministas previas a la búsqueda (paso 3 del contrato, docs/CONTRATO-3B.md). No llaman a ningún proveedor ni al LLM.

  ESCALAR        quejas, reclamaciones, fraude → WhatsApp del banco (decisión de las directivas).
  CUENTA_PROPIA  el cliente pide un dato de SU producto (cuánto debe, su saldo, sus movimientos, su extracto, su cupo disponible, sus puntos…).
                 El asistente NO tiene conexión a las bases de datos de clientes, así que remite a la app, al portal transaccional y a las líneas
                 de atención. Es una integración futura posible (con autenticación del cliente): cuando exista, esta regla es el punto donde se
                 conectaría la consulta de cuenta, en vez de remitir.
Los números de las líneas salen del corpus (doc 083, Preguntas frecuentes, «¿Cómo consultar los valores a cancelar de mis productos?»).
`mensaje_cuenta(fragmentos)` comprueba que sigan ahí. Si el banco los cambia y ya no aparecen, devuelve un mensaje sin números.
Las preguntas generales («¿cómo consulto mi saldo?», «¿cuánto cuesta consultar el saldo en un cajero?») NO entran en la regla: las responde el ciclo normal.
Uso: python pipeline/fase3b/reglas.py --autoprueba     (incluye la medición de falsos positivos sobre todo el golden, si está disponible)"""
import json, os, re, sys

ESCALAR = re.compile(r'(?i)\b(me (robaron|hurtaron|estafaron|clonaron|hackearon|suplantaron|cobraron (de m[aá]s|sin autorizaci[oó]n|doble))|no reconozco (un |el |este )?(cargo|compra|movimiento|transacci[oó]n|retiro)|fui (v[ií]ctima|estafad[oa])|quiero (poner|presentar|interponer) (una )?(queja|reclamo|reclamaci[oó]n|denuncia)|tengo (una )?(queja|reclamo)|hicieron (una )?transferencia sin|clonaron mi|phishing|suplantaci[oó]n de identidad)')

_PROD = r'(tarjeta|cr[eé]dito|pr[eé]stamo|cuenta|cdt|leasing|hipoteca|rotativo|sobregiro|libranza|producto)'
CUENTA_PROPIA = re.compile(r'(?i)(' + '|'.join([
    r'\bcu[aá]nto (le )?debo\b',                                                        # «cuánto debo en mi tarjeta»
    r'\bcu[aá]nto me (falta|queda) (por )?pagar\b',
    r'\b(dime|dame|cu[aá]l es|cu[aá]nto es|consulta(me)?|revisa(me)?|mu[eé]strame|ver) (el |la |los |las )?(valor|saldo|deuda|cupo|movimientos|extracto|estado de cuenta|puntos)\b[^?]{0,25}\b(mi|mis) ' + _PROD + r's?\b',   # el producto es del cliente, no «de mi hermano»
    r'\b(dime|dame|cu[aá]l es|cu[aá]nto es|consulta(me)?|revisa(me)?|mu[eé]strame|ver) (mi|mis) (saldo|deuda|cupo disponible|movimientos|[uú]ltimos movimientos|extracto|estado de cuenta|puntos)\b',
    r'\bcu[aá]nto (dinero |plata )?tengo (en|disponible)\b',                            # «cuánto tengo en la cuenta»; no «cuánto tengo PARA pagar» (plazo)
    r'\bcu[aá]ntos puntos tengo\b',
    r'\b(con|seg[uú]n) (mi )?c[eé]dula\b[^?]{0,40}\b(saldo|deuda|debo|movimientos|cupo)\b',
    r'^\W*(y |cu[aá]l es )?mi (saldo|deuda)( actual| pendiente| total)?\W*$',             # el mensaje es solo «¿mi saldo?»
    r'\bcu[aá]ndo (vence|se vence|tengo que pagar|debo pagar) (la cuota de )?mi ' + _PROD,
]) + ')')

LINEAS = ['320 11 77', '895 92 56', '386 97 72', '231 77 00', '01 800 05 14652']
MSG_CUENTA = ('Por ahora no tengo acceso a la información de tus productos, así que no puedo consultar tu saldo, tu deuda ni tus movimientos. '
              'Puedes consultarlos en la aplicación o en el portal transaccional del Banco de Occidente, o en la línea de atención: Bogotá 320 11 77, '
              'Cali 895 92 56, Barranquilla 386 97 72, Medellín 231 77 00 y 01 800 05 14652 a nivel nacional [1]. Por seguridad, no compartas en este chat tus claves ni los números completos de tus productos.')
MSG_CUENTA_SIN_LINEAS = ('Por ahora no tengo acceso a la información de tus productos, así que no puedo consultar tu saldo, tu deuda ni tus movimientos. '
                         'Puedes consultarlos en la aplicación o en el portal transaccional del Banco de Occidente, o en sus líneas de atención. '
                         'Por seguridad, no compartas en este chat tus claves ni los números completos de tus productos.')


def fragmento_lineas(fragmentos):
    """El fragmento del corpus que respalda las líneas de atención (todas deben aparecer en él), o None."""
    for c in fragmentos:
        if c['doc'] == '083' and all(n in c['texto'] for n in LINEAS): return c
    return None


def es_cuenta_propia(texto): return bool(CUENTA_PROPIA.search(texto))


def _autoprueba():
    si = ['Mi cédula es [DOCUMENTO], ¿cuánto debo en mi tarjeta de crédito?', 'con mi cedula dime mi deuda de la tarjeta', '¿Cuál es mi saldo?', 'dame mis últimos movimientos',
          'cuanto tengo en la cuenta de ahorros', '¿cuántos puntos tengo?', 'muéstrame el extracto de mi tarjeta', '¿cuándo vence mi tarjeta de crédito?', 'Cuánto me falta por pagar del préstamo',
          'consultame el saldo de mi cuenta corriente', 'mi saldo?']
    no = ['¿Cómo consulto mi saldo?', '¿Cuánto cuesta consultar el saldo en un cajero?', 'no tenia plata en la corriente para la cuota de cuenta activa cuanto tengo para pagar el sobregiro',
          '¿Qué tasa tiene el CDT?', '¿Cuál es el cupo máximo de la tarjeta Visa Infinite?', '¿Dónde veo el extracto de la tarjeta?', '¿Cuál es el saldo de la cuenta de ahorros de mi hermano?',
          '¿Cuánto cuesta la cuota de manejo de mi tarjeta?', 'Me robaron la tarjeta']
    mal = [t for t in si if not es_cuenta_propia(t)] + [t for t in no if es_cuenta_propia(t)]
    for t in mal: print('  FALLA ·', t)
    print(f'  regla de cuenta propia: {len(si) - sum(not es_cuenta_propia(t) for t in si)}/{len(si)} detectadas, {sum(es_cuenta_propia(t) for t in no)}/{len(no)} falsos positivos')
    B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) + '/'
    fg = B + 'rag-bocc/golden/golden-v0.jsonl'
    if os.path.exists(fg):
        g = [json.loads(line) for line in open(fg)]
        qs = [(x['pregunta'], x['accion_esperada']) for x in g] + [(v, x['accion_esperada']) for x in g for v in x.get('variantes', [])]
        hits = [(q, a) for q, a in qs if es_cuenta_propia(q)]
        fp = [(q, a) for q, a in hits if a in ('responder', 'corregir_premisa', 'aclarar')]
        print(f'  golden: {len(hits)} de {len(qs)} preguntas entran en la regla; {len(fp)} esperaban una respuesta (falsos positivos)')
        for q, a in fp: print('    FP ·', a, '|', q)
        mal += fp
    fc = B + 'rag-bocc/corpus.jsonl'
    if os.path.exists(fc):
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fase3a'))
        from chunking import chunk_corpus
        f = fragmento_lineas(chunk_corpus([json.loads(line) for line in open(fc)], 'estructural'))
        print('  respaldo de las líneas de atención en el corpus:', f['cid'] if f else 'NO ENCONTRADO')
        if not f: mal.append('lineas')
    if mal: sys.exit(1)
    print('autoprueba aprobada')


if __name__ == '__main__' and '--autoprueba' in sys.argv: _autoprueba()
