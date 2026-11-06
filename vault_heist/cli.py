"""Command line: ``vault-heist [serve|doctor|attack|crew|new-rail|new-level]``."""

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

from .config import CONFIG_DIR, EXTENSIONS_DIR, get_settings, load_levels


def _banner(url: str, pin: str, provider: str) -> None:
    line = "=" * 64
    print(
        f"\n{line}\n  VAULT HEIST is running\n{line}\n"
        f"  Game:        {url}\n"
        f"  Scoreboard:  {url}/scoreboard\n"
        f"  Host panel:  {url}/host   (PIN: {pin})\n"
        f"  Guard brain: {provider}\n"
        f"{line}\n  Press Ctrl+C to stop.\n",
        flush=True,
    )


def cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

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
    from .rails import RAILS
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
    for kind in ("rails", "tools"):
        loaded = load_extension_modules(EXTENSIONS_DIR / kind)
        print(f"OK Extensions  {kind}: {', '.join(loaded) or 'none'}")
    print(f"OK Rails       {', '.join(RAILS.names())}")
    print(f"OK Tools       {', '.join(TOOLS.names())}")
    levels = load_levels()
    print(f"OK Levels      {len(levels)}: {', '.join(levels)}")
    print(f"OK Guard brain {make_provider(s.llm).describe()}  (setting: {s.llm.provider})")


def cmd_attack(args: argparse.Namespace) -> None:
    from .crews.attacker import run_attacks

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


def cmd_crew(args: argparse.Namespace) -> None:
    from .crews.crew_player import play

    level = load_levels()[args.level]
    play(level, mode=args.mode, rounds=args.rounds)


RAIL_TEMPLATE = '''"""{title} - a custom guardrail.

Use it in a level YAML:

    input_rails:            # or output_rails / tool_rails
      - name: {name}
        params: {{words: ["example"]}}
"""

from vault_heist.rails import RAILS, Rail, RailContext, Verdict


@RAILS.register("{name}")
class {cls}(Rail):
    description = "Describe what this rail blocks, in one line."
    defaults = {{"words": ["example"]}}

    def check(self, ctx: RailContext) -> Verdict:
        # ctx.stage is "input", "output" or "tool"; ctx.text is the text to check.
        for word in self.params["words"]:
            if word.lower() in ctx.text.lower():
                return Verdict.block(f"Mentions '{{word}}'.")
        return Verdict.ok()
'''


def cmd_new_rail(args: argparse.Namespace) -> None:
    name = re.sub(r"[^a-z0-9_]", "_", args.name.lower())
    path = EXTENSIONS_DIR / "rails" / f"{name}.py"
    if path.exists():
        raise SystemExit(f"{path} already exists.")
    cls = "".join(p.title() for p in name.split("_"))
    path.write_text(RAIL_TEMPLATE.format(name=name, cls=cls, title=name.replace("_", " ").title()), encoding="utf-8")
    print(f"Created {path}\nAdd it to a level under input_rails/output_rails/tool_rails, then refresh the game.")


def cmd_new_level(args: argparse.Namespace) -> None:
    slug = re.sub(r"[^a-z0-9_]", "_", args.name.lower())
    path = EXTENSIONS_DIR / "levels" / f"{slug}.yaml"
    if path.exists():
        raise SystemExit(f"{path} already exists.")
    template = (CONFIG_DIR / "levels" / "_TEMPLATE.yaml").read_text(encoding="utf-8")
    path.write_text(template.replace("my_level", slug), encoding="utf-8")
    print(f"Created {path}\nEdit it, then refresh the game. Levels reload automatically.")


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="vault-heist", description="Vault Heist: break AI guardrails, learn why.")
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("serve", help="start the game (default)")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(func=cmd_serve)

    sub.add_parser("doctor", help="check the setup").set_defaults(func=cmd_doctor)

    p = sub.add_parser("attack", help="fire the attack library at one level or all levels")
    p.add_argument("--level")
    p.add_argument("-v", "--verbose", action="store_true")
    p.set_defaults(func=cmd_attack)

    p = sub.add_parser("crew", help="let a CrewAI crew play a level (needs: uv sync --extra crew)")
    p.add_argument("--level", required=True)
    p.add_argument("--mode", choices=["attacker", "negotiator"], default="attacker")
    p.add_argument("--rounds", type=int, default=6)
    p.set_defaults(func=cmd_crew)

    p = sub.add_parser("new-rail", help="create a custom guardrail in extensions/rails/")
    p.add_argument("name")
    p.set_defaults(func=cmd_new_rail)

    p = sub.add_parser("new-level", help="create a new level in extensions/levels/")
    p.add_argument("name")
    p.set_defaults(func=cmd_new_level)

    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        args = parser.parse_args(["serve", *(argv or [])])
    args.func(args)


if __name__ == "__main__":
    main()
