import os
import subprocess
import textwrap
from pathlib import Path
from typing import Dict, Any, List
from difflib import SequenceMatcher

try:
    import pdfplumber

    HAS_PDF_SUPPORT = True
except ImportError:
    HAS_PDF_SUPPORT = False


def _normalize_path(path: str) -> Path:
    """
    Normalize LLM-provided paths so things like '.\\file.txt' (Windows style)
    become './file.txt' and work correctly on POSIX too.

    Also resolves common folder names like 'downloads', 'documents', 'desktop'
    to their actual paths.
    """
    p = path.strip()

    # Treat backslashes as path separators (so '.\\foo\\bar.txt' works)
    p = p.replace("\\", "/")

    # Map common folder names to actual paths
    home = Path.home()
    folder_mapping = {
        "downloads": home / "Downloads",
        "download": home / "Downloads",
        "documents": home / "Documents",
        "document": home / "Documents",
        "desktop": home / "Desktop",
        "home": home,
    }

    # Split path into parts
    parts = p.split("/")

    # Filter out empty parts from leading/trailing slashes
    parts = [part for part in parts if part]

    if len(parts) > 0:
        first_part_lower = parts[0].lower()

        # Check if the first part matches a common folder name
        if first_part_lower in folder_mapping:
            # First part is a common folder - replace it with actual path
            actual_path = folder_mapping[first_part_lower]
            if len(parts) > 1:
                # Join remaining parts
                for part in parts[1:]:
                    actual_path = actual_path / part
            return actual_path

        # Check if any part in the middle matches (for "/path/to/downloads/file.txt" patterns)
        for i, part in enumerate(parts):
            part_lower = part.lower()
            if part_lower in folder_mapping and i > 0:  # Not the first part
                # Found a common folder name somewhere in the middle
                actual_base = folder_mapping[part_lower]
                if i + 1 < len(parts):
                    # There are more parts after the folder name
                    for remaining_part in parts[i + 1 :]:
                        actual_base = actual_base / remaining_part
                return actual_base

    # Handle explicit relative paths like "./file" or "../file"
    if p.startswith("./") or p.startswith("../") or p.startswith("."):
        return Path(p).expanduser().resolve()

    # Handle absolute paths (start with /)
    if p.startswith("/"):
        return Path(p).expanduser().resolve()

    # Handle home directory paths (start with ~)
    if p.startswith("~"):
        return Path(p).expanduser().resolve()

    # For anything else that doesn't match patterns above, treat as relative to CWD
    # This is the fallback for cases like "myfile.txt" or "subfolder/file.txt"
    # (but NOT "downloads/file.txt" which should have been caught above)
    return Path(p).expanduser().resolve()


def _fuzzy_match_score(query: str, target: str) -> float:
    """
    Calculate a fuzzy match score between query and target strings.
    Returns a score between 0 and 1, where 1 is a perfect match.

    Uses multiple strategies:
    1. Exact substring match (highest priority)
    2. Sequence matching (handles typos and partial matches)
    3. Extension-agnostic matching (if query has no extension)
    """
    query_lower = query.lower()
    target_lower = target.lower()

    # Perfect match
    if query_lower == target_lower:
        return 1.0

    # Exact substring match gets high score
    if query_lower in target_lower:
        # Bonus for matching the start of the filename
        if target_lower.startswith(query_lower):
            return 0.95
        return 0.85

    # Try matching without extension if query has no extension
    query_has_ext = "." in query and not query.endswith(".")
    target_path = Path(target)
    target_stem = target_path.stem.lower()

    if not query_has_ext:
        # Query has no extension, try matching against filename without extension
        if query_lower == target_stem:
            return 0.9
        if query_lower in target_stem:
            if target_stem.startswith(query_lower):
                return 0.8
            return 0.7

    # Use SequenceMatcher for fuzzy matching (handles typos)
    # Compare against both full name and stem
    full_ratio = SequenceMatcher(None, query_lower, target_lower).ratio()
    stem_ratio = SequenceMatcher(None, query_lower, target_stem).ratio()

    # Return the best score, with a slight preference for stem matches
    return max(full_ratio, stem_ratio * 1.05)


