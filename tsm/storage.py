"""JSON storage module for session groups and templates."""
import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional
from pathlib import Path


def get_config_dir() -> Path:
    """Get configuration directory path."""
    config_dir = Path.home() / ".tsm"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_data_file() -> Path:
    """Get data file path."""
    return get_config_dir() / "data.json"


@dataclass
class SSHSession:
    """SSH session configuration."""
    name: str
    host: str
    port: int = 22
    username: str = ""
    password: str = ""
    key_file: str = ""
    description: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SSHSession":
        return cls(**data)


@dataclass
class SessionGroup:
    """Group of SSH sessions."""
    name: str
    description: str = ""
    sessions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "SessionGroup":
        return cls(**data)


@dataclass
class CommandTemplate:
    """Command template for quick execution."""
    name: str
    description: str = ""
    commands: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "CommandTemplate":
        return cls(**data)


@dataclass
class AppData:
    """Complete application data."""
    sessions: Dict[str, SSHSession] = field(default_factory=dict)
    groups: Dict[str, SessionGroup] = field(default_factory=dict)
    templates: Dict[str, CommandTemplate] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "sessions": {k: v.to_dict() for k, v in self.sessions.items()},
            "groups": {k: v.to_dict() for k, v in self.groups.items()},
            "templates": {k: v.to_dict() for k, v in self.templates.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "AppData":
        return cls(
            sessions={k: SSHSession.from_dict(v) for k, v in data.get("sessions", {}).items()},
            groups={k: SessionGroup.from_dict(v) for k, v in data.get("groups", {}).items()},
            templates={k: CommandTemplate.from_dict(v) for k, v in data.get("templates", {}).items()},
        )


class Storage:
    """JSON file storage manager."""

    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or get_data_file()
        self._data: Optional[AppData] = None

    def load(self) -> AppData:
        """Load data from JSON file."""
        if self._data is not None:
            return self._data

        if not self.data_file.exists():
            self._data = AppData()
            return self._data

        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._data = AppData.from_dict(data)
        except (json.JSONDecodeError, IOError):
            self._data = AppData()

        return self._data

    def save(self, data: Optional[AppData] = None) -> None:
        """Save data to JSON file."""
        if data is not None:
            self._data = data
        if self._data is None:
            self._data = AppData()

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self._data.to_dict(), f, indent=2, ensure_ascii=False)

    def add_session(self, session: SSHSession) -> None:
        """Add or update a session."""
        data = self.load()
        data.sessions[session.name] = session
        self.save()

    def remove_session(self, name: str) -> None:
        """Remove a session."""
        data = self.load()
        if name in data.sessions:
            del data.sessions[name]
            for group in data.groups.values():
                if name in group.sessions:
                    group.sessions.remove(name)
            self.save()

    def get_session(self, name: str) -> Optional[SSHSession]:
        """Get a session by name."""
        data = self.load()
        return data.sessions.get(name)

    def list_sessions(self) -> List[SSHSession]:
        """List all sessions."""
        data = self.load()
        return list(data.sessions.values())

    def add_group(self, group: SessionGroup) -> None:
        """Add or update a group."""
        data = self.load()
        data.groups[group.name] = group
        self.save()

    def remove_group(self, name: str) -> None:
        """Remove a group."""
        data = self.load()
        if name in data.groups:
            del data.groups[name]
            self.save()

    def rename_group(self, old_name: str, new_name: str) -> None:
        """Rename a group."""
        data = self.load()
        if old_name in data.groups and new_name not in data.groups:
            group = data.groups[old_name]
            group.name = new_name
            data.groups[new_name] = group
            del data.groups[old_name]
            self.save()

    def get_group(self, name: str) -> Optional[SessionGroup]:
        """Get a group by name."""
        data = self.load()
        return data.groups.get(name)

    def list_groups(self) -> List[SessionGroup]:
        """List all groups."""
        data = self.load()
        return list(data.groups.values())

    def add_session_to_group(self, group_name: str, session_name: str) -> bool:
        """Add a session to a group."""
        data = self.load()
        if group_name not in data.groups or session_name not in data.sessions:
            return False
        if session_name not in data.groups[group_name].sessions:
            data.groups[group_name].sessions.append(session_name)
            self.save()
        return True

    def remove_session_from_group(self, group_name: str, session_name: str) -> bool:
        """Remove a session from a group."""
        data = self.load()
        if group_name not in data.groups:
            return False
        if session_name in data.groups[group_name].sessions:
            data.groups[group_name].sessions.remove(session_name)
            self.save()
            return True
        return False

    def add_template(self, template: CommandTemplate) -> None:
        """Add or update a template."""
        data = self.load()
        data.templates[template.name] = template
        self.save()

    def remove_template(self, name: str) -> None:
        """Remove a template."""
        data = self.load()
        if name in data.templates:
            del data.templates[name]
            self.save()

    def get_template(self, name: str) -> Optional[CommandTemplate]:
        """Get a template by name."""
        data = self.load()
        return data.templates.get(name)

    def list_templates(self) -> List[CommandTemplate]:
        """List all templates."""
        data = self.load()
        return list(data.templates.values())
