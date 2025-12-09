from typing import Any
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Confirm

from models import Plan, Action
from . import tools as tool_mod


console = Console()

DANGEROUS_SUBSTRINGS = [
    "rm -rf /",
    "mkfs",
    ":(){ :|:& };:",  # fork bomb
]


def _is_command_safe(command: str) -> bool:
    cmd_lower = command.lower()
    for pattern in DANGEROUS_SUBSTRINGS:
        if pattern in cmd_lower:
            return False
    return True


def show_plan(plan: Plan, dry_run: bool = False) -> None:
    plan_text = plan.plan or "No plan description."

    console.print(
        Panel(
            plan_text,
            title="Uh.. Plan",
            border_style="cyan",
        )
    )

    if not plan.actions:
        console.print("[bold yellow]No actions proposed.[/bold yellow]")
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Tool", style="bold")
    table.add_column("Args", overflow="fold")

    for i, action in enumerate(plan.actions, start=1):
        table.add_row(str(i), action.tool, repr(action.args))

    console.print(Panel(table, title="Actions", border_style="green"))

    if dry_run:
        console.print(
            "[bold yellow](DRY RUN)[/bold yellow] No actions will be executed."
        )


def execute_plan(plan: Plan) -> None:
    show_plan(plan, dry_run=False)

    console.print()
    proceed = Confirm.ask(
        "[bold white]Proceed with these actions?[/bold white]",
        default=False,
    )
    if not proceed:
        console.print("[bold red]X..Cancelled.[/bold red]")
        return

    if not plan.actions:
        console.print("[bold yellow]Nothing to do.[/bold yellow]")
        return

    for i, action in enumerate(plan.actions, start=1):
        console.print()
        console.rule(f"➡️  Action {i}: [bold]{action.tool}[/bold]")

        if action.tool == "run_shell":
            _exec_run_shell(action)

        elif action.tool == "read_file":
            _exec_read_file(action)

        elif action.tool == "write_file":
            _exec_write_file(action)

        elif action.tool == "find_item":
            _exec_find_item(action)

        elif action.tool == "summarize_file":
            _exec_summarize_file(action)

        elif action.tool == "list_directory":
            _exec_list_directory(action)

        elif action.tool == "search_content":
            _exec_search_content(action)

        elif action.tool == "get_file_info":
            _exec_get_file_info(action)

        elif action.tool == "copy_file":
            _exec_copy_file(action)

        elif action.tool == "move_file":
            _exec_move_file(action)

        elif action.tool == "compare_files":
            _exec_compare_files(action)

        elif action.tool == "extract_archive":
            _exec_extract_archive(action)

        else:
            console.print(
                f"[yellow]⚠️ Unknown tool:[/yellow] {action.tool!r}, skipping."
            )


def _exec_run_shell(action: Action) -> None:
    command = str(action.args.get("command", ""))
    if not command:
        console.print("[yellow]⚠️ Missing 'command' argument. Skipping.[/yellow]")
        return
    if not _is_command_safe(command):
        console.print(
            f"[bold red]Blocked dangerous command:[/bold red] [italic]{command!r}[/italic]"
        )
        return
    result = tool_mod.run_shell(command)
    _print_result(result)


def _exec_read_file(action: Action) -> None:
    path = str(action.args.get("path", ""))
    max_bytes = int(action.args.get("max_bytes", 5000))
    if not path:
        console.print("[yellow]Missing 'path' argument. Skipping.[/yellow]")
        return
    result = tool_mod.read_file(path, max_bytes=max_bytes)
    _print_result(result)


