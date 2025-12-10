# Terminal Agent

A powerful, LLM-powered terminal agent that lets you control your computer using natural language. Built with Python, it uses local LLMs (via Ollama) to understand your requests and perform file operations, system commands, and intelligent searches.

## ✨ Features

### Core Capabilities
- **Natural Language Interface** - Control your system using plain English commands
- **LLM-Powered Planning** - Automatically breaks down complex tasks into actionable steps
- **Interactive Confirmations** - Review and approve actions before execution
- **Rich Terminal UI** - Beautiful, color-coded output with tables and panels

### File Operations
- **Smart File Search** (`find_item`) - Fuzzy matching that handles typos and missing extensions
  - Automatic extension detection (search "readme" finds "readme.md")
  - Match scoring with visual confidence indicators
  - Searches current directory, Downloads, Documents, and Desktop
  - Option to immediately read high-confidence matches

- **File Reading** (`read_file`) - View file contents with truncation support
  - Configurable size limits
  - UTF-8 encoding with error handling

- **File Writing** (`write_file`) - Create or modify files with preview
  - Append or overwrite modes
  - Before/after content preview
  - Auto-creates parent directories
  - Intelligent path normalization (downloads → ~/Downloads)

- **File Summarization** (`summarize_file`) - AI-generated summaries of file contents
  - Supports text files and PDFs
  - Extracts key information automatically
  - Shows file metadata and content preview

- **PDF Support** - Extract and summarize PDF documents
  - Multi-page text extraction
  - Page count and metadata display

### File Management
- **Directory Listing** (`list_directory`) - Browse folder contents
  - Shows file type, size, and modification date
  - Filter by pattern (*.py, *.txt, etc.)
  - Toggle hidden files visibility
  - Sorted, formatted table output

- **Content Search** (`search_content`) - Grep-like recursive text search
  - Search across multiple files
  - Shows file path, line number, and content
  - Case-sensitive/insensitive options
  - Filter by file pattern
  - Configurable result limits

- **File Info** (`get_file_info`) - Detailed file metadata
  - File type, size, permissions
  - Created, modified, and accessed dates
  - Human-readable formatting

- **File Copy** (`copy_file`) - Duplicate files or directories
  - Auto-creates destination folders
  - Prevents accidental overwrites
  - Smart directory handling

- **File Move** (`move_file`) - Move or rename files
  - Cross-directory moves
  - Rename detection
  - Destination folder creation

- **File Comparison** (`compare_files`) - Compare two text files
  - Unified diff format with context lines
  - Identical file detection
  - Color-coded output

- **Archive Extraction** (`extract_archive`) - Unzip/untar archives
  - Supports .zip, .tar, .tar.gz, .tgz
  - Auto-detects format
  - Lists extracted files
  - Creates destination folders

### System Integration
- **Shell Commands** (`run_shell`) - Execute terminal commands safely
  - Captures stdout and stderr
  - Return code display
  - Built-in safety checks (blocks dangerous commands like `rm -rf /`)

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.13+** (required)
- **Poetry** (for dependency management)
- **Ollama** (for local LLM inference)
- **LLM Model** (e.g., `llama3.2:3b` or similar)
- **make** (optional, for easier commands)

### Quick Start with Makefile (Recommended)

The project includes a comprehensive Makefile for easy interaction:

```bash
# See all available commands
make help

# Complete setup (install + start Ollama + pull model)
make install        # Install dependencies
make start-ollama   # Start Ollama (in new terminal)
make pull-model     # Download LLM model
make test-connection # Verify everything works

# Ask questions
make ask QUERY="what is Python?"

# Execute actions
make do QUERY="find readme file"

# Preview actions without executing
make dry-run QUERY="delete old files"
```

### Manual Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/SenseOfHumor/terminal-agent.git
   cd terminal-agent
   ```

2. **Install dependencies with Poetry**
   ```bash
   poetry install
   ```

3. **Set up Ollama** (if not already installed)
   ```bash
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ```

4. **Start Ollama service**
   ```bash
   ollama serve
   ```

5. **Pull a suitable model** (in a new terminal)
   ```bash
   ollama pull llama3.2:3b
   ```

6. **Configure the model** (optional)
   
   By default, the agent uses the model configured in `service/llm_client.py`. To change it, edit the file:
   ```python
   # In service/llm_client.py
   self.model = "your-model-name"  # e.g., "llama3.2:3b"
   ```

---

## 📖 Usage

### Using the Makefile (Easy Mode)

```bash
# Ask questions (no actions)
make ask QUERY="explain fuzzy matching"

