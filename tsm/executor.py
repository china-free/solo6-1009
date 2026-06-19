"""Batch command executor - execution layer only.

Pure execution logic. Returns raw result data without any presentation concerns.
"""
import concurrent.futures
from typing import List, Optional
from dataclasses import dataclass, field

from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.console import Console

from .storage import Storage, SSHSession, SessionGroup, CommandTemplate
from .ssh_client import SSHClient, CommandResult

console = Console()


@dataclass
class BatchResult:
    """Raw result of a batch command execution.

    Only contains execution data. Presentation-side statistics
    (e.g. successful/failed session lists) are computed by the display layer.
    """
    command: str
    results: List[CommandResult] = field(default_factory=list)


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
                    except Exception as e:
                        result = CommandResult(
                            session_name=session.name,
                            command=command,
                            success=False,
                            error=str(e)
                        )
                        batch_result.results.append(result)
                    progress.advance(task)

        return batch_result

    def execute_template_on_group(self, group_name: str, template_name: str) -> Optional[List[BatchResult]]:
        """Execute a command template on a group.

        Per-session failure tracking: if a session fails at command N,
        it is skipped for commands N+1..end, but other healthy sessions
        continue executing the full template.
        """
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
        failed_sessions: set = set()

        for cmd in template.commands:
            active_sessions = [s for s in sessions if s.name not in failed_sessions]
            batch_result = BatchResult(command=cmd)

            for name in sorted(failed_sessions):
                batch_result.results.append(CommandResult(
                    session_name=name,
                    command=cmd,
                    success=False,
                    error="Skipped due to previous failure in this session",
                ))

            if active_sessions:
                active_batch = self.execute(active_sessions, cmd)
                batch_result.results.extend(active_batch.results)
                for r in active_batch.results:
                    if not r.success:
                        failed_sessions.add(r.session_name)

            results.append(batch_result)

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