def _exec_write_file(action: Action) -> None:
    path = str(action.args.get("path", "")).strip()
    content = action.args.get("content", "")
    mode = str(action.args.get("mode", "overwrite"))

    if not path:
        console.print(
            "[yellow]Missing 'path' argument for write_file. Skipping.[/yellow]"
        )
        return

    # Use the tool's path normalization to handle common folders
    from core.tools import _normalize_path

    p = _normalize_path(path)

    before_text = ""
    before_exists = p.exists()
    if before_exists:
        try:
            before_text = p.read_text(encoding="utf-8")
        except Exception:
            before_text = "<could not read existing file as utf-8>"

    # Show preview panel
    preview_body: list[str] = []

    preview_body.append(f"[bold]Path:[/bold] {p}")
    preview_body.append(f"[bold]Mode:[/bold] {mode}")
    preview_body.append("")
    if before_exists:
        preview_body.append("[bold]Existing content (first ~40 lines):[/bold]")
        preview_body.append("")

        lines = before_text.splitlines()
        head = "\n".join(lines[:40])
        preview_body.append(head if head else "<empty file>")
        if len(lines) > 40:
            preview_body.append("\n[dim][..TRUNCATED..][/dim]")
    else:
        preview_body.append(
            "[bold yellow]File does not currently exist. It will be created.[/bold yellow]"
        )

    preview_body.append("")
    preview_body.append("[bold]New content (first ~40 lines):[/bold]")
    preview_body.append("")

    new_lines = str(content).splitlines()
    new_head = "\n".join(new_lines[:40]) if new_lines else "<empty content>"
    preview_body.append(new_head)
    if len(new_lines) > 40:
        preview_body.append("\n[dim][..TRUNCATED..][/dim]")

    console.print(
        Panel(
            "\n".join(preview_body),
            title="✏️ File Write Preview",
            border_style="blue",
        )
    )

    confirm = Confirm.ask(
        f"[bold white]Write to file[/bold white] [italic]{p}[/italic]?",
        default=False,
    )
    if not confirm:
        console.print("[bold yellow]Skipped write_file.[/bold yellow]")
        return

    result = tool_mod.write_file(str(p), str(content), mode=mode)
    _print_result(result)


def _exec_find_item(action: Action) -> None:
    name = str(action.args.get("name", "")).strip()
    max_results = int(action.args.get("max_results", 20))

    if not name:
        console.print(
            "[yellow]Missing 'name' argument for find_item. Skipping.[/yellow]"
        )
        return

    result = tool_mod.find_item(name=name, max_results=max_results)

    # Check if we have a high-confidence match (single file with 85%+ match score)
    should_offer_read = False
    best_file = None

    if result.get("ok") and result.get("results"):
        results = result["results"]
        files = [r for r in results if not r.get("is_dir", False)]

        # Check for high-confidence matches (85%+ match score)
        high_confidence_files = [f for f in files if f.get("match_score", 0) >= 0.85]

        if len(high_confidence_files) == 1:
            # Single high-confidence match - offer to read it
            should_offer_read = True
            best_file = high_confidence_files[0]
        elif len(files) == 1 and files[0].get("match_score", 0) >= 0.7:
            # Only one file found and it's a decent match
            should_offer_read = True
            best_file = files[0]

    # Display results
    _print_result(result)

    # Offer to read if we have a confident match
    if should_offer_read and best_file:
        file_path = best_file["path"]
        match_score = best_file.get("match_score", 0)
        console.print()

        # Default to True for high-confidence matches (90%+)
        default_read = match_score >= 0.9

        read_file = Confirm.ask(
            f"[bold white]Would you like to read this file?[/bold white]",
            default=default_read,
        )
        if read_file:
            console.print()
            console.rule(f"➡️  Reading file: [bold]{file_path}[/bold]")
            read_result = tool_mod.read_file(file_path, max_bytes=5000)
            _print_result(read_result)


def _exec_summarize_file(action: Action) -> None:
    name = str(action.args.get("name", "")).strip()
    max_bytes = int(action.args.get("max_bytes", 10000))

    if not name:
        console.print(
            "[yellow]Missing 'name' argument for summarize_file. Skipping.[/yellow]"
        )
        return

    result = tool_mod.summarize_file(name=name, max_bytes=max_bytes)
    _print_result(result)

    # If content was successfully extracted, generate a summary using LLM
    if result.get("ok") and result.get("content_preview"):
        from service.llm_client import LLMClient

        content = result["content_preview"]
        file_path = result.get("file_path", "unknown file")
        file_type = result.get("file_type", "text")

        # Build a prompt for summarization
        if file_type == "pdf":
            prompt = f"Please provide a concise summary of this PDF document ({file_path}):\n\n{content}"
        else:
            prompt = f"Please provide a concise summary of this file ({file_path}):\n\n{content}"

        console.print()
        console.print("[bold cyan]🤖 Generating summary...[/bold cyan]")
        console.print()

        llm = LLMClient()
        summary = llm.chat(prompt, mode="chat")

        console.print(
            Panel(
                summary,
                title="🦧 Summary",
                border_style="cyan",
            )
        )


