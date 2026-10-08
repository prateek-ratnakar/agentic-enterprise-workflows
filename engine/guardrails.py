"""Human-in-the-loop triggers. Each returns a reason string or None.

These encode where human judgment must stay in the loop: low confidence,
ungrounded decisions, high value, regulated or judgment-heavy categories, and
account-level flags. A case goes to a human if any trigger fires.
"""


def evaluate(config, case, intake, grounding=None):
    t = config["thresholds"]
    reasons = []
    if intake["category"] is None:
        reasons.append("unclassified: no category signal")
    elif intake["confidence"] < t["min_confidence"]:
        reasons.append("low confidence %.2f < %.2f" % (intake["confidence"], t["min_confidence"]))
    if intake["category"] in config.get("human_only_categories", []):
        reasons.append("human-only category: %s" % intake["category"])
    if case.get("amount", 0) > t["auto_max_amount"]:
        reasons.append("amount %s above auto limit %s" % (case["amount"], t["auto_max_amount"]))
    flags = set(case.get("flags", [])) & set(config.get("human_review_flags", []))
    if flags:
        reasons.append("account flag: %s" % ", ".join(sorted(flags)))
    if grounding is not None and not grounding["grounded"]:
        reasons.append("ungrounded: no policy clause cleared the grounding threshold")
    return reasons
