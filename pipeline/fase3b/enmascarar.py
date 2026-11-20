"""Capa de enmascaramiento de datos personales (fase 3b, paso 2 del contrato). Se aplica al texto del cliente ANTES de enviarlo a cualquier proveedor (LLM, reranker, embeddings).
Obligatorio por cumplimiento: quitar nombres, cédulas y números de cuenta (docs/DECISIONES.md). Aquí también: tarjetas, claves/PIN/CVV/OTP, teléfonos, correos y direcciones.

Datos con formato: reglas (sin dependencias). NOMBRES: reglas con señal en la frase («me llamo…», «a nombre de…», «señor…») MÁS un reconocedor de entidades (spaCy es_core_news_md,
requirements-ml.txt) para nombres sueltos («Pedro Gómez quiere saber…»). El NER se filtra: solo nombres propios escritos con mayúscula inicial y que no aparecen en el corpus del banco
(productos, entidades, personas públicas). Sin spaCy instalado, la capa sigue funcionando solo con reglas (enmascarar(..., ner=False) fuerza ese modo). Nombres en minúscula («pedro gomez») no se detectan.

enmascarar(texto) → (texto_enmascarado, hallazgos). `hallazgos` solo trae el TIPO y la cuenta por tipo (nunca el valor), para poder registrar sin guardar datos personales.
Uso:  python pipeline/fase3b/enmascarar.py --autoprueba
"""
import os, re, sys, unicodedata

_NER = {}   # carga perezosa: {'nlp': modelo, 'vocab': frases en mayúscula del corpus}
def _sin_tildes(t): return ''.join(c for c in unicodedata.normalize('NFD', t.lower()) if unicodedata.category(c) != 'Mn')


TITULOS = re.compile(r'(?i)^(?:do[nñ]a|don|se[nñ]or(?:a|ita)?|sr\.?|sra\.?|doctora?|dra?\.?)\s+')