def get_tool_specs() -> str:
    """
    Return a string describing the tools and their argument schemas
    to inject into the ACTION system prompt.

    This text is what the model sees as {{TOOLS}}.
    """
    return textwrap.dedent(
        """
        1. \"run_shell\"
           - description: Run a shell command and capture stdout/stderr.
           - args schema:
             {
               "command": "string, the shell command to run"
             }

        2. \"read_file\"
           - description: Read a text file from disk (for inspection).
           - args schema:
             {
               "path": "string, absolute or relative file path",
               "max_bytes": "optional integer, maximum number of bytes to read (default 5000)"
             }

        3. \"write_file\"
           - description: Create or modify a text file on disk. Intended for small to medium text files (configs, scripts, code).
           - args schema:
             {
               "path": "string, file path - can use shortcuts like 'downloads/file.txt', 'documents/file.txt', 'desktop/file.txt'",
               "content": "string, full new content to write",
               "mode": "optional string, either 'overwrite' or 'append' (default 'overwrite')"
             }
           - notes:
             - When using 'overwrite', you replace the entire file content.
             - When using 'append', you add to the end of the file.
             - Path can use common folder names: 'downloads', 'documents', 'desktop' which will be resolved automatically.
             - Parent directories will be created automatically if they don't exist.
             - Examples: "downloads/jokes.txt", "documents/notes.md", "~/myfile.txt"
        
        4. "find_item"
           - description: Search for files or directories by name in sensible locations.
             The tool first searches recursively from the current working directory.
             If nothing is found, it also searches in the user's home folders such as
             Downloads, Documents, and Desktop (where they exist).
           - args schema:
             {
               "name": "string, filename or fragment to search for (e.g. 'welcome_prompt.md')",
               "max_results": "optional integer, maximum number of matches to return (default 20)"
             }
           - notes:
             - This is for discovery. It does not modify anything.
             - Use this when you are not sure where a file lives.

        5. "summarize_file"
           - description: Find a file by name and generate a concise summary of its contents.
             This is a SINGLE TOOL that both finds AND reads the file - do NOT use find_item first.
             Works with text files (txt, md, py, js, etc.), code files, and PDF documents.
             USE THIS TOOL whenever the user asks to "summarize", "explain", "overview", 
             "what does X contain", or "tell me about" a file.
           - args schema:
             {
               "name": "string, filename or fragment to search for (e.g. 'readme', 'config.py', 'presentation rubric')",
               "max_bytes": "optional integer, maximum bytes to read from file (default 10000)"
             }
           - notes:
             - This tool combines find and read - use it ALONE, not with find_item.
             - Handles fuzzy matching, so exact filename not required.
             - If multiple files match, it automatically uses the best match.
             - The content is displayed for the LLM to summarize in its response.
             - PDF support: extracts text from PDF pages automatically.

        6. "list_directory"
           - description: List contents of a directory with file/folder details.
             Shows names, types, sizes, and modification times.
           - args schema:
             {
               "path": "optional string, directory path (default is current directory)",
               "show_hidden": "optional boolean, show hidden files (default false)",
               "pattern": "optional string, filter by pattern (e.g. '*.py', '*.txt')"
             }
           - notes:
             - Use this to explore directory contents.
             - Supports common folder names like 'downloads', 'documents'.
             - Returns sorted list with files and directories clearly marked.

        7. "search_content"
           - description: Search for text within files in a directory tree.
             Like grep but more accessible - finds files containing specific text.
           - args schema:
             {
               "query": "string, text to search for",
               "path": "optional string, directory to search (default current directory)",
               "file_pattern": "optional string, limit to file types (e.g. '*.py', '*.txt')",
               "max_results": "optional integer, maximum results to return (default 20)",
               "case_sensitive": "optional boolean, case-sensitive search (default false)"
             }
           - notes:
             - Searches recursively through all subdirectories.
             - Shows filename, line number, and matching line context.
             - Use for "find files containing X" or "where is X mentioned".

        8. "get_file_info"
           - description: Get detailed metadata about a specific file.
             Returns size, dates, permissions, type, and other information.
           - args schema:
             {
               "path": "string, path to the file"
             }
           - notes:
             - Shows: size, creation date, modification date, file type, permissions.
             - Works with common folder shortcuts like 'downloads/file.txt'.
             - Useful for checking file properties before operations.

        9. "copy_file"
           - description: Copy a file from source to destination.
             Creates a duplicate of the file at the new location.
           - args schema:
             {
               "source": "string, path to source file",
               "destination": "string, path to destination (file or directory)"
             }
           - notes:
             - If destination is a directory, uses same filename.
             - Creates parent directories if needed.
             - Will not overwrite existing files without confirmation.

        10. "move_file"
            - description: Move or rename a file from source to destination.
              Relocates the file without creating a copy.
            - args schema:
              {
                "source": "string, path to source file",
                "destination": "string, path to destination (file or directory)"
              }
            - notes:
              - If destination is a directory, uses same filename.
              - Can be used to rename files (same directory, different name).
              - Creates parent directories if needed.

        11. "compare_files"
            - description: Compare two files and show their differences.
              Highlights what's changed between the files.
            - args schema:
              {
                "file1": "string, path to first file",
                "file2": "string, path to second file",
                "context_lines": "optional integer, lines of context to show (default 3)"
              }
            - notes:
              - Shows line-by-line differences.
              - Useful for reviewing changes between versions.
              - Returns unified diff format.

        12. "extract_archive"
            - description: Extract/unzip compressed archive files.
              Supports .zip, .tar, .tar.gz, .tgz formats.
            - args schema:
              {
                "archive_path": "string, path to archive file",
                "destination": "optional string, where to extract (default is same directory)"
              }
            - notes:
              - Automatically detects archive format.
              - Creates destination directory if needed.
              - Lists extracted files.
        """
    ).strip()


