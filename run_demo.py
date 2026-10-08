"""Run one or all industry workflows and write dashboards and audit logs.

    python run_demo.py                  # all three workflows, deterministic
    python run_demo.py --workflow o2c_deductions
    python run_demo.py --llm            # use Claude if ANTHROPIC_API_KEY is set
"""
import argparse
import json
import os
import sys

from engine.config import load_workflow
from engine.pipeline import Pipeline
from engine.value import summarize
from engine import dashboard
from engine.llm import llm_available, ClaudeClient

HERE = os.path.dirname(os.path.abspath(__file__))
WORKFLOWS = ["o2c_deductions", "bfsi_collections", "s2p_invoice_exceptions"]


def run(workflow_id, llm=None, out_dir=None):
    config, clauses, cases = load_workflow(os.path.join(HERE, "workflows", workflow_id))
    pipe = Pipeline(config, clauses, llm=llm)
    results = pipe.run(cases)
    summary = summarize(config, results, pipe.full_corpus_tokens)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, workflow_id + "_dashboard.html"), "w", encoding="utf-8") as fh:
            fh.write(dashboard.render(config, summary, results))
        with open(os.path.join(out_dir, workflow_id + "_audit.json"), "w", encoding="utf-8") as fh:
            json.dump({"summary": summary, "cases": results}, fh, indent=1)
    return config, summary, results


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", choices=WORKFLOWS)
    ap.add_argument("--llm", action="store_true", help="use Claude for intake and notes")
    ap.add_argument("--out", default=os.path.join(HERE, "sample_outputs"))
    args = ap.parse_args(argv)
    llm = None
    if args.llm:
        if not llm_available():
            sys.exit("--llm needs ANTHROPIC_API_KEY set")
        llm = ClaudeClient()
    for wf in [args.workflow] if args.workflow else WORKFLOWS:
        config, s, _ = run(wf, llm, args.out)
        print("%-24s cases=%d auto=%s%% human=%s%% pending=%s%% auto_accuracy=%s%% agreement=%s%% "
              "effort %s->%s min" % (wf, s["cases"], s["straight_through_rate"], s["human_review_rate"],
                                     s["pending_rate"], s["auto_accuracy"], s["recommendation_agreement"],
                                     s["baseline_minutes_per_case"], s["agentic_minutes_per_case"]))


if __name__ == "__main__":
    main()
