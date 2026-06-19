"""Result display module - pure presentation layer."""
from typing import List, Dict
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .ssh_client import CommandResult

console = Console()


class BatchResultView:
    """View model for a batch command result.

    Computes presentation-side statistics from raw execution results.
    """

    def __init__(self, command: str, results: List[CommandResult]):
        self.command = command
        self.results = results

    @property
    def successful_sessions(self) -> List[str]:
        return [r.session_name for r in self.results if r.success]

    @property
    def failed_sessions(self) -> List[str]:
        return [r.session_name for r in self.results if not r.success]

    @property
    def all_success(self) -> bool:
        return len(self.results) > 0 and all(r.success for r in self.results)

    def stdout_aggregate(self) -> Dict[str, List[str]]:
        """Aggregate stdout by content."""
        content_map: Dict[str, List[str]] = defaultdict(list)
        for result in self.results:
            if result.success:
                content_map[result.stdout.strip()].append(result.session_name)
        return dict(content_map)

    def get_result(self, session_name: str) -> CommandResult:
        for r in self.results:
            if r.session_name == session_name:
                return r
        return None


class ResultDisplay:
    """Display command execution results in various formats."""

    @staticmethod
    def show_detailed(view: BatchResultView, show_stdout: bool = True, show_stderr: bool = True) -> None:
        """Show detailed results for each session."""
        console.print(f"\n[bold cyan]Execution Summary: {view.command}[/bold cyan]")
        console.print(f"[green]Success: {len(view.successful_sessions)}[/green] | "
                      f"[red]Failed: {len(view.failed_sessions)}[/red] | "
                      f"[blue]Total: {len(view.results)}[/blue]\n")

        for result in view.results:
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
    def show_summary(view: BatchResultView) -> None:
        """Show aggregated results grouped by output."""
        console.print(f"\n[bold cyan]Aggregated Results: {view.command}[/bold cyan]")
        console.print(f"[green]Success: {len(view.successful_sessions)}[/green] | "
                      f"[red]Failed: {len(view.failed_sessions)}[/red] | "
                      f"[blue]Total: {len(view.results)}[/blue]\n")

        content_map = view.stdout_aggregate()

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

        if view.failed_sessions:
            console.print(f"\n[bold red]Failed sessions:[/bold red]")
            for session_name in view.failed_sessions:
                result = next(r for r in view.results if r.session_name == session_name)
                console.print(f"  [red]• {session_name}:[/red] {result.error or result.stderr or 'Unknown error'}")

    @staticmethod
    def show_table(view: BatchResultView) -> None:
        """Show results in table format."""
        table = Table(title=f"Execution: {view.command}", show_lines=True)
        table.add_column("Session", style="cyan", no_wrap=True)
        table.add_column("Status", style="green", no_wrap=True)
        table.add_column("Exit Code", style="yellow", no_wrap=True)
        table.add_column("Output", style="dim")

        for result in view.results:
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
