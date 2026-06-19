"""Batch command executor and result display module."""
import concurrent.futures
from typing import List, Dict, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn

from .storage import Storage, SSHSession, SessionGroup, CommandTemplate
from .ssh_client import SSHClient, CommandResult

console = Console()


@dataclass
class BatchResult:
    """Result of batch command execution."""
    command: str
    results: List[CommandResult] = field(default_factory=list)
    failed_sessions: List[str] = field(default_factory=list)
    successful_sessions: List[str] = field(default_factory=list)

    @property
    def all_success(self) -> bool:
        return len(self.failed_sessions) == 0 and len(self.results) > 0

    def get_stdout_aggregate(self) -> Dict[str, List[str]]:
        """Aggregate stdout by content."""
        content_map: Dict[str, List[str]] = defaultdict(list)
        for result in self.results:
            if result.success:
                content_map[result.stdout.strip()].append(result.session_name)
        return dict(content_map)


class BatchExecutor:
    """Execute commands on multiple SSH sessions concurrently."""

    def __init__(self, storage: Storage, max_workers: int = 10):
        self.storage = storage
        self.max_workers = max_workers

    def execute_on_group(self, group_name: str, command: str) -> Optional[BatchResult]:
        """Execute a command on all sessions in a group."""
        group = self.storage.get_group(group_name)
        if not group:
            console.print(f"[red]Group '{group_name}' not found[/red]")
            return None

        sessions: List[SSHSession] = []
        for session_name in group.sessions:
            session = self.storage.get_session(session_name)
            if session:
                sessions.append(session)

        if not sessions:
            console.print(f"[yellow]No sessions in group '{group_name}'[/yellow]")
            return None

        return self.execute(sessions, command)

    def execute(self, sessions: List[SSHSession], command: str) -> BatchResult:
        """Execute command on multiple sessions concurrently."""
        batch_result = BatchResult(command=command)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=True
        ) as progress:
            task = progress.add_task(f"Executing: {command}", total=len(sessions))

            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_session = {
                    executor.submit(self._execute_single, session, command): session
                    for session in sessions
                }

                for future in concurrent.futures.as_completed(future_to_session):
                    session = future_to_session[future]
                    try:
                        result = future.result()
                        batch_result.results.append(result)
                        if result.success:
                            batch_result.successful_sessions.append(session.name)
                        else:
                            batch_result.failed_sessions.append(session.name)
                    except Exception as e:
                        result = CommandResult(
                            session_name=session.name,
                            command=command,
                            success=False,
                            error=str(e)
                        )
                        batch_result.results.append(result)
                        batch_result.failed_sessions.append(session.name)
                    progress.advance(task)

        return batch_result

    def execute_template_on_group(self, group_name: str, template_name: str) -> Optional[List[BatchResult]]:
        """Execute a command template on a group."""
        template = self.storage.get_template(template_name)
        if not template:
            console.print(f"[red]Template '{template_name}' not found[/red]")
            return None

        group = self.storage.get_group(group_name)
        if not group:
            console.print(f"[red]Group '{group_name}' not found[/red]")
            return None

        sessions: List[SSHSession] = []
        for session_name in group.sessions:
            session = self.storage.get_session(session_name)
            if session:
                sessions.append(session)

        if not sessions:
            console.print(f"[yellow]No sessions in group '{group_name}'[/yellow]")
            return None

        results: List[BatchResult] = []
        for cmd in template.commands:
            batch_result = self.execute(sessions, cmd)
            results.append(batch_result)
            if not batch_result.all_success:
                console.print(f"[yellow]Template execution stopped at command: {cmd}[/yellow]")
                break

        return results

    def _execute_single(self, session: SSHSession, command: str) -> CommandResult:
        """Execute command on a single session."""
        with SSHClient(session) as client:
            if not client.connected:
                return CommandResult(
                    session_name=session.name,
                    command=command,
                    success=False,
                    error=getattr(client, 'error', 'Connection failed')
                )
            return client.execute(command)


