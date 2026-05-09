import click
from datetime import datetime

from meetcap.config import load_config, run_first_run_wizard


@click.group(invoke_without_command=True)
@click.argument("title", required=False, default=None)
@click.pass_context
def main(ctx: click.Context, title: str | None) -> None:
    """Record a meeting. Provide a TITLE or let meetcap generate one."""
    # When a subcommand name (e.g. 'config') is passed as the first positional token,
    # click parses it as the TITLE argument before subcommand routing can occur.
    # Explicitly forward to the subcommand if title matches a registered command name.
    if title is not None and title in main.commands:
        sub_cmd = main.commands[title]
        ctx.invoke(sub_cmd)
        return

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
    click.echo("Recording... (not yet implemented — stub for Phase 2)")


@main.command("config")
def config_cmd() -> None:
    """Show current meetcap configuration."""
    cfg = load_config()
    if cfg is None:
        click.echo("No config file found. Run meetcap to set up.")
        return
    for k, v in cfg.items():
        click.echo(f"{k} = {v!r}")
