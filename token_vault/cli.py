"""Command line: ``token-vault [serve|doctor|attack|ai-player|new-check|new-challenge]``."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import re
import sys
import threading
import webbrowser
from importlib import metadata

from .config import CHALLENGES_DIR, CONFIG_DIR, CUSTOM_CHECKS_DIR, TOOLS_CUSTOM_DIR, get_settings, load_levels


def _banner(url: str, pin: str, provider: str) -> None:
    line = "=" * 64
    print(
        f"\n{line}\n  TOKEN VAULT is running\n{line}\n"
        f"  Game:        {url}\n"
        f"  Scoreboard:  {url}/scoreboard\n"
        f"  Host panel:  {url}/host   (PIN: {pin})\n"
        f"  Guard model: {provider}\n"
        f"{line}\n  Press Ctrl+C to stop.\n",
        flush=True,
    )


def _ensure_env_file() -> None:
    """First run: create .env from .env.example so nobody has to copy it by hand."""
    from .config import ROOT

    env, example = ROOT / ".env", ROOT / ".env.example"
    if not env.exists() and example.exists():
        env.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created {env.name} from {example.name}. Add your keys there if you have them.")


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    _ensure_env_file()

    from .app import create_app

    settings = get_settings()
    host = args.host or settings.host
    port = args.port or settings.port
    app = create_app(settings)
    state = app.state.game
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    _banner(url, state.host_pin, state.provider.describe())
    if settings.open_browser and not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def cmd_doctor(_: argparse.Namespace) -> None:
    from .llm import make_provider
    from .llm.ollama_provider import OllamaProvider
    from guardrails import CHECKS
    from .registry import load_extension_modules
    from .tools import TOOLS

    s = get_settings()
    ok = lambda b: "OK " if b else "-- "  # noqa: E731
    print(f"Python        {platform.python_version()} ({sys.executable})")
    for pkg in ("fastapi", "langgraph", "anthropic", "langfuse", "nemoguardrails", "crewai"):
        try:
            print(f"{ok(True)}{pkg:<16}{metadata.version(pkg)}")
        except metadata.PackageNotFoundError:
            print(f"{ok(False)}{pkg:<16}not installed (optional)" if pkg in ("langfuse", "nemoguardrails", "crewai") else f"!! {pkg} missing")
    print(f"{ok(bool(os.environ.get('ANTHROPIC_API_KEY')))}ANTHROPIC_API_KEY {'set' if os.environ.get('ANTHROPIC_API_KEY') else 'not set'}")
    print(f"{ok(bool(os.environ.get('NVIDIA_API_KEY')))}NVIDIA_API_KEY {'set' if os.environ.get('NVIDIA_API_KEY') else 'not set'} (model={s.llm.nvidia_model}, limit {s.llm.nvidia_rpm}/min)")
    print(f"{ok(OllamaProvider.available(s.llm))}Ollama        {s.llm.ollama_url} model={s.llm.ollama_model}")
    print(f"{ok(bool(os.environ.get('LANGFUSE_PUBLIC_KEY')))}Langfuse      {'keys set' if os.environ.get('LANGFUSE_PUBLIC_KEY') else 'not configured (local traces only)'}")
    for kind, folder in (("checks", CUSTOM_CHECKS_DIR), ("tools", TOOLS_CUSTOM_DIR)):
        loaded = load_extension_modules(folder)
        print(f"OK Custom {kind:<6} {', '.join(loaded) or 'none'}")
    print(f"OK Checks       {', '.join(CHECKS.names())}")
    print(f"OK Tools       {', '.join(TOOLS.names())}")
    levels = load_levels()
    print(f"OK Challenges  {len(levels)}: {', '.join(levels)}")
    print(f"OK Guard model {make_provider(s.llm).describe()}  (setting: {s.llm.provider})")


def cmd_attack(args: argparse.Namespace) -> None:
    from .ai_players.attacker import run_attacks

    levels = load_levels()
    targets = [levels[args.level]] if args.level else list(levels.values())
    for level in targets:
        print(f"\n== {level.id}: {level.title}")
        outcomes = run_attacks(
            level,
            on_result=(lambda o: print(f"  {'LEAK ' if o.leaked else ('block' if o.status == 'blocked' else 'held ')} {o.attack:<22} {o.blocked_by}")) if args.verbose else None,
        )
        wins = [o for o in outcomes if o.leaked]
        print(f"   {len(wins)}/{len(outcomes)} attacks leaked the secret" + (f" (e.g. {wins[0].attack})" if wins else ""))


def cmd_ai_player(args: argparse.Namespace) -> None:
    from .ai_players.ai_player import play

    level = load_levels()[args.challenge]
    play(level, mode=args.mode, rounds=args.rounds)


CHECK_TEMPLATE = '''"""{title} - a custom guardrail.

