"""Explicit workflow states, legal transitions and an audit trail.

Every case moves through the same state graph regardless of industry. Illegal
transitions raise, so a design gap shows up as a failing test, not a silent
production behavior.
"""

RECEIVED = "RECEIVED"
CLASSIFIED = "CLASSIFIED"
EVIDENCE_CHECKED = "EVIDENCE_CHECKED"
GROUNDED = "GROUNDED"
AUTO_RESOLVED = "AUTO_RESOLVED"
PENDING_INFO = "PENDING_INFO"
HUMAN_REVIEW = "HUMAN_REVIEW"
RESOLVED_BY_HUMAN = "RESOLVED_BY_HUMAN"

TERMINAL = {AUTO_RESOLVED, PENDING_INFO, RESOLVED_BY_HUMAN}

TRANSITIONS = {
    RECEIVED: {CLASSIFIED, HUMAN_REVIEW},
    CLASSIFIED: {EVIDENCE_CHECKED, HUMAN_REVIEW},
    EVIDENCE_CHECKED: {GROUNDED, PENDING_INFO, HUMAN_REVIEW},
    GROUNDED: {AUTO_RESOLVED, HUMAN_REVIEW},
    HUMAN_REVIEW: {RESOLVED_BY_HUMAN},
    AUTO_RESOLVED: set(),
    PENDING_INFO: set(),
    RESOLVED_BY_HUMAN: set(),
}


class IllegalTransition(RuntimeError):
    pass


class CaseRun:
    def __init__(self, case_id):
        self.case_id = case_id
        self.state = RECEIVED
        self.audit = [{"state": RECEIVED, "actor": "system", "note": "case received"}]

    def move(self, new_state, actor, note):
        if new_state not in TRANSITIONS[self.state]:
            raise IllegalTransition("%s: %s -> %s" % (self.case_id, self.state, new_state))
        self.state = new_state
        self.audit.append({"state": new_state, "actor": actor, "note": note})

    @property
    def done(self):
        return self.state in TERMINAL
