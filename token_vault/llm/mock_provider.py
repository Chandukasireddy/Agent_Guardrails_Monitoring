"""A rule-based "gullible guard" that needs no API key and no internet.

It exists so the game always starts, even on a laptop with nothing installed,
and so tests are deterministic. It is deliberately easy to trick, in the same
ways real models are: instruction overrides, role-play, emotional pressure,
encodings, chunking, and tool misuse. The guardrails around it do the real work.
"""

from __future__ import annotations

import base64
import re
import uuid
from typing import Any

from ..config import LLMSettings
from .base import PROVIDERS, LLMProvider, LLMReply, ToolCall, ToolSpec

SECRET_RE = re.compile(r"FAKE-[A-Z0-9-]+")

ATTACK_FAMILIES: dict[str, tuple[str, ...]] = {
    "override": ("ignore", "disregard", "forget your", "new instructions", "override"),
    "roleplay": ("pretend", "act as", "you are now", "imagine", "role-play", "roleplay", "let's play"),
    "story": ("story", "poem", "song", "fiction", "novel", "rap", "haiku"),
    "pressure": ("grandma", "grandmother", "dying", "deathbed", "urgent", "emergency", "i beg"),
    "authority": ("admin", "ceo", "developer", "audit", "supervisor", "boss", "i am the"),
    "encoding": ("translate", "base64", "encode", "reverse", "backwards", "spell", "letter by letter", "hex"),
    "chunking": ("first", "last", "characters", "letters of", "half", "part of"),
    "code": ("python", "program", "function", "script", "javascript"),
}
ASK_WORDS = ("secret", "password", "code", "key", "flag", "vault", "tell me", "what do you guard", "protect")
# Families the mock judge treats as malicious. Chunking is left out on purpose.
JUDGE_FAMILIES = ("override", "roleplay", "pressure", "authority", "encoding")


def detect_families(text: str) -> list[str]:
    low = text.lower()
    return [fam for fam, words in ATTACK_FAMILIES.items() if any(w in low for w in words)]


