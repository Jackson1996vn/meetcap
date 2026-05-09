# Phase 1: Foundation - Research

**Researched:** 2026-05-09
**Domain:** Python CLI packaging (uv + pyproject.toml + click + platformdirs + TOML config)
**Confidence:** HIGH

## Summary

This phase builds the installable Python package shell for `meetcap`. The core tasks are: (1) scaffold a `src/`-layout Python package with `uv`, (2) wire up a `click`-based CLI entry point, (3) implement TOML config read/write using stdlib `tomllib` + `tomli-w`, and (4) add a first-run interactive wizard using `click.prompt`. No audio recording code is written — the phase ends with a working `meetcap` CLI that installs via `pipx install .` and stores user config.

All libraries in the locked stack are well-established, actively maintained, and confirmed at current versions via the package index. The architecture is straightforward: a single `src/meetcap/` package with `cli.py` as the entry point and `config.py` owning the config read/write lifecycle.

**Primary recommendation:** Use `uv init --app --package` to scaffold the project with `src/` layout, `uv_build` as the build backend (confirmed pipx-compatible), `click 8.3.3` for the CLI, `platformdirs 4.9.6` for OS-appropriate config paths, and `tomllib` (stdlib) + `tomli-w 1.2.0` for TOML read/write.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Use `uv` as the build tool with `pyproject.toml` configuration
- **D-02:** Entry point registered as `[project.scripts] meetcap = "meetcap.cli:main"`
- **D-03:** User must explicitly configure recordings directory — no silent defaults. Config is set either via first-run interactive prompt or via `meetcap config`
- **D-04:** Config file is TOML format at platform-appropriate path (use `platformdirs` for cross-platform resolution)
- **D-05:** Required config keys for milestone 1: `recordings_dir`
- **D-06:** API keys are read from environment variables only, never stored in config file
- **D-07:** When user runs `meetcap` with no config, show interactive prompt asking for required settings (recordings directory), save to config, then proceed
- **D-08:** When user runs `meetcap` without a title, auto-generate a timestamp-based title (e.g., `2026-05-09-1430`) — no prompt, just start
- **D-09:** `meetcap "<title>"` accepts a user-provided title for the recording session

### Claude's Discretion
- Project layout (src/meetcap/ vs flat meetcap/) — Claude picks best approach

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | User can start recording with `meetcap` or `meetcap "<title>"` | `invoke_without_command=True` on click group; optional `[TITLE]` argument on the default command |
| CLI-02 | Config file at platform-appropriate path (TOML format) with recordings_dir | `platformdirs.user_config_dir('meetcap')` → `config.toml`; read with `tomllib`; write with `tomli-w` |
| CLI-03 | First run prompts for recordings directory if not configured | Config absence detected on startup; `click.prompt()` collects path; written via `tomli-w` |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| CLI entry point + argument parsing | CLI layer (`cli.py`) | — | Click owns all user-facing input; no web/API layer exists |
| Config read/write | Config module (`config.py`) | — | Single module isolates OS-path logic from CLI and recording logic |
| First-run wizard | CLI layer (`cli.py`) | Config module | CLI drives the prompt; config module persists the result |
| Recording session (stub) | CLI layer (`cli.py`) | — | Phase 2 fills; Phase 1 only prints a placeholder |
| OS path resolution | Config module (`config.py`) | — | `platformdirs` called once at config load time |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| click | 8.3.3 | CLI argument parsing, prompts, help text | De facto standard Python CLI toolkit; decorator-based API; built-in prompt/confirm [VERIFIED: pip index] |
| platformdirs | 4.9.6 | OS-appropriate config directory paths | Replaces `appdirs`; used by pip, black, mypy; handles macOS/Windows/Linux correctly [VERIFIED: pip index] |
| tomli-w | 1.2.0 | Write TOML config files | Only well-maintained TOML writer; counterpart to stdlib `tomllib` [VERIFIED: pip index, PyPI] |

### Supporting (stdlib — no install needed)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tomllib | stdlib (Python 3.11+) | Read TOML config files | Always — no external dep needed for reading [VERIFIED: Python 3.11 stdlib] |
| pathlib | stdlib | File path manipulation, mkdir, exists | All file/directory operations |
| datetime | stdlib | Timestamp-based title generation | Auto-title when user runs `meetcap` with no title argument |