# ---------- Tool implementations ----------


def run_shell(command: str) -> Dict[str, Any]:
    """
    Run a shell command safely. This is still powerful, so we do basic
    guardrails in executor before calling this.
    """
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "ok": True,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def read_file(path: str, max_bytes: int = 5000) -> Dict[str, Any]:
    try:
        p = _normalize_path(path)
        data = p.read_bytes()
        snippet = data[:max_bytes]
        try:
            text = snippet.decode("utf-8", errors="replace")
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"decode error: {e}"}

        truncated = len(data) > max_bytes
        return {
            "ok": True,
            "path": str(p),
            "content": text,
            "truncated": truncated,
        }
    except FileNotFoundError:
        return {"ok": False, "error": f"file not found: {path}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def write_file(path: str, content: str, mode: str = "overwrite") -> Dict[str, Any]:
    """
    Write text content to a file.

    mode:
      - 'overwrite': replace entire file (truncate or create).
      - 'append'   : append to the end of the file (create if missing).
    """
    try:
        p = _normalize_path(path)

        # Map logical modes to file modes
        if mode == "append":
            file_mode = "a"
        else:
            # Default to overwrite if anything else is passed
            file_mode = "w"
            mode = "overwrite"

        # Create parent directory if it doesn't exist
        if not p.parent.exists():
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                return {
                    "ok": False,
                    "error": f"could not create parent directory {p.parent}: {e}",
                }

        text = str(content)

        before_exists = p.exists()
        before_size = p.stat().st_size if before_exists else 0

        with p.open(file_mode, encoding="utf-8") as f:
            f.write(text)

        after_size = p.stat().st_size

        return {
            "ok": True,
            "path": str(p),
            "mode": mode,
            "existed_before": before_exists,
            "bytes_before": before_size,
            "bytes_after": after_size,
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


def find_item(
    name: str, max_results: int = 20, fuzzy_threshold: float = 0.6
) -> Dict[str, Any]:
    """
    Search for files/directories using fuzzy matching.

    Handles:
    - Exact matches and substring matches
    - Spelling errors and typos
    - Missing file extensions
    - Partial name matches

    Strategy:
      1. Search recursively from the current working directory.
      2. If fewer than max_results are found, also search common home subdirs:
         ~/Downloads, ~/Documents, ~/Desktop (if they exist).
      3. Use fuzzy matching to score each potential match.
      4. Return results sorted by match score (best matches first).

    Args:
      name: Filename or fragment to search for
      max_results: Maximum number of results to return
      fuzzy_threshold: Minimum similarity score (0-1) to include a result

    Returns:
      {
        "ok": True,
        "query": name,
        "roots": [list of roots searched],
        "results": [
          {
            "path": "...",
            "root": "...",
            "is_dir": bool,
            "size": int | null,
            "match_score": float  # 0-1, how well it matched
          },
          ...
        ]
      }
    """
    query = name.strip()
    if not query:
        return {"ok": False, "error": "empty name for find_item"}

    roots: List[Path] = []
    cwd = Path.cwd()
    roots.append(cwd)

    home = Path.home()
    for sub in ("Downloads", "Documents", "Desktop"):
        candidate = home / sub
        if candidate.exists():
            roots.append(candidate)

    # Deduplicate roots
    unique_roots: List[Path] = []
    seen = set()
    for r in roots:
        rp = r.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique_roots.append(rp)
    roots = unique_roots

    # Collect all candidates with their scores
    candidates: List[Dict[str, Any]] = []

    for root in roots:
        try:
            for path in root.rglob("*"):
                # Calculate fuzzy match score
                score = _fuzzy_match_score(query, path.name)

                # Only include if score meets threshold
                if score >= fuzzy_threshold:
                    try:
                        is_dir = path.is_dir()
                        size = path.stat().st_size if path.is_file() else None
                    except OSError:
                        is_dir = path.is_dir()
                        size = None

                    candidates.append(
                        {
                            "path": str(path),
                            "root": str(root),
                            "is_dir": is_dir,
                            "size": size,
                            "match_score": score,
                        }
                    )
        except Exception:
            # Ignore unreadable roots
            continue

    # Sort by match score (best matches first)
    candidates.sort(key=lambda x: x["match_score"], reverse=True)

    # Limit to max_results
    results = candidates[:max_results]

    return {
        "ok": True,
        "query": query,
        "roots": [str(r) for r in roots],
        "results": results,
        "fuzzy_threshold": fuzzy_threshold,
    }


def summarize_file(name: str, max_bytes: int = 10000) -> Dict[str, Any]:
    """
    Find a file and generate a summary of its contents.

    Strategy:
      1. Use fuzzy search to find the file
      2. If multiple matches, use the best match (highest score)
      3. Read the file content (limited to max_bytes)
      4. Generate a structured summary

    Args:
      name: Filename or fragment to search for
      max_bytes: Maximum bytes to read from the file (default 10000)

    Returns:
      {
        "ok": True,
        "query": name,
        "file_path": "path to the file",
        "file_size": int,
        "match_score": float,
        "content_preview": "first portion of content for summarization",
        "truncated": bool,
        "multiple_matches": bool,  # True if multiple files were found
        "match_count": int,
      }
    """
    # First, find the file using fuzzy search
    find_result = find_item(name=name, max_results=5, fuzzy_threshold=0.6)

    if not find_result.get("ok"):
        return {"ok": False, "error": find_result.get("error", "find failed")}

    results = find_result.get("results", [])

    if not results:
        return {
            "ok": False,
            "error": f"No files found matching '{name}'. Try a different search term.",
        }

    # Filter to only files (not directories)
    files = [r for r in results if not r.get("is_dir", False)]

    if not files:
        return {
            "ok": False,
            "error": f"Found {len(results)} match(es), but all were directories. Need a file to summarize.",
        }

    # Use the best match (first one after sorting by score)
    best_match = files[0]
    file_path = best_match["path"]
    match_score = best_match.get("match_score", 0)

    # Check if it's a readable text file by extension
    text_extensions = {
        ".txt",
        ".md",
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".json",
        ".xml",
        ".html",
        ".css",
        ".scss",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".sh",
        ".bash",
        ".zsh",
        ".fish",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".rs",
        ".go",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".r",
        ".sql",
        ".log",
        ".csv",
        ".rst",
        ".tex",
    }

    file_ext = Path(file_path).suffix.lower()

    # Special handling for PDFs
    if file_ext == ".pdf":
        if not HAS_PDF_SUPPORT:
            return {
                "ok": False,
                "error": f"PDF support not available. Install pdfplumber to read PDFs: pip install pdfplumber",
            }

        try:
            p = Path(file_path)
            if not p.exists():
                return {"ok": False, "error": f"File not found: {file_path}"}

            file_size = p.stat().st_size

            # Extract text from PDF using pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                total_chars = 0

                # Extract text from each page until we reach max_bytes
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                        total_chars += len(page_text)

                        # Stop if we've extracted enough
                        if total_chars >= max_bytes:
                            break

                content = "\n\n".join(text_parts)

                # Limit to max_bytes
                if len(content) > max_bytes:
                    content = content[:max_bytes]
                    truncated = True
                else:
                    truncated = len(pdf.pages) > len(text_parts)

                if not content.strip():
                    return {
                        "ok": False,
                        "error": f"Could not extract text from PDF. It may be image-based or encrypted.",
                    }

                return {
                    "ok": True,
                    "query": name,
                    "file_path": file_path,
                    "file_size": file_size,
                    "match_score": match_score,
                    "content_preview": content,
                    "truncated": truncated,
                    "multiple_matches": len(files) > 1,
                    "match_count": len(files),
                    "file_type": "pdf",
                    "page_count": len(pdf.pages),
                }
        except Exception as e:
            return {"ok": False, "error": f"Error reading PDF: {e}"}

    if file_ext and file_ext not in text_extensions:
        return {
            "ok": False,
            "error": f"File type '{file_ext}' may not be a text file. File: {file_path}",
        }

    # Read the file content
    try:
        p = Path(file_path)
        if not p.exists():
            return {"ok": False, "error": f"File not found: {file_path}"}

        file_size = p.stat().st_size
        data = p.read_bytes()

        # Limit to max_bytes
        snippet = data[:max_bytes]
        truncated = len(data) > max_bytes

        try:
            content = snippet.decode("utf-8", errors="replace")
        except Exception as e:
            return {"ok": False, "error": f"Could not decode file as text: {e}"}

        return {
            "ok": True,
            "query": name,
            "file_path": file_path,
            "file_size": file_size,
            "match_score": match_score,
            "content_preview": content,
            "truncated": truncated,
            "multiple_matches": len(files) > 1,
            "match_count": len(files),
        }

    except FileNotFoundError:
        return {"ok": False, "error": f"File not found: {file_path}"}
    except Exception as e:
        return {"ok": False, "error": f"Error reading file: {e}"}


def list_directory(
    path: str = ".", show_hidden: bool = False, pattern: str = None
) -> Dict[str, Any]:
    """
    List contents of a directory with details.
    """
    try:
        p = _normalize_path(path)

        if not p.exists():
            return {"ok": False, "error": f"Directory not found: {path}"}

        if not p.is_dir():
            return {"ok": False, "error": f"Path is not a directory: {path}"}

        items = []

        for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            # Skip hidden files unless requested
            if not show_hidden and item.name.startswith("."):
                continue

            # Apply pattern filter if provided
            if pattern:
                import fnmatch

                if not fnmatch.fnmatch(item.name, pattern):
                    continue

            try:
                stat = item.stat()
                is_dir = item.is_dir()

                items.append(
                    {
                        "name": item.name,
                        "is_dir": is_dir,
                        "size": stat.st_size if not is_dir else None,
                        "modified": stat.st_mtime,
                        "path": str(item),
                    }
                )
            except (PermissionError, OSError):
                # Skip items we can't access
                continue

        return {
            "ok": True,
            "path": str(p),
            "items": items,
            "count": len(items),
        }

    except Exception as e:
        return {"ok": False, "error": f"Error listing directory: {e}"}


def search_content(
    query: str,
    path: str = ".",
    file_pattern: str = None,
    max_results: int = 20,
    case_sensitive: bool = False,
) -> Dict[str, Any]:
    """
    Search for text within files.
    """
    try:
        p = _normalize_path(path)

        if not p.exists():
            return {"ok": False, "error": f"Directory not found: {path}"}

        if not p.is_dir():
            return {"ok": False, "error": f"Path is not a directory: {path}"}

        results = []
        search_query = query if case_sensitive else query.lower()

        # Determine glob pattern
        glob_pattern = "**/*" if not file_pattern else f"**/{file_pattern}"

        for file_path in p.glob(glob_pattern):
            if not file_path.is_file():
                continue

            # Skip binary files and very large files
            try:
                if file_path.stat().st_size > 10_000_000:  # Skip files > 10MB
                    continue

                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line_num, line in enumerate(f, 1):
                        check_line = line if case_sensitive else line.lower()

                        if search_query in check_line:
                            results.append(
                                {
                                    "file": str(
                                        file_path.relative_to(p)
                                        if file_path.is_relative_to(p)
                                        else file_path
                                    ),
                                    "line_number": line_num,
                                    "line_content": line.rstrip(),
                                }
                            )

                            if len(results) >= max_results:
                                break

                if len(results) >= max_results:
                    break

            except (PermissionError, UnicodeDecodeError, OSError):
                # Skip files we can't read
                continue

        return {
            "ok": True,
            "query": query,
            "search_path": str(p),
            "results": results,
            "result_count": len(results),
            "truncated": len(results) >= max_results,
        }

    except Exception as e:
        return {"ok": False, "error": f"Error searching content: {e}"}


def get_file_info(path: str) -> Dict[str, Any]:
    """
    Get detailed metadata about a file.
    """
    try:
        p = _normalize_path(path)

        if not p.exists():
            return {"ok": False, "error": f"File not found: {path}"}

        stat = p.stat()
        is_dir = p.is_dir()

        # Determine file type
        if is_dir:
            file_type = "directory"
        else:
            suffix = p.suffix.lower()
            type_map = {
                ".py": "Python script",
                ".js": "JavaScript file",
                ".txt": "Text file",
                ".md": "Markdown file",
                ".json": "JSON file",
                ".pdf": "PDF document",
                ".zip": "ZIP archive",
                ".tar": "TAR archive",
                ".gz": "GZIP archive",
            }
            file_type = type_map.get(
                suffix, f"{suffix[1:].upper()} file" if suffix else "Unknown"
            )

        import time

        file_info = {
            "path": str(p),
            "name": p.name,
            "type": file_type,
            "is_directory": is_dir,
            "size": f"{stat.st_size:,} bytes",
            "created": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_ctime)
            ),
            "modified": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)
            ),
            "accessed": time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stat.st_atime)
            ),
            "permissions": oct(stat.st_mode)[-3:],
        }

        return {
            "ok": True,
            "file_info": file_info,
        }

    except Exception as e:
        return {"ok": False, "error": f"Error getting file info: {e}"}


