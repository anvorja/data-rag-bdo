"""Fase 3b · evaluación del ciclo completo (pregunta → respuesta con citas y avisos) sobre `dev` (167 preguntas + variantes coloquiales). NO usa el split `test`.
Mide: acción correcta (contra accion_esperada; escalar y abstenerse cuentan como «no responder»), cita correcta (el documento esperado o una versión equivalente está entre las citas),
corrección y respaldo de la respuesta (juez LLM deepseek-v4-pro, thinking desactivado, contra respuesta_referencia y los fragmentos citados), avisos de vigencia y comportamiento del verificador.
Uso: set -a; . ./.env; set +a; python pipeline/27_ciclo_completo.py [--max N] [--juez deepseek-v4-pro] [--sufijo -x] [--prompt-juez p1|p2] [--cache _raw/suficiencia/<archivo>.json]
Salida: rag-bocc/evaluacion/fase3b/ciclo-completo-dev<sufijo>.json (respuestas del asistente a preguntas sintéticas, sin datos personales)."""
import argparse, collections, json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3b')); sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3a'))
from asistente import Asistente
from evaluar import cargar_golden
import suficiencia

ap = argparse.ArgumentParser(); ap.add_argument('--max', type=int, default=0); ap.add_argument('--juez', default='deepseek-v4-pro'); ap.add_argument('--modelo', default='deepseek-flash'); ap.add_argument('--sufijo', default=''); ap.add_argument('--prompt-juez', default='p1', choices=['p1', 'p2'], help='prompt del juez de suficiencia (compuerta); p2 deja pasar las preguntas de premisa falsa')
ap.add_argument('--cache', default='_raw/suficiencia/rerank3-dev.json', help='caché de rerank-3 (relativo a la raíz); usar uno nuevo si cambió el corpus')
args = ap.parse_args()
B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
f_cache = B + args.cache; cache = json.load(open(f_cache)) if os.path.exists(f_cache) else {}
a = Asistente(B, modelo=args.modelo, prompt_juez=args.prompt_juez, cache_rerank=cache)
juez = suficiencia.cliente('deepseek', args.juez)
CLASE = {'responder': 'responder', 'corregir_premisa': 'responder', 'aclarar': 'aclarar', 'abstenerse': 'no_responder', 'escalar': 'no_responder'}
PJ = """Eres un evaluador estricto. Compara la RESPUESTA DEL ASISTENTE con la RESPUESTA DE REFERENCIA para la PREGUNTA, y revisa si lo que afirma está respaldado por los FRAGMENTOS CITADOS.
- "correcta": "si" si coincide en lo esencial con la referencia (datos y conclusión), "parcial" si acierta parte o le falta un dato importante, "no" si contradice o no responde lo pedido.
- "sin_respaldo": true si la respuesta afirma datos (cifras, condiciones) que NO están en los fragmentos citados.
Responde SOLO con JSON: {"correcta": "si|parcial|no", "sin_respaldo": true|false, "motivo": "una frase"}

PREGUNTA: %s
REFERENCIA: %s
RESPUESTA DEL ASISTENTE: %s
FRAGMENTOS CITADOS:
%s"""

