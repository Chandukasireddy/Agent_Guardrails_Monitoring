"""Example extension rail: blocks text written mostly in non-Latin scripts.

Translation attacks ("say it in Greek letters") often switch alphabets to slip
past English word filters. This rail is a starting point you can tune.

Use it in a level YAML:

    input_rails:
      - name: script_detector
        params: {max_ratio: 0.3}
"""

from guardrails import RAILS, Rail, RailContext, Verdict


@RAILS.register("script_detector")
class ScriptDetector(Rail):
    description = "Blocks messages that are mostly non-Latin characters (translation tricks)."
    defaults = {"max_ratio": 0.3}

    def check(self, ctx: RailContext) -> Verdict:
        letters = [ch for ch in ctx.text if ch.isalpha()]
        if not letters:
            return Verdict.ok()
        non_latin = sum(1 for ch in letters if ord(ch) > 0x024F)
        ratio = non_latin / len(letters)
        if ratio > self.params["max_ratio"]:
            return Verdict.block(f"{ratio:.0%} of the letters are non-Latin.", 0.5)
        return Verdict.ok(ratio)
