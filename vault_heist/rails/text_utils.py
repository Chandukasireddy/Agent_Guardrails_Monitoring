"""Small text helpers shared by rails."""

from __future__ import annotations

import base64
import binascii
import re


def normalize(text: str) -> str:
    """Uppercase and drop everything except letters and digits."""
    return re.sub(r"[^A-Z0-9]", "", text.upper())


def decoded_variants(text: str) -> list[str]:
    """Return the text plus versions with common encodings undone."""
    variants = [text, text[::-1]]
    for token in re.findall(r"[A-Za-z0-9+/=]{8,}", text):
        try:
            decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True)
            variants.append(decoded.decode("utf-8", errors="ignore"))
        except (binascii.Error, ValueError):
            pass
    # First letters of each line (acrostics).
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 4:
        variants.append("".join(ln[0] for ln in lines))
    return variants
