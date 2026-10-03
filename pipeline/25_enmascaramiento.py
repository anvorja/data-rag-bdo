"""Fase 3b · mide la capa de enmascaramiento (pipeline/fase3b/enmascarar.py) con datos INVENTADOS (rag-bocc/evaluacion/fase3b/pii-sintetico.jsonl):
  - recall por grupo: fracción de secretos que NO sobreviven en el texto enmascarado (grupo «formato» = datos con formato claro; «dificil» = sin pista en la frase);
  - falsos positivos: textos benignos del conjunto sintético y TODAS las preguntas del golden (290 + variantes) que la capa modifica sin deber.
Salida: rag-bocc/evaluacion/fase3b/enmascaramiento.json. Los casos sintéticos son escritos por el proyecto: no sustituyen una prueba con mensajes reales anonimizados."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'fase3b'))
from enmascarar import enmascarar

B = os.environ.get('RAG_BASE', os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))) + '/'
casos = [json.loads(line) for line in open(B + 'rag-bocc/evaluacion/fase3b/pii-sintetico.jsonl')]
out = {}
for g in ('formato', 'dificil'):
    tot = ok = 0; fallos = []
    for c in (x for x in casos if x['grupo'] == g):
        m, _ = enmascarar(c['texto'])
        for s in c['secretos']:
            tot += 1
            if s in m: fallos.append(s)
            else: ok += 1
    out[g] = dict(secretos=tot, enmascarados=ok, recall=round(ok / tot, 3), no_detectados=fallos)
    print(g, out[g]['recall'], f'({ok}/{tot})', 'no detectados:', fallos)
ben = [c['texto'] for c in casos if c['grupo'] == 'benigno']
mal = [t for t in ben if enmascarar(t)[0] != t]
golden = [json.loads(line) for line in open(B + 'rag-bocc/golden/golden-v0.jsonl')]
textos = sorted({t for q in golden for t in [q['pregunta']] + q.get('variantes', [])})
mal_g = [t for t in textos if enmascarar(t)[0] != t]
out['falsos_positivos'] = dict(sinteticos=dict(n=len(ben), modificados=len(mal), ejemplos=mal), golden=dict(n=len(textos), modificados=len(mal_g), ejemplos=[(t, enmascarar(t)[0]) for t in mal_g[:15]]))
print('falsos positivos sintéticos:', len(mal), '/', len(ben), mal)
print('falsos positivos golden:', len(mal_g), '/', len(textos))
for t in mal_g[:15]: print('  ', t, '->', enmascarar(t)[0])
json.dump(out, open(B + 'rag-bocc/evaluacion/fase3b/enmascaramiento.json', 'w'), ensure_ascii=False, indent=1)