dev = cargar_golden(B, 'dev')
items = [(q['pregunta'], q, 'pregunta') for q in dev] + [(v, q, 'variante') for q in dev if q['fuentes'] for v in q.get('variantes', [])]
if args.max: items = items[::max(1, len(items) // args.max)][:args.max]
print(len(items), 'casos', flush=True)


f_prev = B + f'rag-bocc/evaluacion/fase3b/ciclo-completo-dev{args.sufijo}.json'
previos = {(d['pregunta'], d['kind']): d for d in (json.load(open(f_prev))['detalle'] if os.path.exists(f_prev) else []) if 'error' not in d}    # reanudable: no se vuelve a pagar lo ya evaluado


def correr(it):
    texto, q, kind = it
    if (texto, kind) in previos: return previos[(texto, kind)]
    try: r = a.responder(texto)
    except Exception as ex: return dict(id=q['id'], tipo=q['tipo'], kind=kind, pregunta=texto, error=str(ex)[:200])
    esp = CLASE[q['accion_esperada']]; ok_acc = (r['accion'] in ('abstenerse', 'escalar') if esp == 'no_responder' else r['accion'] == esp)
    d = dict(id=q['id'], tipo=q['tipo'], kind=kind, pregunta=texto, esperada=q['accion_esperada'], accion=r['accion'], accion_ok=ok_acc, via=r['traza'].get('via'), respuesta=r['respuesta'],
             citas=[c['doc_id'] for c in r['citas']], avisos=r['avisos'], traza=r['traza'])
    if q['fuentes'] and r['accion'] == 'responder':
        docs = {x for f in q['fuentes'] for x in a.grupos.get(f['doc_id'], {f['doc_id']})}
        d['cita_ok'] = any(c in docs for c in d['citas'])
    if r['accion'] == 'responder' and esp == 'responder':
        frs = '\n\n'.join(f"[{c['n']}] " + a.rec.ch[next(i for i, x in enumerate(a.rec.ch) if x['cid'] == c['fragmento'])]['texto'] for c in r['citas'])
        ok, _ = True, None
        try:
            rr = juez[0].chat.completions.create(model=juez[1], messages=[{'role': 'user', 'content': PJ % (texto, q['respuesta_referencia'], r['respuesta'], frs)}], extra_body={'thinking': {'type': 'disabled'}}, response_format={'type': 'json_object'})
            d['juez'] = json.loads(rr.choices[0].message.content)
        except Exception as ex: d['juez'] = dict(correcta='error', sin_respaldo=None, motivo=str(ex)[:100])
    return d


t0 = time.time(); res = []
with ThreadPoolExecutor(4) as ex:
    for n, d in enumerate(ex.map(correr, items), 1):
        res.append(d)
        if n % 50 == 0: print(f'  {n}/{len(items)}', flush=True)
json.dump(cache, open(f_cache, 'w'))
ok = [d for d in res if 'error' not in d]


def tasa(xs, f): xs = list(xs); return (round(sum(1 for x in xs if f(x)) / len(xs), 3), len(xs)) if xs else (None, 0)


if len(res) - len(ok): print('ATENCIÓN:', len(res) - len(ok), 'casos con error (p. ej. saldo agotado, 402); vuelve a ejecutar para completar solo esos.')
out = dict(corpus_docs=len(a.rec.filas), cache=args.cache, prompt_juez=args.prompt_juez, modelo=args.modelo, juez=args.juez, casos=len(items), errores=len(res) - len(ok), segundos=round(time.time() - t0))
for kind in ('pregunta', 'variante', 'todos'):
    xs = [d for d in ok if kind == 'todos' or d['kind'] == kind]
    resp = [d for d in xs if d['esperada'] in ('responder', 'corregir_premisa')]
    out[kind] = dict(accion_correcta=tasa(xs, lambda d: d['accion_ok']),
                     responder_esperado=dict(responde=tasa(resp, lambda d: d['accion'] == 'responder'), cita_ok=tasa([d for d in resp if d['accion'] == 'responder' and 'cita_ok' in d], lambda d: d['cita_ok']),
                                             correcta_si=tasa([d for d in resp if d.get('juez')], lambda d: d['juez']['correcta'] == 'si'), correcta_si_o_parcial=tasa([d for d in resp if d.get('juez')], lambda d: d['juez']['correcta'] in ('si', 'parcial')),
                                             con_afirmaciones_sin_respaldo=tasa([d for d in resp if d.get('juez')], lambda d: d['juez']['sin_respaldo'] is True)),
                     abstencion_esperada=tasa([d for d in xs if d['esperada'] == 'abstenerse'], lambda d: d['accion'] in ('abstenerse', 'escalar')),
                     aclarar_esperado=tasa([d for d in xs if d['esperada'] == 'aclarar'], lambda d: d['accion'] == 'aclarar'))
vias = collections.Counter(d['via'] for d in ok); out['via'] = dict(vias)
out['verificador'] = dict(reintentos=sum(d['traza'].get('reintento', False) for d in ok), bloqueos_finales=sum(d['via'] == 'verificador' for d in ok),
                          problemas=dict(collections.Counter(p for d in ok for p in d['traza'].get('problemas', []))))
out['avisos'] = dict(respuestas_con_aviso=sum(1 for d in ok if d['avisos']), respuestas=sum(1 for d in ok if d['accion'] == 'responder'))
out['tokens_generador'] = sum(d['traza'].get('tokens_generador', 0) for d in ok); out['segundos_por_caso_mediana'] = sorted(d['traza']['segundos'] for d in ok)[len(ok) // 2]
out['tokens_rerank_nuevos'] = a.rec.tokens_rerank
print(json.dumps(out, ensure_ascii=False, indent=1))
json.dump(dict(resumen=out, detalle=res), open(B + f'rag-bocc/evaluacion/fase3b/ciclo-completo-dev{args.sufijo}.json', 'w'), ensure_ascii=False, indent=1)