def copy_file(source: str, destination: str) -> Dict[str, Any]:
    """
    Copy a file from source to destination.
    """
    try:
        import shutil

        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.exists():
            return {"ok": False, "error": f"Source file not found: {source}"}

        if src.is_dir():
            return {
                "ok": False,
                "error": f"Source is a directory, not a file: {source}",
            }

        # If destination is a directory, use source filename
        if dst.exists() and dst.is_dir():
            dst = dst / src.name

        # Check if destination already exists
        if dst.exists():
            return {
                "ok": False,
                "error": f"Destination already exists: {dst}. Use move_file to overwrite.",
            }

        # Create parent directory if needed
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Copy the file
        shutil.copy2(src, dst)

        return {
            "ok": True,
            "source": str(src),
            "destination": str(dst),
            "size": dst.stat().st_size,
            "message": "File copied successfully",
        }

    except Exception as e:
        return {"ok": False, "error": f"Error copying file: {e}"}


def move_file(source: str, destination: str) -> Dict[str, Any]:
    """
    Move or rename a file.
    """
    try:
        import shutil

        src = _normalize_path(source)
        dst = _normalize_path(destination)

        if not src.exists():
            return {"ok": False, "error": f"Source file not found: {source}"}

        if src.is_dir():
            return {
                "ok": False,
                "error": f"Source is a directory, not a file: {source}",
            }

        # If destination is a directory, use source filename
        if dst.exists() and dst.is_dir():
            dst = dst / src.name

        # Create parent directory if needed
        dst.parent.mkdir(parents=True, exist_ok=True)

        # Move the file
        shutil.move(str(src), str(dst))

        return {
            "ok": True,
            "source": str(src),
            "destination": str(dst),
            "operation": "renamed" if src.parent == dst.parent else "moved",
            "message": "File moved successfully",
        }

    except Exception as e:
        return {"ok": False, "error": f"Error moving file: {e}"}