MONEDA = re.compile(r'(?i)(\$|cop\b|pesos?\b|millones?\b|mil\b|usd\b|d[oó]lares?\b|%|por ciento|cuotas?\b|meses\b|a[nñ]os\b)')
_N = r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+'
_NOMBRE = rf'{_N}(?:\s+(?:de\s+(?:la\s+|los\s+|las\s+)?|del\s+)?{_N}){{0,3}}'
PUBLICOS = {'8903002794', '890300279', '3186714836', '573186714836', '3164348887', '3125104844'}   # NIT del banco y WhatsApp publicados en el sitio: no son datos del cliente
ANIOS = re.compile(r'(?:(?:19|20)\d\d[ -]?)+')                                                      # «2025 2026» no es un número de cuenta
REGLAS = [   # (tipo, regex, grupo a enmascarar, prioridad por orden)
    ('CORREO', re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+'), 0),
    ('CLAVE', re.compile(r'(?i)\b(?:clave|contrase[nñ]a|pin|cvv2?|cvc|c[oó]digo de (?:seguridad|verificaci[oó]n)|otp|token|c[oó]digo)\b[^\d\n]{0,25}?(\d{3,8})\b'), 1),
    ('CUENTA', re.compile(r'(?i)\b(?:cuenta|ahorros|corriente|cta\.?|producto|obligaci[oó]n|pr[eé]stamo|cr[eé]dito)\b[^\d\n]{0,25}?((?:\d[ -]?){8,16})(?!\d)'), 1),
    ('DOCUMENTO', re.compile(r'(?i)\b(?:c[eé]dula(?: de ciudadan[ií]a| de extranjer[ií]a)?|c\.?\s?c\.?|t\.?\s?i\.?|c\.?\s?e\.?|nit|documento(?: de identidad)?|identificaci[oó]n|pasaporte)\b[^\d\n]{0,18}?(\d{1,3}(?:[. ]\d{3}){1,3}(?:-\d)?|\d{5,12}(?:-\d)?)(?!\d)'), 1),
    ('TELEFONO', re.compile(r'(?<!\d)(?:\+?57[\s-]?)?3\d{2}[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)'), 0),
    ('TELEFONO', re.compile(r'(?<!\d)\(?60\d\)?[\s-]?\d{7}(?!\d)'), 0),
    ('DIRECCION', re.compile(r'(?i)\b(?:calle|carrera|cra|kr|cl|avenida|av|diagonal|transversal|tv|circular)\.?\s*\d+[a-z]?(?:\s?(?:bis|sur|norte|este|oeste))?\s*(?:#|no\.?|n[°º]|-)\s*\d+[a-z]?(?:\s*-\s*\d+)?'), 0),
    ('NOMBRE', re.compile(rf'(?i:\b(?:me llamo|mi nombre es|mi nombre completo es|soy|habla con|a nombre de|titular|se[nñ]or(?:a|ita)?|sr\.?|sra\.?|do[nñ]a?|don|doctora?|dra?\.?)\s+)({_NOMBRE})'), 1),
]


def _luhn(d):
    s, par = 0, False
    for ch in reversed(d):
        n = int(ch)
        if par: n = n * 2 - 9 if n * 2 > 9 else n * 2
        s += n; par = not par
    return s % 10 == 0


def _cargar_ner():
    if 'nlp' in _NER: return _NER['nlp']
    try:
        import spacy; _NER['nlp'] = spacy.load('es_core_news_md', disable=['lemmatizer', 'parser'])
    except Exception: _NER['nlp'] = None
    base = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))) + '/rag-bocc/corpus.jsonl'
    voc, tit = set(), []
    if _NER['nlp'] and os.path.exists(base):
        import json
        for line in open(base):
            r = json.loads(line)
            tit += [r['titulo'], r.get('titulo_publico') or '', *re.findall(r'(?m)^#{1,4} +(.+)$', r['texto'])]
            for m in re.finditer(rf'{_N}(?:\s+(?:de\s+(?:la\s+)?|del\s+)?{_N}){{1,3}}', r['texto']):      # frases de 2+ palabras y todas sus subfrases
                w = m.group(0).lower().split()
                voc.update(' '.join(w[i:j]) for i in range(len(w)) for j in range(i + 2, len(w) + 1))
    _NER['titulos'] = _sin_tildes('\n'.join(tit))
    _NER['vocab'] = voc
    return _NER['nlp']


def _spans_ner(t):
    nlp = _cargar_ner()
    if not nlp: return []
    out = []
    t2 = re.sub(r'\b(?:[A-ZÁÉÍÓÚÑ]{3,}\s+)+[A-ZÁÉÍÓÚÑ]{3,}\b', lambda m: m.group(0).title(), t)     # tandas de 2+ palabras EN MAYÚSCULAS: el NER falla; se le pasan en formato título (misma longitud)
    for e in nlp(t2).ents:
        if e.label_ != 'PER': continue
        a, b = e.start_char, e.end_char; txt = t[a:b]
        m = TITULOS.match(txt)
        if m: a += m.end(); txt = t[a:b]
        pal = txt.split()
        if not pal or not all(p[:1].isupper() or p.lower() in ('de', 'del', 'la', 'los', 'las') for p in pal): continue     # escrito como nombre propio
        if '.' in txt or any(p.isupper() and len(p) <= 3 for p in pal): continue                              # abreviaturas (M.V., E.A., ACH)
        if txt.lower() in _NER['vocab'] or re.search(rf'(?<!\w){re.escape(_sin_tildes(txt))}(?!\w)', _NER['titulos']): continue   # producto, entidad o persona pública del corpus (títulos, encabezados, frases)
        out.append((a, b, 'NOMBRE'))
    return out


