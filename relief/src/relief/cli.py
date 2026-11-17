"""Command line entry point: `relief <command>` (also the Docker image's entrypoint)."""
from __future__ import annotations

import argparse
import json
import sys

from relief.config import Settings


def _check(args, settings: Settings) -> int:
    from relief.checks import run_checks

    results = run_checks(settings, args.only)
    if args.json:
        print(json.dumps([{"name": r.name, "ok": r.ok, "details": r.details} for r in results], indent=2, default=str))
    else:
        for result in results:
            print(f"[{'OK' if result.ok else 'FAIL'}] {result.name}")
            for key, value in result.details.items():
                print(f"    {key}: {value}")
    return 0 if all(r.ok for r in results) else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="relief", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="verify GPUs, Postgres and Neo4j from where RELIEF runs")
    check.add_argument("--only", nargs="+", choices=["runtime", "postgres", "neo4j"], help="run only these checks")
    check.add_argument("--json", action="store_true", help="print the results as JSON")
    check.set_defaults(handler=_check)
    return parser


def main(argv=None) -> int:
    try:
        from dotenv import find_dotenv, load_dotenv

        # outside Docker: pick up the preprocessor's .env; real environment variables still win
        load_dotenv(find_dotenv(usecwd=True), override=False)
    except ImportError:
        pass
    args = build_parser().parse_args(argv)
    return args.handler(args, Settings.from_env())


if __name__ == "__main__":
    sys.exit(main())