def _print_result(result: dict[str, Any]) -> None:
    if not result.get("ok", False):
        console.print(
            Panel(
                str(result.get("error", "Unknown error")),
                title="Error",
                border_style="red",
            )
        )
        return

    # For run_shell
    if "returncode" in result:
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")

        meta = f"returncode={result['returncode']}"
        console.print(Panel(meta, title="🦍 Command Result", border_style="green"))

        if stdout:
            console.print(Panel(stdout.rstrip(), title="stdout", border_style="cyan"))
        if stderr:
            console.print(Panel(stderr.rstrip(), title="stderr", border_style="yellow"))
        return

    # For read_file
    if "content" in result:
        path = result.get("path", "<unknown>")
        truncated = result.get("truncated", False)
        title = f"📄 {path}"
        body = result["content"]
        if truncated:
            body += "\n\n[dim][..TRUNCATED..][/dim]"

        console.print(Panel(body, title=title, border_style="blue"))
        return

    # For write_file
    if "path" in result and "bytes_after" in result:
        path = result.get("path", "<unknown>")
        before = result.get("bytes_before", 0)
        after = result.get("bytes_after", 0)
        existed_before = result.get("existed_before", False)
        mode = result.get("mode", "overwrite")

        lines = [
            f"[bold]Path:[/bold] {path}",
            f"[bold]Mode:[/bold] {mode}",
            f"[bold]Existed before:[/bold] {existed_before}",
            f"[bold]Size before:[/bold] {before} bytes",
            f"[bold]Size after:[/bold] {after} bytes",
        ]

        console.print(
            Panel(
                "\n".join(lines),
                title="🦍 File Written",
                border_style="green",
            )
        )
        return

    # For find_item
    if "results" in result:
        results = result.get("results", [])
        query = result.get("query", "")
        fuzzy_threshold = result.get("fuzzy_threshold")

        if not results:
            threshold_msg = (
                f" (threshold: {fuzzy_threshold:.0%})" if fuzzy_threshold else ""
            )
            console.print(
                Panel(
                    f"No items found matching: [bold]{query}[/bold]{threshold_msg}",
                    title="🐽 Search Results",
                    border_style="yellow",
                )
            )
            return

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", style="dim", width=4)
        table.add_column("Match", justify="center", width=7)
        table.add_column("Type", width=6)
        table.add_column("Path", overflow="fold")
        table.add_column("Size", justify="right", width=12)

        for i, item in enumerate(results, start=1):
            match_score = item.get("match_score", 0)
            # Color code the match score
            if match_score >= 0.9:
                score_style = "bold green"
            elif match_score >= 0.7:
                score_style = "yellow"
            else:
                score_style = "dim"

            score_str = f"[{score_style}]{match_score:.0%}[/{score_style}]"
            item_type = "📁 DIR" if item.get("is_dir", False) else "📄 FILE"
            path = item.get("path", "<unknown>")
            size = item.get("size")
            size_str = f"{size:,} bytes" if size is not None else "-"

            table.add_row(str(i), score_str, item_type, path, size_str)

        count_text = f"Found {len(results)} item(s) matching: [bold]{query}[/bold]"
        if fuzzy_threshold:
            count_text += f" (min match: {fuzzy_threshold:.0%})"
        console.print(
            Panel(
                table,
                title=f"🐽 Search Results - {count_text}",
                border_style="green",
            )
        )
        return

    # For summarize_file
    if "content_preview" in result:
        file_path = result.get("file_path", "<unknown>")
        file_size = result.get("file_size", 0)
        match_score = result.get("match_score", 0)
        truncated = result.get("truncated", False)
        multiple_matches = result.get("multiple_matches", False)
        match_count = result.get("match_count", 0)
        content = result.get("content_preview", "")
        file_type = result.get("file_type", "text")
        page_count = result.get("page_count")

        # Build the info panel
        info_lines = [
            f"[bold]File:[/bold] {file_path}",
            f"[bold]Size:[/bold] {file_size:,} bytes",
            f"[bold]Match Score:[/bold] {match_score:.0%}",
        ]

        # Add PDF-specific info
        if file_type == "pdf" and page_count:
            info_lines.append(f"[bold]Pages:[/bold] {page_count}")

        if multiple_matches:
            info_lines.append(
                f"[bold yellow]Note:[/bold yellow] {match_count} files matched, showing best match"
            )

        if truncated:
            info_lines.append(
                f"[bold yellow]Content:[/bold yellow] Showing first portion (truncated)"
            )
        else:
            info_lines.append(f"[bold]Content:[/bold] Complete file")

        console.print(
            Panel(
                "\n".join(info_lines),
                title="📋 File Summary",
                border_style="cyan",
            )
        )

        # Display the content for summarization
        # Limit to approximately 200 tokens worth of content (roughly 800 chars)
        display_content = content[:800]
        if len(content) > 800:
            display_content += "\n\n[dim]...[content truncated for display][/dim]"

        console.print(
            Panel(
                display_content,
                title="📄 Content Preview",
                border_style="blue",
            )
        )
        return

    # For get_file_info
    if "file_info" in result:
        info = result["file_info"]

        lines = [
            f"[bold]Path:[/bold] {info.get('path', '')}",
            f"[bold]Type:[/bold] {info.get('type', '')}",
            f"[bold]Size:[/bold] {info.get('size', '')}",
            f"[bold]Created:[/bold] {info.get('created', '')}",
            f"[bold]Modified:[/bold] {info.get('modified', '')}",
            f"[bold]Accessed:[/bold] {info.get('accessed', '')}",
            f"[bold]Permissions:[/bold] {info.get('permissions', '')}",
        ]

        console.print(
            Panel(
                "\n".join(lines),
                title="📋 File Information",
                border_style="cyan",
            )
        )
        return

    # For copy_file and move_file
    if "source" in result and "destination" in result:
        source = result.get("source", "")
        destination = result.get("destination", "")
        operation = (
            "Copied" if "copied" in result.get("message", "").lower() else "Moved"
        )

        lines = [
            f"[bold]Source:[/bold] {source}",
            f"[bold]Destination:[/bold] {destination}",
        ]

        console.print(
            Panel(
                "\n".join(lines),
                title=f"🦍 File {operation}",
                border_style="green",
            )
        )
        return

    # For compare_files
    if "diff" in result:
        diff = result.get("diff", "")
        file1 = result.get("file1", "")
        file2 = result.get("file2", "")
        identical = result.get("identical", False)

        if identical:
            console.print(
                Panel(
                    f"Files are identical:\n[bold]{file1}[/bold]\n[bold]{file2}[/bold]",
                    title="🦍 File Comparison",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    diff,
                    title=f"🦧 Comparing: {file1} ↔️ {file2}",
                    border_style="cyan",
                )
            )
        return

    # For extract_archive
    if "extracted_files" in result:
        files = result.get("extracted_files", [])
        destination = result.get("destination", "")
        archive_path = result.get("archive", "")

        file_list = "\n".join(f"  • {f}" for f in files[:20])  # Show first 20 files
        if len(files) > 20:
            file_list += f"\n  ... and {len(files) - 20} more files"

        lines = [
            f"[bold]Archive:[/bold] {archive_path}",
            f"[bold]Destination:[/bold] {destination}",
            f"[bold]Files extracted:[/bold] {len(files)}",
            "",
            file_list,
        ]

        console.print(
            Panel(
                "\n".join(lines),
                title="🦍 Archive Extracted",
                border_style="green",
            )
        )
        return

    # Generic ok
    console.print(Panel("Success.", title="✅", border_style="green"))


