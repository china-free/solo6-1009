"""Command Line Interface for Terminal Session Manager."""
import click
from typing import List

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .storage import Storage, SSHSession, SessionGroup, CommandTemplate, get_config_dir
from .executor import BatchExecutor, ResultDisplay

console = Console()
storage = Storage()
executor = BatchExecutor(storage)


@click.group()
@click.version_option(version="0.1.0", prog_name="tsm")
def cli():
    """Terminal Session Manager - Manage multiple SSH sessions efficiently."""
    pass


@cli.group()
def session():
    """Manage SSH sessions."""
    pass


@session.command("add")
@click.argument("name")
@click.argument("host")
@click.option("--port", "-p", type=int, default=22, help="SSH port")
@click.option("--user", "-u", help="SSH username")
@click.option("--password", "-w", help="SSH password")
@click.option("--key-file", "-k", help="SSH private key file path")
@click.option("--description", "-d", help="Session description")
def session_add(name, host, port, user, password, key_file, description):
    """Add a new SSH session."""
    session = SSHSession(
        name=name,
        host=host,
        port=port,
        username=user or "",
        password=password or "",
        key_file=key_file or "",
        description=description or ""
    )
    storage.add_session(session)
    console.print(f"[green]✓ Session '{name}' added successfully[/green]")


@session.command("remove")
@click.argument("name")
def session_remove(name):
    """Remove an SSH session."""
    if storage.get_session(name) is None:
        console.print(f"[red]Session '{name}' not found[/red]")
        return
    storage.remove_session(name)
    console.print(f"[green]✓ Session '{name}' removed successfully[/green]")


@session.command("list")
def session_list():
    """List all SSH sessions."""
    sessions = storage.list_sessions()
    if not sessions:
        console.print("[yellow]No sessions found[/yellow]")
        return

    table = Table(title="SSH Sessions", show_lines=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Host", style="green", no_wrap=True)
    table.add_column("Port", style="yellow", no_wrap=True)
    table.add_column("User", style="blue")
    table.add_column("Key File", style="magenta")
    table.add_column("Description", style="dim")

    for s in sessions:
        table.add_row(
            s.name,
            s.host,
            str(s.port),
            s.username or "-",
            s.key_file or "-",
            s.description or "-"
        )

    console.print(table)


@cli.group()
def group():
    """Manage session groups."""
    pass


@group.command("create")
@click.argument("name")
@click.option("--description", "-d", help="Group description")
def group_create(name, description):
    """Create a new session group."""
    if storage.get_group(name) is not None:
        console.print(f"[yellow]Group '{name}' already exists[/yellow]")
        return
    group = SessionGroup(name=name, description=description or "")
    storage.add_group(group)
    console.print(f"[green]✓ Group '{name}' created successfully[/green]")


@group.command("remove")
@click.argument("name")
def group_remove(name):
    """Remove a session group."""
    if storage.get_group(name) is None:
        console.print(f"[red]Group '{name}' not found[/red]")
        return
    storage.remove_group(name)
    console.print(f"[green]✓ Group '{name}' removed successfully[/green]")


@group.command("rename")
@click.argument("old_name")
@click.argument("new_name")
def group_rename(old_name, new_name):
    """Rename a session group."""
    if storage.get_group(old_name) is None:
        console.print(f"[red]Group '{old_name}' not found[/red]")
        return
    if storage.get_group(new_name) is not None:
        console.print(f"[yellow]Group '{new_name}' already exists[/yellow]")
        return
    storage.rename_group(old_name, new_name)
    console.print(f"[green]✓ Group renamed from '{old_name}' to '{new_name}'[/green]")


@group.command("list")
def group_list():
    """List all session groups."""
    groups = storage.list_groups()
    if not groups:
        console.print("[yellow]No groups found[/yellow]")
        return

    for g in groups:
        sessions_str = ", ".join(g.sessions) if g.sessions else "(empty)"
        desc_str = f" - {g.description}" if g.description else ""
        title = f"[cyan]{g.name}[/cyan] ({len(g.sessions)} sessions){desc_str}"
        console.print(Panel(
            sessions_str,
            title=title,
            title_align="left",
            border_style="blue"
        ))


@group.command("add-session")
@click.argument("group_name")
@click.argument("session_name")
def group_add_session(group_name, session_name):
    """Add a session to a group."""
    success = storage.add_session_to_group(group_name, session_name)
    if success:
        console.print(f"[green]✓ Session '{session_name}' added to group '{group_name}'[/green]")
    else:
        console.print(f"[red]Failed to add session. Check if group and session exist.[/red]")


@group.command("remove-session")
@click.argument("group_name")
@click.argument("session_name")
def group_remove_session(group_name, session_name):
    """Remove a session from a group."""
    success = storage.remove_session_from_group(group_name, session_name)
    if success:
        console.print(f"[green]✓ Session '{session_name}' removed from group '{group_name}'[/green]")
    else:
        console.print(f"[red]Failed to remove session. Check if group exists.[/red]")


@cli.group()
def template():
    """Manage command templates."""
    pass


@template.command("create")
@click.argument("name")
@click.option("--description", "-d", help="Template description")
@click.option("--command", "-c", multiple=True, help="Add a command to the template")
def template_create(name, description, command):
    """Create a new command template."""
    if storage.get_template(name) is not None:
        console.print(f"[yellow]Template '{name}' already exists[/yellow]")
        return
    template = CommandTemplate(
        name=name,
        description=description or "",
        commands=list(command)
    )
    storage.add_template(template)
    console.print(f"[green]✓ Template '{name}' created successfully[/green]")


@template.command("add-command")
@click.argument("template_name")
@click.argument("command")
def template_add_command(template_name, command):
    """Add a command to a template."""
    tpl = storage.get_template(template_name)
    if tpl is None:
        console.print(f"[red]Template '{template_name}' not found[/red]")
        return
    tpl.commands.append(command)
    storage.add_template(tpl)
    console.print(f"[green]✓ Command added to template '{template_name}'[/green]")


@template.command("remove")
@click.argument("name")
def template_remove(name):
    """Remove a command template."""
    if storage.get_template(name) is None:
        console.print(f"[red]Template '{name}' not found[/red]")
        return
    storage.remove_template(name)
    console.print(f"[green]✓ Template '{name}' removed successfully[/green]")


@template.command("list")
def template_list():
    """List all command templates."""
    templates = storage.list_templates()
    if not templates:
        console.print("[yellow]No templates found[/yellow]")
        return

    table = Table(title="Command Templates", show_lines=True)
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Description", style="dim")
    table.add_column("Commands", style="green")

    for t in templates:
        commands_str = "\n".join([f"  {i+1}. {cmd}" for i, cmd in enumerate(t.commands)])
        table.add_row(t.name, t.description or "-", commands_str or "(no commands)")

    console.print(table)


@cli.command()
@click.argument("group_name")
@click.argument("command")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["detailed", "summary", "table"]),
              default="detailed",
              help="Output format")
