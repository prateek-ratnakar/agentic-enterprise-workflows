"""Optional Claude integration. The engine runs fully without it.

Set ANTHROPIC_API_KEY (and optionally CLAUDE_MODEL) and pass --llm to use Claude
for intake classification and for drafting the resolution note. Every LLM output
passes through the same guardrails as the deterministic path.
"""
import os


def llm_available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


class ClaudeClient:
    def __init__(self, model=None):
        import anthropic  # imported lazily so the core engine has no dependencies
        self._client = anthropic.Anthropic()
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-sonnet-5")

    def complete(self, system, user, max_tokens=400):
        msg = self._client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{"role": "user", "content": user}])
        return "".join(getattr(b, "text", "") for b in msg.content)


def estimate_tokens(text):
    """Rough token estimate (about 4 characters per token) for cost tracking."""
    return max(1, len(text) // 4)
