"""SSH client module for connecting and executing commands."""
import paramiko
from typing import Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path

from .storage import SSHSession


@dataclass
class CommandResult:
    """Result of a command execution."""
    session_name: str
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    success: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "session_name": self.session_name,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "success": self.success,
            "error": self.error,
        }


class SSHClient:
    """SSH client wrapper for paramiko."""

    def __init__(self, session: SSHSession, timeout: int = 10):
        self.session = session
        self.timeout = timeout
        self.client: Optional[paramiko.SSHClient] = None
        self.connected = False

    def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            connect_kwargs = {
                "hostname": self.session.host,
                "port": self.session.port,
                "username": self.session.username,
                "timeout": self.timeout,
                "allow_agent": True,
                "look_for_keys": True,
            }

            if self.session.password:
                connect_kwargs["password"] = self.session.password

            if self.session.key_file:
                key_path = Path(self.session.key_file).expanduser()
                if key_path.exists():
                    connect_kwargs["key_filename"] = str(key_path)

            self.client.connect(**connect_kwargs)
            self.connected = True
            return True
        except Exception as e:
            self.error = str(e)
            self.connected = False
            return False

    def execute(self, command: str) -> CommandResult:
        """Execute a command on the remote server."""
        if not self.connected or not self.client:
            return CommandResult(
                session_name=self.session.name,
                command=command,
                success=False,
                error="Not connected"
            )

        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=30)
            stdout_str = stdout.read().decode("utf-8", errors="replace")
            stderr_str = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()

            return CommandResult(
                session_name=self.session.name,
                command=command,
                stdout=stdout_str,
                stderr=stderr_str,
                exit_code=exit_code,
                success=exit_code == 0,
                error="" if exit_code == 0 else f"Exit code: {exit_code}"
            )
        except Exception as e:
            return CommandResult(
                session_name=self.session.name,
                command=command,
                success=False,
                error=str(e)
            )

    def execute_many(self, commands: List[str]) -> List[CommandResult]:
        """Execute multiple commands sequentially."""
        results = []
        for cmd in commands:
            result = self.execute(cmd)
            results.append(result)
            if not result.success:
                break
        return results

    def close(self) -> None:
        """Close the SSH connection."""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        self.connected = False

    def __enter__(self) -> "SSHClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