# Execute actions
make do QUERY="list files in downloads"
make do QUERY="find all python files"
make do QUERY="search for TODO in project"

# Dry run (preview only)
make dry-run QUERY="delete temporary files"

# Quick examples
make example-search           # Search for files
make example-list             # List directory
make example-info             # Show file info
make example-summarize        # Summarize a file
make example-search-content   # Search within files

# Development
make clean                    # Clean temporary files
make lint                     # Run linters
make format                   # Format code
make check-deps               # Check for updates
make update-deps              # Update dependencies

# Model management
make list-models              # List available models
make switch-model MODEL=llama3.2:7b  # Switch model

# Utilities
make backup                   # Backup project
make diagnose                 # Run diagnostics
make uninstall                # Remove everything
```

### Using Poetry Directly

#### Two Modes

#### Ask Mode - Information Only
Get answers without executing any actions:
```bash
poetry run python agent_cli.py ask "what is fuzzy matching?"
poetry run python agent_cli.py ask "explain how file permissions work"
```

#### Do Mode - Execute Actions
Perform actual system operations (with confirmation):
```bash
poetry run python agent_cli.py do "find my readme file"
poetry run python agent_cli.py do "list files in downloads folder"
poetry run python agent_cli.py do "search for 'TODO' in python files"
```

### Example Commands

**File Search & Reading**
```bash
poetry run python agent_cli.py do "find test_agent.txt and read it"
poetry run python agent_cli.py do "find all python files in the project"
```

**File Management**
```bash
poetry run python agent_cli.py do "copy test.txt to downloads folder"
poetry run python agent_cli.py do "move old_file.txt to archive directory"
poetry run python agent_cli.py do "show me information about pyproject.toml"
```

**Content Search**
```bash
poetry run python agent_cli.py do "search for 'def execute' in core directory"
poetry run python agent_cli.py do "find all TODOs in python files"
```

**Archives**
```bash
poetry run python agent_cli.py do "extract project.zip to extracted_folder"
```

**File Comparison**
```bash
poetry run python agent_cli.py do "compare old_config.json with new_config.json"
```

**PDF Summarization**
```bash
poetry run python agent_cli.py do "summarize presentation.pdf"
```

**Dry Run Mode**
```bash
# See what would happen without executing
poetry run python agent_cli.py do "delete all temporary files" --dry-run
```

---

## 🔧 Configuration

### LLM Settings
Edit `service/llm_client.py`:
- `model`: Change the Ollama model
- `base_url`: Change Ollama API endpoint (default: `http://localhost:11434`)
- `timeout`: Adjust request timeout

### Safety Controls
Edit `core/executor.py`:
- `DANGEROUS_SUBSTRINGS`: Add/remove blocked command patterns

### Path Normalization
The agent automatically maps common folder names:
- `downloads` → `~/Downloads`
- `documents` → `~/Documents`
- `desktop` → `~/Desktop`
- `home` → `~/`

---

## 🛠️ Troubleshooting

### Issue: "Connection refused" or "Cannot connect to Ollama"

**Solution 1: Check Ollama is running**
```bash
# With Makefile
make start-ollama   # In separate terminal
make test-connection

# Or manually
ollama serve
```

**Solution 2: Use a different port**
```bash
# Start on custom port
OLLAMA_HOST=127.0.0.1:11435 ollama serve

# Update service/llm_client.py
self.base_url = "http://127.0.0.1:11435"
```

**Solution 3: Run diagnostics**
```bash
make diagnose   # Check system status
```

**Solution 4: Use a remote Ollama instance**
```python
# In service/llm_client.py
self.base_url = "http://your-remote-host:11434"
```

---

### Issue: "Model not found"

**Solution: Pull the model**
```bash
# With Makefile
make list-models                    # See available models
make pull-model                     # Pull default model
make switch-model MODEL=llama3.2:7b # Pull specific model

# Or manually
ollama list
ollama pull llama3.2:3b

# Update service/llm_client.py to match
self.model = "llama3.2:3b"
```

