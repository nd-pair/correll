#!/usr/bin/env python3
"""Small Claude (Anthropic API) helper shared by the enrichment scripts.

Uses the official `anthropic` SDK. Authenticates from ANTHROPIC_API_KEY (a GitHub Actions
secret in CI, or your shell locally). Everything is best-effort: if no key is configured the
scripts skip the LLM step, so the site keeps its heuristic figures and simply shows no teasers.

Model defaults to claude-opus-5; override with CORRELL_LLM_MODEL. Thinking is disabled (these are
short, well-scoped calls) which keeps output tight and cost low; effort stays at the default.
"""
import base64, os

MODEL = os.environ.get("CORRELL_LLM_MODEL", "claude-opus-5")


class Unavailable(Exception):
    """No API key configured — skip LLM steps."""


class RateLimited(Exception):
    """Hit a 429 — stop for this run and save partial progress."""


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


_client = None


def _get_client():
    global _client
    if _client is None:
        if not available():
            raise Unavailable("ANTHROPIC_API_KEY not set")
        import anthropic
        _client = anthropic.Anthropic()
    return _client


def _run(content, system, max_tokens):
    import anthropic
    client = _get_client()
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            thinking={"type": "disabled"},
            system=system,
            messages=[{"role": "user", "content": content}],
        )
    except anthropic.RateLimitError as e:
        raise RateLimited(str(e))
    except anthropic.AuthenticationError as e:
        raise Unavailable(f"auth failed: {e}")
    if resp.stop_reason == "refusal":
        return ""
    return next((b.text for b in resp.content if b.type == "text"), "").strip()


def text(system, user, max_tokens=80):
    """Single text completion — returns the model's text (may be '')."""
    return _run(user, system, max_tokens)


def choose_image(prompt, png_list, max_tokens=8):
    """Show numbered images and return the model's chosen 1-based index (int), or None."""
    content = [{"type": "text", "text": prompt}]
    for i, png in enumerate(png_list, 1):
        content.append({"type": "text", "text": f"Candidate {i}:"})
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/png",
            "data": base64.b64encode(png).decode()}})
    ans = _run(content, "You compare figures and answer with a single number.", max_tokens)
    import re
    m = re.search(r"\d+", ans)
    return int(m.group()) if m else None