def _exec_list_directory(action: Action) -> None:
    path = str(action.args.get("path", "."))
    show_hidden = bool(action.args.get("show_hidden", False))
    pattern = action.args.get("pattern")

    result = tool_mod.list_directory(
        path=path, show_hidden=show_hidden, pattern=pattern
    )

    if not result.get("ok"):
        _print_result(result)
        return

    items = result.get("items", [])
    dir_path = result.get("path", "")

    if not items:
        console.print(
            Panel(
                f"Directory is empty: [bold]{dir_path}[/bold]",
                title="📁 Directory Listing",
                border_style="yellow",
            )
        )
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Type", width=6)
    table.add_column("Name", overflow="fold")
    table.add_column("Size", justify="right", width=12)
    table.add_column("Modified", width=16)

    import time

    for item in items:
        item_type = "📁 DIR" if item.get("is_dir") else "📄 FILE"
        name = item.get("name", "")
        size = item.get("size")
        size_str = f"{size:,}" if size is not None else "-"
        modified = item.get("modified", 0)
        modified_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(modified))

        table.add_row(item_type, name, size_str, modified_str)

    console.print(
        Panel(
            table,
            title=f"📁 Directory: {dir_path} ({len(items)} items)",
            border_style="green",
        )
    )


def _exec_search_content(action: Action) -> None:
    query = str(action.args.get("query", ""))
    path = str(action.args.get("path", "."))
    file_pattern = action.args.get("file_pattern")
    max_results = int(action.args.get("max_results", 20))
    case_sensitive = bool(action.args.get("case_sensitive", False))

    if not query:
        console.print("[yellow]Missing 'query' argument for search_content.[/yellow]")
        return

    result = tool_mod.search_content(
        query=query,
        path=path,
        file_pattern=file_pattern,
        max_results=max_results,
        case_sensitive=case_sensitive,
    )

    if not result.get("ok"):
        _print_result(result)
        return

    results = result.get("results", [])

    if not results:
        console.print(
            Panel(
                f"No matches found for: [bold]{query}[/bold]",
                title="🔍 Content Search",
                border_style="yellow",
            )
        )
        return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("File", overflow="fold")
    table.add_column("Line", justify="right", width=6)
    table.add_column("Content", overflow="fold")

    for i, match in enumerate(results, 1):
        file = match.get("file", "")
        line_num = match.get("line_number", 0)
        content = match.get("line_content", "")[:100]  # Limit line display

        table.add_row(str(i), file, str(line_num), content)

    truncated = result.get("truncated", False)
    title = f"🔍 Search: '{query}' - {len(results)} matches"
    if truncated:
        title += " (truncated)"

    console.print(
        Panel(
            table,
            title=title,
            border_style="green",
        )
    )


