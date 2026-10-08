"""Orchestrator: runs every case through intake, evidence, grounding, guardrails
and decision, then routes it to AUTO_RESOLVED, PENDING_INFO or HUMAN_REVIEW.

The human reviewer in this prototype is simulated from the synthetic ground
truth so the design can be measured the way a real UAT would be: agent
recommendations scored against human decisions.
"""
from . import guardrails
from . import state_machine as sm
from .agents import IntakeAgent, EvidenceAgent, PolicyAgent, DecisionAgent
from .llm import estimate_tokens
from .retrieval import Retriever


class Pipeline:
    def __init__(self, config, clauses, llm=None):
        self.config = config
        self.retriever = Retriever(clauses)
        self.intake = IntakeAgent(config, llm)
        self.evidence = EvidenceAgent(config)
        self.policy = PolicyAgent(config, self.retriever)
        self.decision = DecisionAgent(config, llm)
        self.full_corpus_tokens = estimate_tokens(" ".join(c["text"] for c in clauses))

    def run_case(self, case):
        public = dict((k, v) for k, v in case.items() if k != "truth")  # agents never see truth
        run = sm.CaseRun(case["id"])
        rec = {"id": case["id"], "amount": case.get("amount", 0), "text": case["text"],
               "flags": case.get("flags", []), "intake": None, "evidence": None,
               "grounding": None, "proposal": None, "reasons": [], "route": None,
               "final_action": None, "final_outcome": None}

        intake = self.intake.classify(public)
        rec["intake"] = intake
        if intake["category"] is None:
            rec["reasons"] = guardrails.evaluate(self.config, public, intake)
            run.move(sm.HUMAN_REVIEW, "guardrails", "; ".join(rec["reasons"]))
            return self._human(case, run, rec)

        cat = intake["category"]
        run.move(sm.CLASSIFIED, "intake_agent",
                 "%s (confidence %.2f)" % (cat, intake["confidence"]))
        ev = self.evidence.check(public, cat)
        rec["evidence"] = ev
        run.move(sm.EVIDENCE_CHECKED, "evidence_agent", ev["status"])
        grounding = self.policy.ground(public, cat)
        rec["grounding"] = grounding
        reasons = guardrails.evaluate(self.config, public, intake, grounding)
        rec["reasons"] = reasons

        if ev["status"] != "incomplete" and grounding["grounded"]:
            rec["proposal"] = self.decision.propose(public, cat, ev, grounding)

        if reasons:
            run.move(sm.HUMAN_REVIEW, "guardrails", "; ".join(reasons))
            return self._human(case, run, rec)
        if ev["status"] == "incomplete":
            run.move(sm.PENDING_INFO, "evidence_agent",
                     "requested: %s" % ", ".join(ev["missing"]))
            rec["route"] = "pending_info"
            rec["final_action"] = "Request missing evidence: %s" % ", ".join(ev["missing"])
            rec["audit"] = run.audit
            return rec
        run.move(sm.GROUNDED, "policy_agent", "cited %s" % grounding["cited"][0]["id"])
        prop = rec["proposal"]
        run.move(sm.AUTO_RESOLVED, "decision_agent", prop["action"])
        rec["route"] = "auto"
        rec["final_action"] = prop["action"]
        rec["final_outcome"] = prop["outcome"]
        rec["audit"] = run.audit
        return rec

    def _human(self, case, run, rec):
        """Simulated reviewer: decides from ground truth, as a UAT reference would."""
        truth = case["truth"]
        cat = self.config["categories"][truth["category"]]
        action = cat["on_valid"] if truth["outcome"] == "valid" else cat["on_invalid"]
        run.move(sm.RESOLVED_BY_HUMAN, "human_reviewer", action)
        rec["route"] = "human"
        rec["final_action"] = action
        rec["final_outcome"] = truth["outcome"]
        rec["agreed_with_agent"] = bool(rec["proposal"]) and rec["proposal"]["action"] == action
        rec["audit"] = run.audit
        return rec

    def run(self, cases):
        results = [self.run_case(c) for c in cases]
        truth = dict((c["id"], c["truth"]) for c in cases)
        for r in results:
            t = truth[r["id"]]
            if r["route"] == "auto":
                r["correct"] = (r["intake"]["category"] == t["category"] and r["final_outcome"] == t["outcome"])
            else:
                r["correct"] = None
            r["truth"] = t
        return results
