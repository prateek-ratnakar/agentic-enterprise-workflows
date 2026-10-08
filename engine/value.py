"""Value model: baseline versus agentic handling, sample and annualized.

All baseline figures come from the workflow's config and are labelled as
assumptions. On a real engagement they are replaced by the client's measured
baseline before any business case is signed.
"""


_BUCKETS = [("unclassified", "Unclassified"), ("low confidence", "Low confidence"),
            ("human-only", "Human-only category"), ("amount", "Above auto-decision limit"),
            ("account flag", "Account flag"), ("ungrounded", "Ungrounded")]


def _bucket(reason):
    for prefix, label in _BUCKETS:
        if reason.startswith(prefix):
            return label
    return reason


def summarize(config, results, full_corpus_tokens):
    vm = config["value_model"]
    n = len(results)
    routes = {"auto": 0, "human": 0, "pending_info": 0}
    for r in results:
        routes[r["route"]] += 1
    auto = [r for r in results if r["route"] == "auto"]
    correct = [r for r in auto if r["correct"]]
    human = [r for r in results if r["route"] == "human"]
    with_rec = [r for r in human if r.get("proposal")]
    agreed = [r for r in with_rec if r.get("agreed_with_agent")]

    base_min = vm["manual_minutes_per_case"]
    ag_min_total = (routes["auto"] * vm["auto_minutes_per_case"] +
                    routes["human"] * vm["assisted_minutes_per_case"] +
                    routes["pending_info"] * vm["pending_minutes_per_case"])
    ag_min = ag_min_total / float(n)
    base_days = vm["manual_days_to_resolve"]
    ag_days = (routes["auto"] * vm["auto_days_to_resolve"] +
               routes["human"] * vm["assisted_days_to_resolve"] +
               routes["pending_info"] * vm["pending_days_to_resolve"]) / float(n)
    annual = vm["annual_volume"]
    hours_saved = annual * (base_min - ag_min) / 60.0
    cost_saved = hours_saved * vm["cost_per_hour"]

    invalid_amount = sum(r["amount"] for r in results
                         if r["route"] in ("auto", "human") and r["final_outcome"] == "invalid")
    reasons = {}
    for r in results:
        for reason in r["reasons"]:
            label = _bucket(reason)
            reasons[label] = reasons.get(label, 0) + 1
    topk = [r["grounding"]["context_tokens_topk"] for r in results if r.get("grounding")]
    avg_topk = sum(topk) / float(len(topk)) if topk else 0

    return {
        "cases": n,
        "routes": routes,
        "straight_through_rate": round(100.0 * routes["auto"] / n, 1),
        "human_review_rate": round(100.0 * routes["human"] / n, 1),
        "pending_rate": round(100.0 * routes["pending_info"] / n, 1),
        "auto_accuracy": round(100.0 * len(correct) / len(auto), 1) if auto else None,
        "auto_errors": [r["id"] for r in auto if not r["correct"]],
        "recommendation_agreement": round(100.0 * len(agreed) / len(with_rec), 1) if with_rec else None,
        "baseline_minutes_per_case": base_min,
        "agentic_minutes_per_case": round(ag_min, 1),
        "baseline_days_to_resolve": base_days,
        "agentic_days_to_resolve": round(ag_days, 1),
        "annual_volume": annual,
        "annual_hours_saved": int(round(hours_saved)),
        "annual_cost_saved": int(round(cost_saved)),
        "currency": config.get("currency", "USD"),
        "invalid_amount_label": vm.get("invalid_amount_label"),
        "invalid_amount_sample": round(invalid_amount, 2),
        "trigger_counts": reasons,
        "avg_context_tokens_topk": int(round(avg_topk)),
        "full_corpus_tokens": full_corpus_tokens,
    }