def compare_files(file1: str, file2: str, context_lines: int = 3) -> Dict[str, Any]:
    """
    Compare two files and show differences.
    """
    try:
        import difflib

        f1 = _normalize_path(file1)
        f2 = _normalize_path(file2)

        if not f1.exists():
            return {"ok": False, "error": f"First file not found: {file1}"}

        if not f2.exists():
            return {"ok": False, "error": f"Second file not found: {file2}"}

        # Read both files
        try:
            with open(f1, "r", encoding="utf-8") as file:
                lines1 = file.readlines()
        except UnicodeDecodeError:
            return {"ok": False, "error": f"Cannot read {file1} as text (binary file?)"}

        try:
            with open(f2, "r", encoding="utf-8") as file:
                lines2 = file.readlines()
        except UnicodeDecodeError:
            return {"ok": False, "error": f"Cannot read {file2} as text (binary file?)"}

        # Generate unified diff
        diff = difflib.unified_diff(
            lines1,
            lines2,
            fromfile=str(f1),
            tofile=str(f2),
            lineterm="",
            n=context_lines,
        )

        diff_lines = list(diff)

        if not diff_lines:
            return {
                "ok": True,
                "file1": str(f1),
                "file2": str(f2),
                "identical": True,
                "diff": "Files are identical",
            }

        return {
            "ok": True,
            "file1": str(f1),
            "file2": str(f2),
            "identical": False,
            "diff": "\n".join(diff_lines),
            "changes": len(
                [l for l in diff_lines if l.startswith("+") or l.startswith("-")]
            ),
        }

    except Exception as e:
        return {"ok": False, "error": f"Error comparing files: {e}"}


