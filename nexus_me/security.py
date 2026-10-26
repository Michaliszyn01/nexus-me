"""Defesas limitadas; classificação e revisão humana continuam necessárias."""
import re


SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{16,}"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"(?im)\b(?:api[_ -]?key|access[_ -]?token|password|senha|secret|service_role_key)\s*[:=]\s*[\"']?[^\s\"']{8,}"),
]


def reject_secrets(text: str) -> None:
    if any(pattern.search(text) for pattern in SECRET_PATTERNS):
        raise ValueError("Possível credencial detectada. Remova o segredo antes de salvar ou enviar.")


def clean_text(value: str, name: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name}: texto esperado.")
    value = value.strip().replace("\x00", "")
    if (required and not value) or len(value) > limit:
        raise ValueError(f"{name}: use {'1 a ' if required else 'até '}{limit} caracteres.")
    reject_secrets(value)
    return value
