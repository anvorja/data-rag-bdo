"""Componentes de recuperación para la fase 3a: BM25 propio, búsqueda densa, fusión RRF y reranker."""
import collections, math, re, unicodedata
import numpy as np

STOP = set('de la el en y los las que del con por para una un se su al es lo como mas sus este esta son entre a o u e sin sobre ser tu te mi me si no ni ya hay'.split())


def nacc(s): return unicodedata.normalize('NFKD', s.lower()).encode('ascii', 'ignore').decode()
def toks(s): return [t for t in re.findall(r'\w+', nacc(s)) if len(t) > 1 and t not in STOP]


class BM25:
    def __init__(self, textos, k1=1.5, b=0.75):
        self.k1, self.b = k1, b
        self.inv = collections.defaultdict(list); self.dl = []; self.df = collections.Counter()
        for i, t in enumerate(textos):
            tk = toks(t); self.dl.append(len(tk))
            for w, n in collections.Counter(tk).items():
                self.inv[w].append((i, n)); self.df[w] += 1
        self.N = len(textos); self.avg = sum(self.dl) / max(1, self.N)

    def scores(self, q):
        sc = collections.defaultdict(float)
        for w in set(toks(q)):
            if w not in self.inv: continue
            idf = math.log(1 + (self.N - self.df[w] + 0.5) / (self.df[w] + 0.5))
            for i, n in self.inv[w]:
                sc[i] += idf * n * (self.k1 + 1) / (n + self.k1 * (1 - self.b + self.b * self.dl[i] / self.avg))
        return sc

    def search(self, q, k=100):
        sc = self.scores(q)
        top = sorted(sc, key=lambda i: -sc[i])[:k]
        return [(i, sc[i]) for i in top]


class Densa:
    def __init__(self, matriz, modelo):
        self.m = matriz; self.modelo = modelo; self.prefijo = 'query: ' if 'e5' in getattr(modelo, '_nombre', '') else ''

    def search(self, q, k=100):
        v = self.modelo.encode([self.prefijo + q], normalize_embeddings=True)[0]
        s = self.m @ v
        top = np.argpartition(-s, min(k, len(s) - 1))[:k]
        top = top[np.argsort(-s[top])]
        return [(int(i), float(s[i])) for i in top]


def rrf(listas, k=60, top=100):
    sc = collections.defaultdict(float)
    for lst in listas:
        for r, (i, _) in enumerate(lst, 1): sc[i] += 1.0 / (k + r)
    return sorted(((i, s) for i, s in sc.items()), key=lambda x: -x[1])[:top]
