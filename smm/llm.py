"""LLM providers that cost $0.

- claude_code : your existing Claude subscription, run headless through the Claude Code CLI
                (`claude -p`). Auth: CLAUDE_CODE_OAUTH_TOKEN from `claude setup-token`.
                Usage counts against your plan's normal usage limits.
- gemini      : Google AI Studio free tier (GEMINI_API_KEY). Free-tier prompts may be used by
                Google to improve its products, so never send private customer data through it.
- fake        : deterministic responses for tests.

Every agent calls `llm.complete_json(system, prompt, schema)` and gets a dict back.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
import time

import requests

from .config import Config, env


class LLMError(RuntimeError):
    pass


def extract_json(text: str) -> dict:
    """Parse a JSON object out of model text (tolerates ``` fences and chatter)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError as exc:
                raise LLMError(f"Model did not return valid JSON: {exc}") from exc
        raise LLMError("Model did not return JSON")


def _with_schema(prompt: str, schema: dict) -> str:
    return (
        f"{prompt}\n\nReturn ONLY a JSON object (no prose, no code fences) matching this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False)}"
    )


class ClaudeCodeLLM:
    name = "claude_code"

    def __init__(self, model: str | None = None, timeout: int = 600):
        self.bin = env("CLAUDE_BIN") or shutil.which("claude") or "claude"
        self.model = model
        self.timeout = timeout

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        cmd = [
            self.bin, "-p",
            "--output-format", "json",
            "--tools", "",                     # pure text generation, no tool use
            "--no-session-persistence",
            "--system-prompt", system,
            "--json-schema", json.dumps(schema),
        ]
        if self.model:
            cmd += ["--model", self.model]
        # Run from an empty temp dir so no project files/CLAUDE.md leak into the context.
        with tempfile.TemporaryDirectory() as tmp:
            try:
                proc = subprocess.run(
                    cmd, input=_with_schema(prompt, schema), capture_output=True,
                    text=True, timeout=self.timeout, cwd=tmp,
                )
            except FileNotFoundError as exc:
                raise LLMError("Claude Code CLI not found. Install: npm install -g @anthropic-ai/claude-code") from exc
            except subprocess.TimeoutExpired as exc:
                raise LLMError("Claude Code timed out") from exc
        if proc.returncode != 0 and not proc.stdout.strip():
            raise LLMError(f"Claude Code failed: {proc.stderr.strip()[:500]}")
        try:
            data = json.loads(proc.stdout)
        except json.JSONDecodeError:
            return extract_json(proc.stdout)
        if data.get("is_error"):
            raise LLMError(f"Claude Code error: {str(data.get('result'))[:500]}")
        structured = data.get("structured_output")
        if isinstance(structured, dict):
            return structured
        return extract_json(str(data.get("result", "")))


class GeminiLLM:
    name = "gemini"
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str | None = None, timeout: int = 180):
        self.api_key = api_key
        self.model = model or "gemini-flash-latest"
        self.timeout = timeout

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": _with_schema(prompt, schema)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.8},
        }
        last = ""
        for attempt in range(4):
            resp = requests.post(
                self.URL.format(model=self.model), json=body, timeout=self.timeout,
                headers={"x-goog-api-key": self.api_key},
            )
            if resp.status_code in (429, 500, 503):  # free-tier rate limit / overload: back off
                last = resp.text[:300]
                time.sleep(15 * (attempt + 1))
                continue
            if resp.status_code >= 400:
                raise LLMError(f"Gemini {resp.status_code}: {resp.text[:500]}")
            data = resp.json()
            try:
                text = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError) as exc:
                raise LLMError(f"Gemini returned no text: {str(data)[:300]}") from exc
            return extract_json(text)
        raise LLMError(f"Gemini rate-limited: {last}")


class FallbackLLM:
    """Try the primary provider, fall back to the secondary on any error."""

    def __init__(self, primary, secondary):
        self.primary, self.secondary = primary, secondary
        self.name = f"{primary.name}+{secondary.name}"

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        try:
            return self.primary.complete_json(system, prompt, schema)
        except LLMError:
            return self.secondary.complete_json(system, prompt, schema)


class FakeLLM:
    """Test double: `responder(system, prompt, schema) -> dict`."""
    name = "fake"

    def __init__(self, responder):
        self.responder = responder
        self.calls: list[tuple[str, str]] = []

    def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        self.calls.append((system, prompt))
        return self.responder(system, prompt, schema)


def _provider(name: str):
    if name == "claude_code":
        return ClaudeCodeLLM(model=env("CLAUDE_MODEL"))
    if name == "gemini":
        key = env("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is not set")
        return GeminiLLM(key, model=env("GEMINI_MODEL"))
    raise LLMError(f"Unknown LLM provider: {name}")


def get_llm(cfg: Config):
    primary = _provider(env("LLM_PROVIDER") or "claude_code")
    fallback_name = env("LLM_FALLBACK")
    if fallback_name:
        try:
            return FallbackLLM(primary, _provider(fallback_name))
        except LLMError:
            return primary
    return primary
