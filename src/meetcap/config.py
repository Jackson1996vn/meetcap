import tomllib
from pathlib import Path

import platformdirs
import tomli_w
import click


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


def run_first_run_wizard() -> dict:
    """Prompt for required settings, save, and return config dict."""
    click.echo("First run — let's set up meetcap.")
    recordings_dir = click.prompt(
        "Where should recordings be saved?",
        default=str(Path.home() / "recordings"),
    )
    # Expand ~ and resolve to absolute path before storing (Pitfall 5)
    recordings_path = Path(recordings_dir).expanduser().resolve()
    recordings_path.mkdir(parents=True, exist_ok=True)

    config = {"recordings_dir": str(recordings_path)}
    save_config(config)
    click.echo(f"Config saved. Recordings will go to: {recordings_path}")
    return config