---

### Issue: "Could not generate a valid action plan"

**Solution 1: Rephrase your request**
```bash
# Instead of vague:
make do QUERY="do something with files"

# Be specific:
make do QUERY="list all text files in current directory"
```

**Solution 2: Check model compatibility**
- Smaller models (<3B parameters) may struggle with complex planning
- Try a larger model: `ollama pull llama3.2:7b`

**Solution 3: Check the logs**
The agent prints the raw LLM response if JSON parsing fails. Look for malformed JSON.

---

### Issue: "PDF support not available"

**Solution: Install pdfplumber**
```bash
poetry add pdfplumber
# or
pip install pdfplumber
```

---

### Issue: Fuzzy search not finding files

**Solution 1: Check search paths**
The search automatically covers:
- Current working directory
- `~/Downloads`
- `~/Documents`
- `~/Desktop`

**Solution 2: Be more specific**
```bash
# Instead of:
poetry run python agent_cli.py do "find report"

# Try:
poetry run python agent_cli.py do "find report in downloads folder"
```

**Solution 3: Adjust fuzzy threshold**
Edit `core/tools.py`:
```python
def find_item(...):
    fuzzy_threshold = 0.6  # Lower = more matches (e.g., 0.4)
```

---

### Issue: "Permission denied" errors

**Solution 1: Check file permissions**
```bash
ls -la <file>
chmod +r <file>  # Add read permission
```

**Solution 2: Run with appropriate permissions**
```bash
# For system files (use cautiously)
sudo poetry run python agent_cli.py do "read system file"
```

---

### Issue: Shell commands not working

**Solution 1: Check if command is blocked**
Dangerous commands are blocked by default. Edit `core/executor.py`:
```python
DANGEROUS_SUBSTRINGS = [
    "rm -rf /",
    "mkfs",
    ":(){ :|:& };:",  # fork bomb
    # Add or remove patterns here
]
```

**Solution 2: Use absolute paths**
```bash
# Instead of:
poetry run python agent_cli.py do "run cat file.txt"

# Try:
poetry run python agent_cli.py do "run cat /full/path/to/file.txt"
```

---

### Issue: Slow response times

**Solution 1: Use a faster model**
```bash
# Smaller, faster models
ollama pull llama3.2:1b
ollama pull phi3:mini
```

**Solution 2: Increase timeout**
Edit `service/llm_client.py`:
```python
self.timeout = 60  # Increase from default 30
```

**Solution 3: Use GPU acceleration**
Ensure Ollama is using your GPU (Should be default on M series Mac models):
```bash
# Check GPU usage
nvidia-smi  # NVIDIA GPUs
```

---

### Issue: Out of memory

**Solution: Use a smaller model**
```bash
# Quantized models use less RAM
ollama pull llama3.2:3b-q4_0
```

---

## 🏗️ Project Structure

```
terminal-agent/
├── agent_cli.py          # Main CLI entry point
├── core/
│   ├── executor.py       # Action execution & display
│   ├── planner.py        # LLM plan parsing
│   └── tools.py          # Tool implementations
├── models/
│   ├── __init__.py
│   ├── action.py         # Action data model
│   └── plan.py           # Plan data model
├── service/
│   └── llm_client.py     # Ollama API client
├── patterns/
│   └── welcome_prompt.md # System prompts
├── pyproject.toml        # Dependencies
└── README.md             # This file
```

---

## 🤝 Contributing

Still Figuring out the potential of the application. Although currently not accepting contributions, feel free to leave a suggestion!

---


## ⚠️ Safety Notice

This agent executes real system commands. Always:
- ✅ Review the planned actions before confirming
- ✅ Use `--dry-run` for testing
- ✅ Keep dangerous command patterns blocked
- ❌ Don't run untrusted queries
- ❌ Don't disable safety checks without understanding risks

---

## 🙏 Acknowledgments

- Built with [Ollama](https://ollama.com) for local LLM inference
- UI powered by [Rich](https://github.com/Textualize/rich)
- PDF support via [pdfplumber](https://github.com/jsvine/pdfplumber)