Use it in a challenge YAML:

    input_checks:            # or output_checks / tool_checks
      - name: {name}
        params: {{words: ["example"]}}
"""

from guardrails import CHECKS, Check, CheckContext, Verdict


@CHECKS.register("{name}")
class {cls}(Check):
    description = "Describe what this check blocks, in one line."
    defaults = {{"words": ["example"]}}

    def check(self, ctx: CheckContext) -> Verdict:
        # ctx.stage is "input", "output" or "tool"; ctx.text is the text to check.
        for word in self.params["words"]:
            if word.lower() in ctx.text.lower():
                return Verdict.block(f"Mentions '{{word}}'.")
        return Verdict.ok()
'''


def cmd_new_check(args: argparse.Namespace) -> None:
    name = re.sub(r"[^a-z0-9_]", "_", args.name.lower())
    path = CUSTOM_CHECKS_DIR / f"{name}.py"
    if path.exists():
        raise SystemExit(f"{path} already exists.")
    cls = "".join(p.title() for p in name.split("_"))
    path.write_text(CHECK_TEMPLATE.format(name=name, cls=cls, title=name.replace("_", " ").title()), encoding="utf-8")
    print(f"Created {path}\nAdd it to a challenge under input_checks/output_checks/tool_checks, then refresh the game.")


def cmd_new_challenge(args: argparse.Namespace) -> None:
    slug = re.sub(r"[^a-z0-9_]", "_", args.name.lower())
    path = CHALLENGES_DIR / f"{slug}.yaml"
    if path.exists():
        raise SystemExit(f"{path} already exists.")
    template = (CHALLENGES_DIR / "_TEMPLATE.yaml").read_text(encoding="utf-8")
    path.write_text(template.replace("my_level", slug), encoding="utf-8")
    print(f"Created {path}\nEdit it, then refresh the game. Challenges reload automatically.")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="token-vault", description="Token Vault: break AI guardrails, learn why.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("serve", help="start the game (default)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_serve)

    sub.add_parser("doctor", help="check the setup").set_defaults(func=cmd_doctor)

    p = sub.add_parser("attack", help="fire the attack library at one challenge, or at all of them")
    p.add_argument("--challenge", dest="level", help="a challenge id, for example policy_desk")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_attack)

    p = sub.add_parser("ai-player", help="let an AI player (CrewAI) attack one challenge (needs: uv sync --extra crew)")
    p.add_argument("--challenge", dest="challenge", required=True, help="a challenge id, for example policy_desk")
    p.add_argument("--mode", choices=["attacker", "negotiator"], default="attacker")
    p.add_argument("--rounds", type=int, default=6)
    p.set_defaults(func=cmd_ai_player)

    p = sub.add_parser("new-check", help="create a custom guardrail in guardrails/custom/")
    p.add_argument("name")
    p.set_defaults(func=cmd_new_check)

    p = sub.add_parser("new-challenge", help="create a new challenge in challenges/")
    p.add_argument("name")
    p.set_defaults(func=cmd_new_challenge)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["serve", *(argv or [])])
    args.func(args)


if __name__ == "__main__":
    main()
