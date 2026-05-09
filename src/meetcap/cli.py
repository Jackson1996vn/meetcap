import click
from datetime import datetime


@click.group(invoke_without_command=True)
@click.argument("title", required=False, default=None)
@click.pass_context
def main(ctx: click.Context, title: str | None) -> None:
    """Record a meeting. Provide a TITLE or let meetcap generate one."""
    if ctx.invoked_subcommand is not None:
        return

    # Config loading will be added in Plan 02
    # For now, stub the recording message

    if title is None:
        title = datetime.now().strftime("%Y-%m-%d-%H%M")

    click.echo(f"Starting recording: {title!r}")
    click.echo("Recording... (not yet implemented — stub for Phase 2)")