def _spans(t, ner=None):
    sp = []
    for tipo, rx, g in REGLAS:
        for m in rx.finditer(t):
            a, b = m.span(g)
            if tipo == 'NOMBRE' and re.fullmatch(r'(?i)(el|la|un|una|cliente|banco|occidente|usted|ustedes|quien|alguien|yo|me|mi)', m.group(g).strip()): continue
            dig = re.sub(r'\D', '', m.group(g))
            if tipo in ('CUENTA', 'DOCUMENTO', 'TELEFONO') and (dig in PUBLICOS or (dig[2:] if dig.startswith('57') and len(dig) == 12 else dig) in PUBLICOS or ANIOS.fullmatch(m.group(g).strip())): continue
            sp.append((a, b, tipo))
    for m in re.finditer(r'(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)', t):               # tarjeta: 13–19 dígitos con Luhn válido
        d = re.sub(r'\D', '', m.group(0))
        if 13 <= len(d) <= 19 and _luhn(d): sp.append((m.start(), m.end(), 'TARJETA'))
    for m in re.finditer(r'(?<![\d.,])(\d{9,16}|\d{1,2}(?:\.\d{3}){3,4})(?![\d]|[.,]\d)', t):    # número largo suelto: identificador probable si no parece un monto
        ctx = t[max(0, m.start() - 12):m.start()] + '|' + t[m.end():m.end() + 14]
        if not MONEDA.search(ctx) and re.sub(r'\D', '', m.group(0)) not in PUBLICOS: sp.append((m.start(), m.end(), 'NUMERO_PERSONAL'))
    if ner is not False: sp += _spans_ner(t)
    sp.sort(key=lambda x: (x[0], -(x[1] - x[0])))           # prioridad: el primero y el más largo; los solapados se descartan
    out, fin = [], -1
    for a, b, tipo in sp:
        if a >= fin: out.append((a, b, tipo)); fin = b
    return out


def enmascarar(texto, ner=None):
    """ner=None: usa el NER si spaCy está instalado; False: solo reglas."""
    out, ult, cuenta = [], 0, {}
    for a, b, tipo in _spans(texto, ner):
        out.append(texto[ult:a]); ult = b
        cuenta[tipo] = cuenta.get(tipo, 0) + 1
        out.append(f'[{tipo}]')
    out.append(texto[ult:])
    return ''.join(out), cuenta


def autoprueba():
    casos = [
        ('Mi cédula es 1.098.765.432 y quiero saber mi saldo', 'DOCUMENTO'), ('cc 52123456, ¿puedo abrir una cuenta?', 'DOCUMENTO'),
        ('número de cuenta 123-456789-01 de ahorros', 'CUENTA'), ('mi cuenta de ahorros 4567890123 no deja transferir', 'CUENTA'),
        ('mi tarjeta 4111 1111 1111 1111 fue bloqueada', 'TARJETA'), ('llámame al 310 555 1234', 'TELEFONO'), ('escríbeme a juan.perez@correo.com', 'CORREO'),
        ('mi clave es 4821 y no entra', 'CLAVE'), ('me llegó el código 482913, ¿lo digo?', 'CLAVE'), ('vivo en la Carrera 45 # 12-30 de Cali', 'DIRECCION'),
        ('Me llamo Carlos Andrés Borja y quiero un crédito', 'NOMBRE'), ('a nombre de María Fernanda López de la Cruz', 'NOMBRE'),
    ]
    for t, esp in casos:
        m, c = enmascarar(t); assert esp in c, (t, m, c)
    for t in ['Quiero un crédito de $30.000.000 a 60 meses', 'la tasa es 1,95% mensual', 'desde 30000000 pesos', 'Banco de Occidente Visa Infinite', 'cuánto cuesta la cuota de manejo de 19.900',
              'soy cliente del banco y quiero saber el cupo', 'el CDT desde 1.000.000 por 90 días']:
        m, c = enmascarar(t); assert not c and m == t, (t, m, c)
    print(f'autoprueba aprobada ({len(casos)} con datos, 7 sin datos)')


if __name__ == '__main__':
    if '--autoprueba' in sys.argv: autoprueba()
    else: print(__doc__)
