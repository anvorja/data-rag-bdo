"""Métricas de recuperación sobre el golden set (solo preguntas con fuente)."""
import collections, json, os
from retrieval import toks

KS = (1, 3, 5, 10, 20)


def cubre(texto, cita):
    ct = set(toks(cita))
    return bool(ct) and len(ct & set(toks(texto))) / len(ct) >= 0.8


def cargar_golden(B, split):
    return [q for q in (json.loads(l) for l in open(B + 'rag-bocc/golden/golden-v0.jsonl')) if q['split'] == split]


class Evaluador:
    def __init__(self, chunks, golden):
        self.ch = chunks; self.gold = golden
        self.por_doc = collections.defaultdict(list)
        for i, c in enumerate(chunks): self.por_doc[c['doc']].append(i)
        self._rel = {}
        for q in golden:
            if not q['fuentes']: continue
            self._rel[q['id']] = [{i for i in self.por_doc.get(f['doc_id'], []) if cubre(chunks[i]['texto'], f['cita_literal'])} for f in q['fuentes']]

    def inalcanzables(self):
        return [qid for qid, sets in self._rel.items() if any(not s for s in sets)]

    def evaluar(self, buscar, con_variantes=True):
        """buscar(texto) -> lista [(idx_chunk, score)] ordenada. Devuelve dict de métricas por grupo."""
        acc = collections.defaultdict(collections.Counter)
        for q in self.gold:
            if not q['fuentes']: continue
            docs = {f['doc_id'] for f in q['fuentes']}
            consultas = [('pregunta', q['pregunta'])] + ([('variante', v) for v in q.get('variantes', [])] if con_variantes else [])
            for kind, texto in consultas:
                top = [i for i, _ in buscar(texto)][:max(KS)]
                rd = next((r for r, i in enumerate(top, 1) if self.ch[i]['doc'] in docs), None)
                rcs = [next((r for r, i in enumerate(top, 1) if i in s), None) for s in self._rel[q['id']]]
                rc = None if any(x is None for x in rcs) else max(rcs)
                for g in ('todos', f"tipo:{q['tipo']}", f"seg:{q['segmento']}"):
                    c = acc[(g, kind)]; c['n'] += 1
                    for k in KS:
                        c[f'doc@{k}'] += rd is not None and rd <= k
                        c[f'cita@{k}'] += rc is not None and rc <= k
                    c['mrr'] += 1 / rc if rc and rc <= 10 else 0
        out = {}
        for (g, kind), c in sorted(acc.items()):
            n = c['n']
            out[f'{g}|{kind}'] = dict(n=n, **{k: round(c[k] / n, 3) for k in c if k != 'n' and k != 'mrr'}, mrr=round(c['mrr'] / n, 3))
        return out
