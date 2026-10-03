"""Recuperación de la fase 3b = la configuración elegida en la fase 3a: BM25 + denso e5-small (RRF) → vigencia blanda → reranker Voyage rerank-3 (top-20).
Devuelve los fragmentos ordenados por puntaje del reranker. Las claves se leen solo del entorno (VOYAGE_API_KEY). `cache` (dict consulta → [(fragmento, puntaje)]) evita repetir llamadas pagas
(p. ej. el de pipeline/24_suficiencia.py: _raw/suficiencia/rerank3-dev.json)."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'fase3a'))
from chunking import chunk_corpus
from retrieval import BM25, rrf
from vigencia import doc_ok_blanda
import almacen, embed_api


class Recuperador:
    def __init__(self, base, cache=None, topk=20):
        self.B = base; self.topk = topk; self.cache = cache if cache is not None else {}
        self.filas = [json.loads(line) for line in open(base + 'rag-bocc/corpus.jsonl')]
        self.corpus = {r['id']: r for r in self.filas}
        self.ch = chunk_corpus(self.filas, 'estructural')
        self.bm = BM25([c['ctx'] + '\n' + c['texto'] for c in self.ch])
        self.E = almacen.cargar(base, 'e5-small', 'estructural', 1, self.ch)
        from sentence_transformers import SentenceTransformer
        self.mod = SentenceTransformer('intfloat/multilingual-e5-small', device='cpu')
        self.voyage = embed_api._clientes()['voyage']
        self.tokens_rerank = 0

    def buscar(self, q):
        """→ lista [(índice de fragmento, puntaje rerank-3)] de mayor a menor, tras vigencia blanda; [] si no hay candidatos."""
        if q in self.cache: return [tuple(x) for x in self.cache[q]]
        qv = self.mod.encode(['query: ' + q], normalize_embeddings=True)[0]
        s = self.E @ qv; top = np.argpartition(-s, 199)[:200]; top = top[np.argsort(-s[top])]
        den = [(int(i), float(s[i])) for i in top]
        cand = [i for i, _ in rrf([self.bm.search(q, 200), den], top=200) if doc_ok_blanda(self.corpus[self.ch[i]['doc']]['estado_vigencia'], q)][:self.topk]
        if not cand: self.cache[q] = []; return []
        r = embed_api._reintentar(lambda: self.voyage.rerank(q, [self.ch[i]['ctx'] + '\n' + self.ch[i]['texto'] for i in cand], model='rerank-3', truncation=True))
        self.tokens_rerank += r.total_tokens
        self.cache[q] = sorted(((cand[x.index], float(x.relevance_score)) for x in r.results), key=lambda z: -z[1])
        return self.cache[q]