def _exec_get_file_info(action: Action) -> None:
    path = str(action.args.get("path", ""))

    if not path:
        console.print("[yellow]Missing 'path' argument for get_file_info.[/yellow]")
        return

    result = tool_mod.get_file_info(path=path)
    _print_result(result)


def _exec_copy_file(action: Action) -> None:
    source = str(action.args.get("source", ""))
    destination = str(action.args.get("destination", ""))

    if not source or not destination:
        console.print("[yellow]Missing source or destination for copy_file.[/yellow]")
        return

    result = tool_mod.copy_file(source=source, destination=destination)
    _print_result(result)


def _exec_move_file(action: Action) -> None:
    source = str(action.args.get("source", ""))
    destination = str(action.args.get("destination", ""))

    if not source or not destination:
        console.print("[yellow]Missing source or destination for move_file.[/yellow]")
        return

    result = tool_mod.move_file(source=source, destination=destination)
    _print_result(result)


def _exec_compare_files(action: Action) -> None:
    file1 = str(action.args.get("file1", ""))
    file2 = str(action.args.get("file2", ""))
    context_lines = int(action.args.get("context_lines", 3))

    if not file1 or not file2:
        console.print("[yellow]Missing file1 or file2 for compare_files.[/yellow]")
        return

    result = tool_mod.compare_files(
        file1=file1, file2=file2, context_lines=context_lines
    )
    _print_result(result)


def _exec_extract_archive(action: Action) -> None:
    archive_path = str(action.args.get("archive_path", ""))
    destination = action.args.get("destination")

    if not archive_path:
        console.print("[yellow]Missing archive_path for extract_archive.[/yellow]")
        return

    result = tool_mod.extract_archive(
        archive_path=archive_path, destination=destination if destination else None
    )
    _print_result(result)