### Build System
| Tool | Version | Purpose | Why |
|------|---------|---------|-----|
| uv | 0.9.13 | Package management, venv, build | Locked (D-01); fastest Python tool runner; produces pip-compatible wheels [VERIFIED: uv --version] |
| uv_build | (bundled with uv) | Build backend in pyproject.toml | Default for `uv init --app --package`; produces standard PEP 517 wheels installable by pipx [VERIFIED: PyPI, web search] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv_build | hatchling | hatchling is more widely adopted but uv_build is now stable and produces identical wheels; uv_build auto-updates with uv |
| uv_build | setuptools | setuptools is legacy; no advantage here |
| tomli-w | tomlkit | tomlkit preserves comments/formatting (useful for human-edited files); heavier; overkill for a generated config file |
| platformdirs | hardcoded paths | Breaks on Windows; platformdirs is 2 lines |

**Installation:**
```bash
uv add click platformdirs tomli-w
```

**Version verification:** Confirmed against pip index on 2026-05-09:
- click: latest=8.3.3 [VERIFIED: pip index versions click]
- platformdirs: latest=4.9.6 [VERIFIED: pip index versions platformdirs]
- tomli-w: latest=1.2.0 [VERIFIED: pip index versions tomli-w]

## Architecture Patterns

### System Architecture Diagram

```
User invokes: meetcap [TITLE]
        |
        v
  cli.py: main()          <-- click group, invoke_without_command=True
        |
        +-- config.py: load_config()
        |       |
        |       +-- platformdirs.user_config_dir('meetcap') --> OS path
        |       +-- tomllib.load() if file exists
        |       +-- returns None if file missing
        |
        +-- [config is None?]
        |       YES --> first_run_wizard()
        |               |
        |               +-- click.prompt("Recordings directory")
        |               +-- pathlib.Path.mkdir(parents=True, exist_ok=True)
        |               +-- config.py: save_config()
        |                       |
        |                       +-- tomli_w.dump() to config.toml
        |
        +-- [TITLE argument provided?]
                YES --> title = TITLE
                NO  --> title = datetime.now().strftime("%Y-%m-%d-%H%M")
                |
                v
        print(f"Recording '{title}' → {config.recordings_dir}/<title>.wav")
        [stub — Phase 2 starts actual recording here]
```

### Recommended Project Structure
```
meetcap/                     # repo root
├── pyproject.toml           # build config, deps, entry point
├── uv.lock                  # lockfile (auto-generated)
├── src/
│   └── meetcap/
│       ├── __init__.py      # package marker (empty or version)
│       ├── cli.py           # click entry point — main() function
│       └── config.py        # config load/save + platformdirs path logic
└── .python-version          # pin Python version for uv
```

