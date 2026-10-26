from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit


def data_directory() -> Path:
    override = os.getenv("NEXUS_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local" / "share")))
    return base / "NexusME"


def validate_local_url(url: str) -> str:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError as exc:
        raise ValueError("Endereço do Ollama inválido.") from exc
    # Numeric addresses avoid DNS resolution and accidental remote endpoints.
    if (parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "::1"}
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in {"", "/"} or not port or not 1 <= port <= 65535):
        raise ValueError("Use http://127.0.0.1:11434 ou outro endereço numérico de loopback com porta.")
    return url.rstrip("/")


@dataclass
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = ""
    openai_model: str = ""
    context_chars: int = 8000
    max_output_tokens: int = 1200

    def validate(self) -> None:
        self.ollama_url = validate_local_url(self.ollama_url.strip())
        self.ollama_model = self.ollama_model.strip()
        self.openai_model = self.openai_model.strip()
        if any(len(x) > 160 or "\n" in x for x in (self.ollama_model, self.openai_model)):
            raise ValueError("Nome de modelo inválido.")
        if not 1000 <= self.context_chars <= 12000:
            raise ValueError("O contexto deve ficar entre 1.000 e 12.000 caracteres.")
        if not 256 <= self.max_output_tokens <= 4096:
            raise ValueError("Limite de saída inválido.")

    @classmethod
    def load(cls, directory: Path) -> "Settings":
        path = directory / "settings.json"
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        settings = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        settings.validate()
        return settings

    def save(self, directory: Path) -> None:
        self.validate()
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / "settings.tmp"
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, directory / "settings.json")
