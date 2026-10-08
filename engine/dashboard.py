"""Static HTML value dashboard. No JavaScript, opens in any browser."""
import html

CSS = """
body{font-family:Georgia,'Source Serif 4',serif;background:#FBFBF9;color:#131C2B;margin:0;padding:32px;line-height:1.5}
h1{font-family:Arial,sans-serif;font-size:22px;margin:0 0 4px}
h2{font-family:Arial,sans-serif;font-size:15px;margin:28px 0 8px;border-bottom:2px solid #131C2B;padding-bottom:4px}
.sub{color:#5A6472;font-size:14px;max-width:880px}
.note{background:#FFF7E8;border-left:3px solid #B4690E;padding:8px 12px;font-size:13px;margin:12px 0;max-width:880px}
.tiles{display:flex;flex-wrap:wrap;max-width:1000px}
.tile{border:1px solid #E4E2DA;background:#fff;padding:12px;width:205px;margin:0 10px 10px 0}
.tile b{display:block;font-family:Arial,sans-serif;font-size:22px;color:#1E5E46}
.tile span{font-size:12.5px;color:#5A6472}
table{border-collapse:collapse;font-size:12.5px;width:100%;max-width:1180px;background:#fff}
th,td{border:1px solid #E4E2DA;padding:5px 7px;text-align:left;vertical-align:top}
th{background:#F1F0EA;font-family:Arial,sans-serif}
.bar{height:10px;background:#1E5E46;display:inline-block}
.bad{color:#9B2C2C;font-weight:bold}.ok{color:#1E5E46}
"""


def _e(x):
    return html.escape(str(x))


def render(config, summary, results):
    s = summary
    cur = s["currency"]
    tiles = [
        ("%s%%" % s["straight_through_rate"], "straight-through (auto-resolved)"),
        ("%s%%" % s["human_review_rate"], "routed to a person by guardrails"),
        ("%s%%" % s["pending_rate"], "held for missing evidence"),
        ("%s%%" % s["auto_accuracy"] if s["auto_accuracy"] is not None else "n/a",
         "auto-decision accuracy vs human reference"),
        ("%s%%" % s["recommendation_agreement"] if s["recommendation_agreement"] is not None else "n/a",
         "agent recommendation matched reviewer"),
        ("%s to %s min" % (s["baseline_minutes_per_case"], s["agentic_minutes_per_case"]), "handling effort per case"),
        ("%s to %s days" % (s["baseline_days_to_resolve"], s["agentic_days_to_resolve"]), "time to resolve"),
        ("%s tokens" % s["avg_context_tokens_topk"], "grounded context per call (vs %s full corpus)" % s["full_corpus_tokens"]),
    ]
    out = ["<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>%s</title><style>%s</style></head><body>"
           % (_e(config["display_name"]), CSS)]
    out.append("<h1>%s</h1>" % _e(config["display_name"]))
    out.append("<p class='sub'>%s | %s | %s</p>" % (_e(config["industry"]), _e(config["process_family"]), _e(config["process_step"])))
    out.append("<p class='sub'>%s</p>" % _e(config["description"]))
    out.append("<div class='note'>Synthetic data. %d generated cases; the human reviewer is simulated from ground truth "
               "the way a UAT reference set would be. Value figures use the labelled assumptions below, not client data.</div>" % s["cases"])
    out.append("<h2>Outcome</h2><div class='tiles'>")
    for big, small in tiles:
        out.append("<div class='tile'><b>%s</b><span>%s</span></div>" % (_e(big), _e(small)))
    out.append("</div>")

    out.append("<h2>Why cases went to a person</h2><table><tr><th>Guardrail trigger</th><th>Cases</th><th></th></tr>")
    for k, v in sorted(s["trigger_counts"].items(), key=lambda kv: -kv[1]):
        out.append("<tr><td>%s</td><td>%d</td><td><span class='bar' style='width:%dpx'></span></td></tr>" % (_e(k), v, v * 12))
    out.append("</table>")

    vm = config["value_model"]
    out.append("<h2>Value case (annualized on assumptions)</h2>")
    out.append("<div class='note'>%s</div>" % _e(vm.get("_note", "")))
    out.append("<table><tr><th>Measure</th><th>Baseline (manual)</th><th>Agentic design</th></tr>")
    out.append("<tr><td>Effort per case (minutes)</td><td>%s</td><td>%s</td></tr>" % (s["baseline_minutes_per_case"], s["agentic_minutes_per_case"]))
    out.append("<tr><td>Days to resolve</td><td>%s</td><td>%s</td></tr>" % (s["baseline_days_to_resolve"], s["agentic_days_to_resolve"]))
    out.append("<tr><td>Annual volume (assumed)</td><td colspan='2'>%s cases</td></tr>" % "{:,}".format(s["annual_volume"]))
    out.append("<tr><td>Annual effort released</td><td colspan='2'>%s hours</td></tr>" % "{:,}".format(s["annual_hours_saved"]))
    out.append("<tr><td>Annual cost released at %s %s/hour</td><td colspan='2'>%s %s</td></tr>"
               % (cur, vm["cost_per_hour"], cur, "{:,}".format(s["annual_cost_saved"])))
    if s["invalid_amount_label"]:
        out.append("<tr><td>%s</td><td colspan='2'>%s %s</td></tr>" % (_e(s["invalid_amount_label"]), cur, "{:,.2f}".format(s["invalid_amount_sample"])))
    out.append("</table>")

    out.append("<h2>Case audit trail</h2><table><tr><th>Case</th><th>Amount</th><th>Text</th><th>Intake</th>"
               "<th>Route</th><th>Action</th><th>Cited clauses</th><th>Guardrail reasons</th><th>Check</th></tr>")
    for r in results:
        it = r["intake"]
        intake = "%s (%.2f)" % (it["category"], it["confidence"]) if it["category"] else "unclassified"
        cites = ", ".join(c["id"] for c in r["grounding"]["cited"]) if r.get("grounding") else "-"
        if r["route"] == "auto":
            chk = "<span class='ok'>correct</span>" if r["correct"] else "<span class='bad'>error</span>"
        elif r["route"] == "human":
            chk = "agent agreed" if r.get("agreed_with_agent") else ("no proposal" if not r.get("proposal") else "reviewer overrode")
        else:
            chk = "held"
        out.append("<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (
            _e(r["id"]), "{:,.2f}".format(r["amount"]), _e(r["text"]), _e(intake), _e(r["route"]),
            _e(r["final_action"]), _e(cites), _e("; ".join(r["reasons"]) or "-"), chk))
    out.append("</table></body></html>")
    return "\n".join(out)
