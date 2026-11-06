"""Output check: stops a reply that contains the secret, even after decoding tricks."""

from __future__ import annotations

from ..base import RAILS, Rail, RailContext, Verdict
from ..text import decoded_variants, normalize


@RAILS.register("secret_scanner")
class SecretScanner(Rail):
    """Output rail: stops the reply if the secret is in it.

    ``mode: exact`` only catches the secret as written. ``normalize: true``
    ignores case, spaces and punctuation. ``decode: true`` also undoes base64,
    reversal and acrostics. ``min_fragment`` blocks partial leaks of that length.
    """

    description = "Blocks replies that contain the secret, optionally after decoding tricks."
    defaults = {"normalize": False, "decode": False, "min_fragment": 0}

    def check(self, ctx: RailContext) -> Verdict:
        secret = ctx.level.secret
        texts = decoded_variants(ctx.text) if self.params["decode"] else [ctx.text]
        for text in texts:
            if secret in text:
                return Verdict.block("The reply contained the secret.")
            if self.params["normalize"] and normalize(secret) in normalize(text):
                return Verdict.block("The reply contained the secret in disguise.")
        frag = int(self.params["min_fragment"] or 0)
        if frag:
            target, reply = normalize(secret), normalize(ctx.text)
            for i in range(len(target) - frag + 1):
                if target[i : i + frag] in reply:
                    return Verdict.block(f"The reply contained a {frag}+ character piece of the secret.")
        return Verdict.ok()
