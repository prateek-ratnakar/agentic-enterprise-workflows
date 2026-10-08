"""Run with: python -m unittest discover -s tests -v"""
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, ROOT)

from engine.config import load_workflow, validate, ConfigError  # noqa: E402
from engine.pipeline import Pipeline  # noqa: E402
from engine.value import summarize  # noqa: E402
from engine.agents import citations_in  # noqa: E402
from engine import state_machine as sm  # noqa: E402

WORKFLOWS = ["o2c_deductions", "bfsi_collections", "s2p_invoice_exceptions"]


def load(wf):
    return load_workflow(os.path.join(ROOT, "workflows", wf))


class EngineTests(unittest.TestCase):
    def test_every_case_reaches_a_terminal_state(self):
        for wf in WORKFLOWS:
            config, clauses, cases = load(wf)
            for r in Pipeline(config, clauses).run(cases):
                self.assertIn(r["route"], ("auto", "human", "pending_info"), wf)
                self.assertIn(r["audit"][-1]["state"], sm.TERMINAL, wf)

    def test_agents_never_see_ground_truth(self):
        config, clauses, cases = load("o2c_deductions")
        pipe = Pipeline(config, clauses)
        seen = []
        original = pipe.intake.classify
        pipe.intake.classify = lambda case: (seen.append(case), original(case))[1]
        pipe.run(cases[:5])
        self.assertTrue(all("truth" not in c for c in seen))

    def test_human_only_categories_never_auto_resolve(self):
        for wf in ("bfsi_collections", "s2p_invoice_exceptions"):
            config, clauses, cases = load(wf)
            human_only = set(config["human_only_categories"])
            for r in Pipeline(config, clauses).run(cases):
                if r["intake"]["category"] in human_only:
                    self.assertEqual(r["route"], "human", r["id"])

    def test_amount_above_limit_goes_to_a_person(self):
        config, clauses, cases = load("o2c_deductions")
        case = copy.deepcopy(cases[0])
        case["amount"] = config["thresholds"]["auto_max_amount"] + 1
        r = Pipeline(config, clauses).run([case])[0]
        self.assertEqual(r["route"], "human")

    def test_ungrounded_decision_goes_to_a_person(self):
        config, clauses, cases = load("o2c_deductions")
        config = copy.deepcopy(config)
        config["thresholds"]["min_grounding_score"] = 0.99
        case = next(c for c in cases if not c["flags"] and c["amount"] < 1000)
        r = Pipeline(config, clauses).run([case])[0]
        self.assertEqual(r["route"], "human")

    def test_auto_decisions_cite_only_retrieved_clauses(self):
        for wf in WORKFLOWS:
            config, clauses, cases = load(wf)
            for r in Pipeline(config, clauses).run(cases):
                if r["route"] == "auto":
                    cited = citations_in(r["proposal"]["note"])
                    self.assertTrue(cited, r["id"])
                    self.assertTrue(cited.issubset(set(r["grounding"]["retrieved_ids"])), r["id"])

    def test_illegal_transition_raises(self):
        run = sm.CaseRun("X")
        with self.assertRaises(sm.IllegalTransition):
            run.move(sm.AUTO_RESOLVED, "test", "skip steps")

    def test_value_summary_is_consistent(self):
        for wf in WORKFLOWS:
            config, clauses, cases = load(wf)
            pipe = Pipeline(config, clauses)
            s = summarize(config, pipe.run(cases), pipe.full_corpus_tokens)
            self.assertEqual(sum(s["routes"].values()), s["cases"])
            self.assertLess(s["agentic_minutes_per_case"], s["baseline_minutes_per_case"])
            self.assertLess(s["avg_context_tokens_topk"], s["full_corpus_tokens"])

    def test_config_validation_catches_bad_clause(self):
        config, clauses, cases = load("s2p_invoice_exceptions")
        bad = copy.deepcopy(clauses)
        bad[0]["category"] = "not_a_category"
        with self.assertRaises(ConfigError):
            validate(config, bad, cases)

    def test_runs_are_deterministic(self):
        config, clauses, cases = load("bfsi_collections")
        a = [r["route"] for r in Pipeline(config, clauses).run(cases)]
        b = [r["route"] for r in Pipeline(config, clauses).run(cases)]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
