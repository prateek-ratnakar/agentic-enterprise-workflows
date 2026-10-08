"""The four agent roles. Each has one job and a narrow contract.

IntakeAgent    classifies the case into a configured category, with confidence
EvidenceAgent  checks the category's evidence rules against case attributes
PolicyAgent    retrieves and cites the policy clauses that justify a decision
DecisionAgent  proposes the action and drafts a resolution note from citations

Agents never see ground truth. The orchestrator strips it before they run.
"""
import json
import re

from .llm import estimate_tokens


class IntakeAgent:
    def __init__(self, config, llm=None):
        self.categories = config["categories"]
        self.llm = llm

    def classify(self, case):
        text = case["text"].lower()
        scores = {}
        for cid, cat in self.categories.items():
            scores[cid] = sum(1 for kw in cat["keywords"] if kw in text)
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        top_id, top = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0
        if top == 0:
            result = {"category": None, "confidence": 0.0, "method": "keywords",
                      "rationale": "no category signal in case text"}
        else:
            conf = round(top / float(top + second), 2)
            result = {"category": top_id, "confidence": conf, "method": "keywords",
                      "rationale": "keyword hits %s" % dict((k, v) for k, v in ranked if v)}
        if self.llm is not None:
            result = self._llm_classify(case, result)
        return result

    def _llm_classify(self, case, fallback):
        allowed = list(self.categories.keys())
        system = ("You classify enterprise workflow cases. Reply with JSON only: "
                  '{"category": one of %s or null, "confidence": number 0-1}.' % allowed)
        try:
            raw = self.llm.complete(system, case["text"], max_tokens=60)
            data = json.loads(raw.strip().strip("`").replace("json", "", 1))
            cat = data.get("category")
            conf = float(data.get("confidence", 0))
            if cat is None or cat in allowed:
                return {"category": cat, "confidence": round(conf, 2), "method": "llm",
                        "rationale": "Claude classification"}
        except Exception as exc:  # any LLM failure falls back to the deterministic path
            fallback["rationale"] += " | llm fallback: %s" % type(exc).__name__
        return fallback


class EvidenceAgent:
    def __init__(self, config):
        self.categories = config["categories"]

    def check(self, case, category):
        attrs = case.get("attributes", {})
        rules = self.categories[category]["valid_if"]
        missing = [r for r in rules if attrs.get(r) is None]
        if missing:
            return {"status": "incomplete", "missing": missing, "failed": []}
        failed = [r for r in rules if attrs.get(r) is not True]
        return {"status": "invalid" if failed else "valid", "missing": [], "failed": failed}


class PolicyAgent:
    def __init__(self, config, retriever, k=3):
        self.categories = config["categories"]
        self.retriever = retriever
        self.k = k
        self.min_score = config["thresholds"]["min_grounding_score"]

    def ground(self, case, category):
        query = self.categories[category]["policy_query"] + " " + case["text"]
        hits = self.retriever.search(query, k=self.k)
        cited = [h for h in hits if h["clause"]["category"] == category and h["score"] >= self.min_score]
        context = " ".join(h["clause"]["text"] for h in hits)
        return {
            "retrieved_ids": [h["clause"]["id"] for h in hits],
            "cited": [{"id": h["clause"]["id"], "score": h["score"], "title": h["clause"]["title"]} for h in cited],
            "grounded": bool(cited),
            "context_tokens_topk": estimate_tokens(context),
        }


_CITE = re.compile(r"\[([A-Z0-9]+-[A-Z]+-\d+)\]")


class DecisionAgent:
    def __init__(self, config, llm=None):
        self.categories = config["categories"]
        self.llm = llm

    def propose(self, case, category, evidence, grounding):
        cat = self.categories[category]
        action = cat["on_valid"] if evidence["status"] == "valid" else cat["on_invalid"]
        cites = [c["id"] for c in grounding["cited"]]
        note = self._template_note(action, evidence, cites)
        if self.llm is not None and cites:
            note = self._llm_note(case, action, evidence, cites, note)
        return {"action": action, "outcome": evidence["status"], "note": note, "citations": cites}

    @staticmethod
    def _template_note(action, evidence, cites):
        basis = "all evidence conditions met" if evidence["status"] == "valid" else \
            "failed checks: %s" % ", ".join(evidence["failed"])
        refs = " ".join("[%s]" % c for c in cites)
        return "%s. Basis: %s. Policy: %s" % (action, basis, refs)

    def _llm_note(self, case, action, evidence, cites, fallback):
        system = ("Draft a two-sentence resolution note. Cite only these clause ids in square "
                  "brackets: %s. Do not invent facts." % cites)
        user = "Case: %s\nDecided action: %s\nEvidence status: %s" % (case["text"], action, evidence)
        try:
            draft = self.llm.complete(system, user, max_tokens=160)
            used = set(_CITE.findall(draft))
            if used and used.issubset(set(cites)):
                return draft.strip()
        except Exception:
            pass
        return fallback


def citations_in(note):
    return set(_CITE.findall(note))