class ResultDisplay:
    """Display command execution results in various formats."""

    @staticmethod
    def show_detailed(batch_result: BatchResult, show_stdout: bool = True, show_stderr: bool = True) -> None:
        """Show detailed results for each session."""
        console.print(f"\n[bold cyan]Execution Summary: {batch_result.command}[/bold cyan]")
        console.print(f"[green]Success: {len(batch_result.successful_sessions)}[/green] | "
                      f"[red]Failed: {len(batch_result.failed_sessions)}[/red] | "
                      f"[blue]Total: {len(batch_result.results)}[/blue]\n")

        for result in batch_result.results:
            status_icon = "[green]✓[/green]" if result.success else "[red]✗[/red]"
            status_color = "green" if result.success else "red"

            panel_content = []
            if show_stdout and result.stdout:
                stdout_text = Text(result.stdout.rstrip(), style="dim")
                panel_content.append(Text("stdout:", style="bold blue"))
                panel_content.append(stdout_text)

            if show_stderr and result.stderr:
                stderr_text = Text(result.stderr.rstrip(), style="yellow")
                if panel_content:
                    panel_content.append(Text(""))
                panel_content.append(Text("stderr:", style="bold yellow"))
                panel_content.append(stderr_text)

            if not result.success and result.error:
                if panel_content:
                    panel_content.append(Text(""))
                panel_content.append(Text(f"error: {result.error}", style="bold red"))

            content = Text("\n").join(panel_content) if panel_content else Text("(no output)", style="dim")

            title = f"{status_icon} [{status_color}]{result.session_name}[/{status_color}]"
            if result.exit_code != 0:
                title += f" (exit: {result.exit_code})"

            console.print(Panel(content, title=title, title_align="left"))

    @staticmethod
    def show_summary(batch_result: BatchResult) -> None:
        """Show aggregated results grouped by output."""
        console.print(f"\n[bold cyan]Aggregated Results: {batch_result.command}[/bold cyan]")
        console.print(f"[green]Success: {len(batch_result.successful_sessions)}[/green] | "
                      f"[red]Failed: {len(batch_result.failed_sessions)}[/red] | "
                      f"[blue]Total: {len(batch_result.results)}[/blue]\n")

        content_map = batch_result.get_stdout_aggregate()

        if content_map:
            for content, sessions in content_map.items():
                sessions_str = ", ".join(sessions)
                display_content = content if content else "(no output)"
                if len(display_content) > 500:
                    display_content = display_content[:500] + "..."
                console.print(Panel(
                    Text(display_content, style="dim"),
                    title=f"[blue]{len(sessions)}[/blue] hosts: {sessions_str}",
                    title_align="left"
                ))

        if batch_result.failed_sessions:
            console.print(f"\n[bold red]Failed sessions:[/bold red]")
            for session_name in batch_result.failed_sessions:
                result = next(r for r in batch_result.results if r.session_name == session_name)
                console.print(f"  [red]• {session_name}:[/red] {result.error or result.stderr or 'Unknown error'}")

    @staticmethod
    def show_table(batch_result: BatchResult) -> None:
        """Show results in table format."""
        table = Table(title=f"Execution: {batch_result.command}", show_lines=True)
        table.add_column("Session", style="cyan", no_wrap=True)
        table.add_column("Status", style="green", no_wrap=True)
        table.add_column("Exit Code", style="yellow", no_wrap=True)
        table.add_column("Output", style="dim")

        for result in batch_result.results:
            status = "✓" if result.success else "✗"
            status_style = "green" if result.success else "red"
            output = result.stdout.strip() or result.stderr.strip() or result.error or "(no output)"
            if len(output) > 80:
                output = output[:77] + "..."
            table.add_row(
                result.session_name,
                Text(status, style=status_style),
                str(result.exit_code),
                output
            )

        console.print("\n")
        console.print(table)
