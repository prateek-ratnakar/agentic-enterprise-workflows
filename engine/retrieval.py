"""Tiny TF-IDF retriever used for RAG grounding. Standard library only.

In production this layer would be a vector store over the client's contracts,
policies and SOPs. The contract with the rest of the engine is the same: every
decision must cite clauses that were actually retrieved.
"""
import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("a an the and or of to in on for by with is are was were be been this that "
            "it as at from not no our we us per any all its their".split())


def tokenize(text):
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 1]


class Retriever:
    def __init__(self, clauses):
        self.clauses = clauses
        self.docs = [tokenize(c["title"] + " " + c["text"]) for c in clauses]
        n = len(self.docs)
        df = Counter()
        for doc in self.docs:
            df.update(set(doc))
        self.idf = {t: math.log((n + 1) / (d + 1)) + 1.0 for t, d in df.items()}
        self.vecs = [self._vec(doc) for doc in self.docs]

    def _vec(self, tokens):
        tf = Counter(tokens)
        vec = {t: (c / max(len(tokens), 1)) * self.idf.get(t, 0.0) for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def search(self, query, k=3):
        q = self._vec(tokenize(query))
        scored = []
        for clause, vec in zip(self.clauses, self.vecs):
            score = sum(w * vec.get(t, 0.0) for t, w in q.items())
            scored.append((round(score, 4), clause))
        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [{"score": s, "clause": c} for s, c in scored[:k]]