**Layout choice (Claude's discretion):** Use `src/` layout. Reason: prevents accidental imports from the repo root during development before install; `uv init --app --package` generates `src/` layout by default; standard for modern Python packages.

### Pattern 1: Click Group with invoke_without_command

The `meetcap` root command doubles as the record command — it does NOT have a mandatory subcommand. `invoke_without_command=True` enables this. A future `meetcap config` subcommand is added separately.

```python
# Source: https://click.palletsprojects.com/en/stable/commands-and-groups/
import click

@click.group(invoke_without_command=True)
@click.argument("title", required=False, default=None)
@click.pass_context
def main(ctx, title):
    """Record a meeting. Pass a title or let meetcap generate one."""
    if ctx.invoked_subcommand is not None:
        return  # a subcommand (e.g. 'config') was called — do nothing here

    config = load_config()
    if config is None:
        config = run_first_run_wizard()

    if title is None:
        from datetime import datetime
        title = datetime.now().strftime("%Y-%m-%d-%H%M")

    click.echo(f"Recording '{title}' → {config['recordings_dir']}")
    # Phase 2: start recording here
```

### Pattern 2: Config Read/Write with tomllib + tomli-w

```python
# Source: https://docs.python.org/3/library/tomllib.html
#         https://pypi.org/project/tomli-w/
import tomllib
import tomli_w
import platformdirs
from pathlib import Path

CONFIG_FILE = Path(platformdirs.user_config_dir("meetcap")) / "config.toml"

def load_config() -> dict | None:
    """Return config dict, or None if config file does not exist."""
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, "rb") as f:
        return tomllib.load(f)

def save_config(data: dict) -> None:
    """Write config dict to TOML file, creating parent dirs as needed."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(data, f)
```

### Pattern 3: First-Run Wizard

```python
# Source: https://click.palletsprojects.com/en/stable/prompts/
import click
from pathlib import Path

def run_first_run_wizard() -> dict:
    """Prompt for required settings, save, and return config dict."""
    click.echo("First run — let's set up meetcap.")
    recordings_dir = click.prompt(
        "Where should recordings be saved?",
        default=str(Path.home() / "recordings"),
    )
    # Expand ~ and resolve
    recordings_path = Path(recordings_dir).expanduser().resolve()
    recordings_path.mkdir(parents=True, exist_ok=True)

    config = {"recordings_dir": str(recordings_path)}
    save_config(config)
    click.echo(f"Config saved. Recordings will go to: {recordings_path}")
    return config
```

### Pattern 4: pyproject.toml Structure

```toml
# Generated by: uv init --app --package meetcap
[project]
name = "meetcap"
version = "0.1.0"
description = "Meeting recorder and summarizer"
requires-python = ">=3.11"
dependencies = [
    "click>=8.3.3",
    "platformdirs>=4.9.6",
    "tomli-w>=1.2.0",
]

[project.scripts]
meetcap = "meetcap.cli:main"

[build-system]
requires = ["uv_build>=0.9.13,<0.10.0"]
build-backend = "uv_build"
```

### Anti-Patterns to Avoid
- **Hardcoding config path:** Never use `~/.config/meetcap/config.toml` directly — always use `platformdirs`; macOS uses `~/Library/Application Support/meetcap/`.
- **Flat package layout:** Avoid placing `meetcap/` at repo root without `src/` — causes `import meetcap` to resolve to the local directory before install, hiding packaging bugs.
- **Using `toml` package (PyPI):** The `toml` package is unmaintained (last release 2020). Use `tomllib` (read) + `tomli-w` (write).
- **Writing TOML by hand (string templates):** TOML serialization has edge cases (strings with special chars, paths with backslashes on Windows). Use `tomli_w.dump()`.
- **Reading config in binary mode with tomllib but opening path in text mode:** `tomllib.load()` requires binary mode (`"rb"`). Opening in text mode raises `TypeError`.
- **Silent default for recordings_dir:** D-03 explicitly forbids this. Never fall back to a hardcoded default path if config is missing — always prompt.
- **Putting `main()` in `__init__.py`:** Keeps cli logic in `cli.py` for clarity and testability; `__init__.py` stays minimal (version string only).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| OS config path (macOS/Win/Linux) | `if sys.platform == "darwin"` branching | `platformdirs.user_config_dir()` | Platform detection is subtle; Linux has XDG, Windows has roaming vs local; platformdirs handles all of it |
| TOML writing | f-string templates | `tomli_w.dump()` | Paths on Windows contain backslashes; strings may contain quotes; hand-rolled TOML breaks |
| TOML reading | `re.match` or line parsing | `tomllib.load()` | TOML has multi-line strings, arrays, inline tables |
| CLI argument parsing | `sys.argv` parsing | `click` | Click handles `--help`, type coercion, missing args, and error formatting automatically |

**Key insight:** The config and CLI surface are small but the cross-platform correctness requirements (path separators, config dirs) justify using the standard library for TOML reading and well-maintained packages for path resolution and CLI.

## Common Pitfalls

### Pitfall 1: tomllib requires binary mode
**What goes wrong:** `with open(CONFIG_FILE, "r") as f: tomllib.load(f)` raises `TypeError: file must be opened in binary mode`.
**Why it happens:** `tomllib` (and `tomli`) are defined to read bytes, not str, to handle encoding correctly.
**How to avoid:** Always open with `"rb"`: `with open(CONFIG_FILE, "rb") as f:`.
**Warning signs:** `TypeError` at config load time, not at startup.

### Pitfall 2: tomli-w requires binary mode for dump()
**What goes wrong:** `with open(CONFIG_FILE, "w") as f: tomli_w.dump(data, f)` raises `TypeError`.
**Why it happens:** `tomli_w.dump()` writes bytes, same rationale as `tomllib`.
**How to avoid:** Always open with `"wb"`: `with open(CONFIG_FILE, "wb") as f:`.

### Pitfall 3: click argument vs option for title
**What goes wrong:** Using `@click.option("--title")` means users must type `meetcap --title "My meeting"` instead of `meetcap "My meeting"`.
**Why it happens:** Options require `--name`; arguments are positional.
**How to avoid:** Use `@click.argument("title", required=False, default=None)` so `meetcap "My meeting"` works naturally (D-09).

### Pitfall 4: invoke_without_command with a positional argument
**What goes wrong:** Combining `@click.group(invoke_without_command=True)` with `@click.argument("title", required=False)` can confuse click if `TITLE` matches a registered subcommand name.
**Why it happens:** Click tries to match positional tokens to subcommand names first.
**How to avoid:** Keep subcommand names (`config`) distinct from plausible meeting titles. This is not a real problem in practice because user titles won't be `"config"`, but document it for future subcommand naming.

### Pitfall 5: Path not expanded before saving
**What goes wrong:** User types `~/recordings`; config stores literal `~/recordings`; Phase 2 opens the path without expanding — file not found.
**Why it happens:** `~/recordings` is a shell shorthand, not a real OS path.
**How to avoid:** Always call `Path(user_input).expanduser().resolve()` before storing in config. Store the resolved absolute path.

### Pitfall 6: Config dir not created before writing
**What goes wrong:** `CONFIG_FILE.parent` (`~/Library/Application Support/meetcap/`) does not exist on first run; `open(CONFIG_FILE, "wb")` raises `FileNotFoundError`.
**How to avoid:** `CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)` before writing.

### Pitfall 7: uv_build version pinning too tightly
**What goes wrong:** `requires = ["uv_build>=0.9.13,<0.10.0"]` may block build when uv releases 0.10.0. The upper pin is generated by `uv init` and is safe for now but will need updating.
**How to avoid:** Understand this is a generated line; update the upper bound when uv releases a new minor version, or use `>=0.9.13` without upper bound if comfortable.

## Code Examples

### Minimal working cli.py (Phase 1 stub)
```python
# Source: patterns from https://click.palletsprojects.com/en/stable/commands-and-groups/
import click
from datetime import datetime
from meetcap.config import load_config, run_first_run_wizard

@click.group(invoke_without_command=True)
@click.argument("title", required=False, default=None)
@click.pass_context
def main(ctx: click.Context, title: str | None) -> None:
    """Record a meeting. Provide a TITLE or let meetcap generate one."""
    if ctx.invoked_subcommand is not None:
        return

    config = load_config()
    if config is None:
        config = run_first_run_wizard()

    if title is None:
        title = datetime.now().strftime("%Y-%m-%d-%H%M")

    recordings_dir = config["recordings_dir"]
    click.echo(f"Starting recording: {title!r}")
    click.echo(f"Output: {recordings_dir}/{title}.wav")
    # TODO Phase 2: start actual recording

@main.command("config")
def config_cmd() -> None:
    """Show or update meetcap configuration."""
    cfg = load_config()
    if cfg is None:
        click.echo("No config file found. Run meetcap to set up.")
        return
    for k, v in cfg.items():
        click.echo(f"{k} = {v!r}")
```

### Config path on each OS
```
macOS:   ~/Library/Application Support/meetcap/config.toml
Windows: C:\Users\<user>\AppData\Local\meetcap\meetcap\config.toml
Linux:   ~/.config/meetcap/config.toml  (or $XDG_CONFIG_HOME/meetcap/)
```
[VERIFIED: platformdirs.user_config_dir('meetcap') tested on macOS; Windows/Linux paths from platformdirs docs]

### pipx install workflow
```bash
# Install uv if not present
curl -LsSf https://astral.sh/uv/install.sh | sh

# Scaffold (one-time)
uv init --app --package meetcap

# Add dependencies
uv add click platformdirs "tomli-w>=1.2.0"

# Install via pipx for isolated CLI install
pipx install .

# Or install via uvx (modern alternative to pipx)
uv tool install .

# Verify
meetcap --help
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `appdirs` for config paths | `platformdirs` | 2021 | `appdirs` is unmaintained; `platformdirs` is the maintained fork |
| `toml` PyPI package | `tomllib` (stdlib) + `tomli-w` | Python 3.11 (2022) | No external dep for reading; `tomllib` is spec-compliant |
| `setuptools` + `setup.py` | `pyproject.toml` + `uv_build` or `hatchling` | PEP 517/518 (2017–2022) | `setup.py` is legacy |
| `argparse` for CLI | `click` | — | click is the ecosystem standard for user-facing CLIs |

**Deprecated/outdated:**
- `toml` (PyPI): last released 2020, no Python 3.11 support, do not use
- `appdirs`: unmaintained, replaced by `platformdirs`
- `setup.py` / `setup.cfg`: legacy; `pyproject.toml` is the standard

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `uv_build` wheels are installable by `pipx install .` on the user's machine | Standard Stack | pipx install would fail; fallback: switch to `hatchling` backend |
| A2 | `pipx` is (or will be) installed on user's machine at test time | Environment Availability | `meetcap --help` can't be verified; workaround: use `uv tool install .` instead |

## Open Questions

1. **Python version minimum**
   - What we know: `uv init --app --package` defaults to `requires-python = ">=3.11"` on this machine; `tomllib` is stdlib from 3.11.
   - What's unclear: Does the user need to support Python 3.10? (If yes, add `tomli` as a conditional dep.)
   - Recommendation: Lock to `>=3.11`; `tomllib` is stdlib, no extra dep needed. Document this in pyproject.toml.

2. **pipx vs uv tool install**
   - What we know: `pipx` is not currently installed on this machine. `uv tool install .` is the equivalent modern command.
   - What's unclear: Which install method the user prefers for end-user distribution.
   - Recommendation: Document both in the plan. The phase success criterion says `pipx install .` — ensure both work. Since `uv_build` produces a PEP 517 wheel, both will work.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| uv | Build, package management | Yes | 0.9.13 | — |
| Python 3.11+ | tomllib stdlib, type hints | Yes | 3.11.5 | — |
| pipx | Phase success criterion test | No | — | `uv tool install .` produces equivalent isolated install |
| click | CLI framework | Not installed system-wide (installed per-project via uv) | 8.3.3 latest | — |
| platformdirs | Config paths | Not installed system-wide | 4.9.6 latest | — |
| tomli-w | TOML write | Not installed system-wide | 1.2.0 latest | — |

**Missing dependencies with no fallback:**
- None — uv manages all Python deps in an isolated venv.

**Missing dependencies with fallback:**
- `pipx`: Not on PATH. Use `uv tool install .` for equivalent isolated CLI install when verifying the success criterion.

## Sources

### Primary (HIGH confidence)
- pip index (PyPI registry) — click 8.3.3, platformdirs 4.9.6, tomli-w 1.2.0 versions verified live
- Python 3.11 stdlib — `tomllib` confirmed available (`python3 -c "import tomllib"`)
- `uv --version` — uv 0.9.13 confirmed installed
- `uv init --app --package` live run — confirmed pyproject.toml structure and `src/` layout
- platformdirs live test — `user_config_dir('meetcap')` returns `~/Library/Application Support/meetcap` on macOS
- Context7 `/pallets/click` — `invoke_without_command`, `click.prompt`, group patterns

### Secondary (MEDIUM confidence)
- [PyPI: tomli-w](https://pypi.org/project/tomli-w/) — dump() API confirmed binary mode
- [Python docs: tomllib](https://docs.python.org/3/library/tomllib.html) — load() binary mode requirement
- [Click docs: commands-and-groups](https://click.palletsprojects.com/en/stable/commands-and-groups/) — invoke_without_command pattern
- [astral.sh: uv_build](https://pypi.org/project/uv-build/) — confirmed PEP 517 compatible wheels (web search)

### Tertiary (LOW confidence)
- None — all critical claims verified via live tool calls or official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all versions confirmed live against pip index
- Architecture: HIGH — patterns from click official docs + live platformdirs test
- Pitfalls: HIGH — binary mode requirements verified live; path expansion is standard Python

**Research date:** 2026-05-09
**Valid until:** 2026-08-09 (90 days — stable libraries with slow release cadence)