@click.option("--no-stderr", is_flag=True, help="Hide stderr output")
@click.option("--no-stdout", is_flag=True, help="Hide stdout output")
def exec(group_name, command, output_format, no_stderr, no_stdout):
    """Execute a command on all sessions in a group."""
    result = executor.execute_on_group(group_name, command)
    if result is None:
        return

    if output_format == "detailed":
        ResultDisplay.show_detailed(result, show_stdout=not no_stdout, show_stderr=not no_stderr)
    elif output_format == "summary":
        ResultDisplay.show_summary(result)
    elif output_format == "table":
        ResultDisplay.show_table(result)

    if not result.all_success:
        click.get_current_context().exit(1)


@cli.command()
@click.argument("group_name")
@click.argument("template_name")
@click.option("--format", "-f", "output_format",
              type=click.Choice(["detailed", "summary", "table"]),
              default="detailed",
              help="Output format")
def exec_template(group_name, template_name, output_format):
    """Execute a command template on all sessions in a group."""
    results = executor.execute_template_on_group(group_name, template_name)
    if results is None:
        return

    has_failure = False
    for i, result in enumerate(results):
        console.print(f"\n[bold magenta]Step {i+1}/{len(results)}[/bold magenta]")
        if output_format == "detailed":
            ResultDisplay.show_detailed(result)
        elif output_format == "summary":
            ResultDisplay.show_summary(result)
        elif output_format == "table":
            ResultDisplay.show_table(result)
        if not result.all_success:
            has_failure = True

    if has_failure:
        click.get_current_context().exit(1)


@cli.command()
def info():
    """Show configuration info."""
    config_dir = get_config_dir()
    data_file = storage.data_file

    sessions = storage.list_sessions()
    groups = storage.list_groups()
    templates = storage.list_templates()

    table = Table(title="TSM Configuration", show_lines=False)
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="green")

    table.add_row("Config Directory", str(config_dir))
    table.add_row("Data File", str(data_file))
    table.add_row("Total Sessions", str(len(sessions)))
    table.add_row("Total Groups", str(len(groups)))
    table.add_row("Total Templates", str(len(templates)))

    console.print(table)


if __name__ == "__main__":
    cli()
