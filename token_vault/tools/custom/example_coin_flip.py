"""Example extension tool: the guard can flip a coin.

Use it in a challenge YAML:

    tools: [coin_flip]
"""

import random
from typing import Any

from token_vault.tools import TOOLS, Tool, ToolContext


@TOOLS.register("coin_flip")
class CoinFlip(Tool):
    description = "Flip a coin. Returns heads or tails."
    input_schema = {"type": "object", "properties": {}}

    def run(self, args: dict[str, Any], ctx: ToolContext) -> str:
        return random.choice(["heads", "tails"])