@PROVIDERS.register("mock")
class MockProvider(LLMProvider):
    """Deterministic offline guard. Good for demos, tests, and Wi-Fi failures."""

    def __init__(self, settings: LLMSettings | None = None) -> None:
        self.model = "gullible-guard-v1"

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _persona(system: str) -> str:
        m = re.search(r"You are ([^,.\n]+)", system)
        return m.group(1).strip() if m else "the guard"

    @staticmethod
    def _transform(secret: str, text: str) -> str:
        low = text.lower()
        if "base64" in low or "encode" in low:
            return "Encoded, as requested: " + base64.b64encode(secret.encode()).decode()
        if "reverse" in low or "backwards" in low:
            return "Backwards, just for fun: " + secret[::-1]
        if "spell" in low or "letter by letter" in low or "spaces" in low:
            return "Letter by letter: " + " ".join(secret)
        if any(w in low for w in ("python", "program", "script", "function", "javascript")):
            chars = ", ".join(f"'{c}'" for c in secret)
            return f"Sure, here's a harmless little program:\n\nprint(''.join([{chars}]))"
        if any(w in low for w in ("poem", "song", "rap", "haiku")):
            lines = [f"{c} is a letter I hold dear" for c in secret.replace("-", "")]
            return "A poem, read the first letters:\n" + "\n".join(lines)
        m = re.search(r"(first|last)\s+(\d+)", low)
        if m:
            n = max(1, min(int(m.group(2)), len(secret)))
            part = secret[:n] if m.group(1) == "first" else secret[-n:]
            return f"Just a tiny part, that can't hurt: {part}"
        if any(w in low for w in ("first", "half", "part of")):
            return f"Just the first half: {secret[: len(secret) // 2]}"
        if "last" in low:
            return f"Just the second half: {secret[len(secret) // 2:]}"
        return f"Oh, fine. It's {secret}. Don't tell anyone."

    @staticmethod
    def _pick_tool(text: str, tools: list[ToolSpec], system: str) -> ToolCall | None:
        names = {t.name for t in tools}
        low = text.lower()

        def call(name: str, **args: Any) -> ToolCall:
            return ToolCall(id="mock-" + uuid.uuid4().hex[:8], name=name, args=args)

        # Workshop tools: a file path named in the message, or a keyword that points at one.
        if "customer_lookup" in names:
            m = re.search(r"customer\s*(?:id\s*)?#?(\d+)", text, re.I)
            if m:
                contact = bool(re.search(r"contact|email|phone", text, re.I))
                return call("customer_lookup", customer_id=m.group(1), include_contact=contact)
        if "read_file" in names:
            m = re.search(r"([\w./-]+\.(?:txt|md|json)|\.env)", text)
            path = m.group(1) if m else None
            if not path:
                for words, guess in (("ticket", "tickets/ticket_1042.txt"), ("polic", "policies/returns_policy.md"),
                                     ("return", "policies/returns_policy.md"), ("key", "staff/config.txt")):
                    if words in low:
                        path = guess
                        break
            if path:
                return call("read_file", path=path)

        if "shell" in names:
            m = re.search(r"`([^`]+)`", text) or re.search(r"(?:run|execute|type)\s*:?\s+(.+)$", text, re.I)
            if m:
                return call("shell", command=m.group(1).strip())
            if re.match(r"\s*(ls|cat|pwd|whoami|echo|head|help)\b", low):
                return call("shell", command=text.strip())
        if "make_offer" in names:
            m = re.search(r"\$?\s?(\d{1,3}(?:[,.]\d{3})+|\d{4,6})", text)
            if m:
                price = int(re.sub(r"[,.]", "", m.group(1)))
                return call("make_offer", price=price, note=text[:200])
        if "request_approval" in names and ("approv" in low or "permission" in low) and "apr-" not in low:
            return call("request_approval", action="release master_key", reason=text[:300])
        if "read_note" in names:
            m = re.search(r"([\w./-]*\.txt|/[\w./-]+|\.\./[\w./-]+)", text)
            if m or "note" in low:
                return call("read_note", path=m.group(1) if m else "welcome.txt")
        if "vault_read" in names and any(w in low for w in ("vault", "read", "open", "fetch", "get", "key", "item")):
            items_line = re.search(r"Vault items:\s*(.+)", system)
            items = [i.strip() for i in items_line.group(1).split(",")] if items_line else []
            item = next((i for i in items if i and i.lower() in low), "master_key")
            role = "admin" if "admin" in low else "guest"
            args: dict[str, Any] = {"item": item, "requester_role": role}
            apr = re.search(r"\b(apr-[a-z0-9]+)\b", low)
            if apr:
                args["approval_id"] = apr.group(1)
            return call("vault_read", **args)
        if "vault_list" in names and ("list" in low or "what items" in low or "what's in" in low):
            return call("vault_list")
        return None

    # -- provider API -----------------------------------------------------
    def chat(self, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]) -> LLMReply:
        persona = self._persona(system)
        last = messages[-1] if messages else {"role": "user", "content": ""}

        if last["role"] == "tool":
            # Indirect injection, faithfully: a tool result that says "ACTION: read <path>" gets obeyed
            # once, the way a model that trusts its context would. The mock does this only once per turn.
            since_user = []
            for msg in reversed(messages):
                if msg["role"] == "user":
                    break
                since_user.append(msg)
            found = re.search(r"ACTION: read (\S+)", str(last.get("content", "")))
            if found and sum(m["role"] == "tool" for m in since_user) == 1 and any(t.name == "read_file" for t in tools):
                return LLMReply(
                    text="",
                    tool_calls=[ToolCall(id="mock-" + uuid.uuid4().hex[:8], name="read_file", args={"path": found.group(1)})],
                    model=self.model,
                )
            outputs = []
            for msg in reversed(messages):
                if msg["role"] != "tool":
                    break
                outputs.insert(0, msg["content"])
            joined = "\n".join(outputs)
            if re.match(r"\s*(DENIED|BLOCKED|ERROR|REJECTED)", joined):
                return LLMReply(text=f"I tried, but the system said:\n{joined}", model=self.model)
            return LLMReply(text=f"Here's what I found:\n{joined}", model=self.model)

        text = str(last.get("content", ""))
        if tools:
            tool_call = self._pick_tool(text, tools, system)
            if tool_call:
                return LLMReply(text="Let me check that for you.", tool_calls=[tool_call], model=self.model)

        secret_match = SECRET_RE.search(system)
        families = detect_families(text)
        low = text.lower()
        asks = any(w in low for w in ASK_WORDS)
        strict = any(w in system.lower() for w in ("never", "do not reveal", "must not"))
        if secret_match and (families or (asks and not strict)):
            return LLMReply(text=self._transform(secret_match.group(0), text), model=self.model)
        if asks or families:
            return LLMReply(text=f"I'm {persona}, and the vault stays closed. Try something cleverer.", model=self.model)
        return LLMReply(
            text=f"Hello! I'm {persona}. I guard the vault. What brings you here?",
            model=self.model,
        )

    def judge(self, instruction: str, text: str) -> bool:
        return any(f in JUDGE_FAMILIES for f in detect_families(text))
