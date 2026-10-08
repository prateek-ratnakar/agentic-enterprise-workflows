"""Load and validate a workflow configuration folder."""
import json
import os

REQUIRED_KEYS = ["workflow_id", "display_name", "industry", "process_family",
                 "categories", "thresholds", "value_model"]


class ConfigError(ValueError):
    pass


def load_workflow(folder):
    """Return (config, clauses, cases) for a workflow folder."""
    def _read(name):
        with open(os.path.join(folder, name), "r", encoding="utf-8") as fh:
            return json.load(fh)

    config = _read("config.json")
    clauses = _read("policy_clauses.json")
    cases = _read("cases.json")
    validate(config, clauses, cases)
    return config, clauses, cases


def validate(config, clauses, cases):
    for key in REQUIRED_KEYS:
        if key not in config:
            raise ConfigError("config.json missing key: %s" % key)
    cat_names = set(config["categories"].keys())
    for cid, cat in config["categories"].items():
        for field in ("keywords", "valid_if", "on_valid", "on_invalid", "policy_query"):
            if field not in cat:
                raise ConfigError("category %s missing %s" % (cid, field))
    for clause in clauses:
        if clause.get("category") not in cat_names:
            raise ConfigError("clause %s tagged to unknown category" % clause.get("id"))
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ConfigError("duplicate case ids")
    return True