def extract_archive(archive_path: str, destination: str = None) -> Dict[str, Any]:
    """
    Extract compressed archive files.
    """
    try:
        import zipfile
        import tarfile

        arc = _normalize_path(archive_path)

        if not arc.exists():
            return {"ok": False, "error": f"Archive not found: {archive_path}"}

        # Determine destination
        if destination:
            dest = _normalize_path(destination)
        else:
            dest = arc.parent / arc.stem

        dest.mkdir(parents=True, exist_ok=True)

        extracted_files = []

        # Detect archive type and extract
        if arc.suffix.lower() == ".zip":
            with zipfile.ZipFile(arc, "r") as zip_ref:
                zip_ref.extractall(dest)
                extracted_files = zip_ref.namelist()

        elif arc.suffix.lower() in [".tar", ".gz", ".tgz"] or arc.name.endswith(
            ".tar.gz"
        ):
            with tarfile.open(arc, "r:*") as tar_ref:
                tar_ref.extractall(dest)
                extracted_files = tar_ref.getnames()

        else:
            return {
                "ok": False,
                "error": f"Unsupported archive format: {arc.suffix}. Supported: .zip, .tar, .tar.gz, .tgz",
            }

        return {
            "ok": True,
            "archive": str(arc),
            "destination": str(dest),
            "extracted_files": extracted_files[:20],  # Limit to first 20 for display
            "total_files": len(extracted_files),
        }

    except Exception as e:
        return {"ok": False, "error": f"Error extracting archive: {e}"}
