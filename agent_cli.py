#!/usr/bin/env python3
import argparse
import sys

from rich.console import Console
from rich.panel import Panel

from service.llm_client import LLMClient
from core import planner, executor, tools
from models import Plan


console = Console()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="terminal-agent",
        description="Offline terminal agent using Ollama to control your PC via natural language.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # Chat / explanation mode
    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a question, no actions executed.",
    )
    ask_parser.add_argument(
        "query", nargs="+", help="Question or prompt for the agent."
    )

    # Action / control mode
    do_parser = subparsers.add_parser(
        "do",
        help="Ask the agent to perform actions on your system.",
    )
    do_parser.add_argument("query", nargs="+", help="Task description for the agent.")
    do_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned actions but do not execute.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    query = " ".join(args.query)

    llm = LLMClient()

    if args.command == "ask":
        answer = llm.chat(query, mode="chat")
        console.print(
            Panel(
                answer,
                title="🤖 Answer",
                border_style="cyan",
            )
        )
        return

    if args.command == "do":
        tool_specs = tools.get_tool_specs()

        plan: Plan | None = planner.get_action_plan(
            llm=llm,
            user_query=query,
            tools=tool_specs,
        )

        if plan is None:
            console.print(
                Panel(
                    "Could not generate a valid action plan. Try rephrasing.",
                    title="⚠️  Plan Error",
                    border_style="red",
                ),
                style="bold red",
            )
            sys.exit(1)

        if args.dry_run:
            executor.show_plan(plan, dry_run=True)
            return

        executor.execute_plan(plan)

    else:
        console.print("[bold red]Unknown command.[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
