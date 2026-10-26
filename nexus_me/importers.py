from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .security import clean_text
from .store import source_date

MAX_FILE_BYTES = 10 * 1024 * 1024


def prepare_import(path: Path) -> list[dict]:
    """Leitura explícita. Nunca executa conteúdo, expande ZIP ou percorre pastas."""
    path = Path(path)
    if path.suffix.lower() not in {".md", ".txt", ".json"} or not path.is_file():
        raise ValueError("Selecione um arquivo .md, .txt ou um export JSON da Condution.")
    with path.open("rb") as file:
        raw = file.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError("Limite de 10 MB por arquivo.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("O arquivo precisa estar codificado em UTF-8.") from exc
    fingerprint = hashlib.sha256(raw).hexdigest()
    source = f"Arquivo: {path.name} | SHA-256 {fingerprint}"
    if path.suffix.lower() in {".txt", ".md"}:
        clean_text(text, "Documento", 40000)
        stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")
        return [{"title": path.stem[:180], "content": text, "kind": "documento", "source": source, "source_at": stamp}]
    try:
        document = json.loads(text)
    except (ValueError, RecursionError) as exc:
        raise ValueError("JSON inválido.") from exc
    if not isinstance(document, dict) or not isinstance(document.get("sessoes_estudo"), list):
        raise ValueError("Formato não reconhecido. Este importador espera o campo sessoes_estudo da Condution Time.")
    sessions = document["sessoes_estudo"]
    if not 1 <= len(sessions) <= 500:
        raise ValueError("O export deve conter entre 1 e 500 sessões de estudo.")
    result = []
    fields = [("materia", "Matéria"), ("assunto", "Assunto"), ("subassunto", "Subassunto"),
              ("duracao_minutos", "Duração (minutos)"), ("questoes_resolvidas", "Questões resolvidas"),
              ("acertos", "Acertos"), ("erros", "Erros"), ("o_que_aprendeu", "Aprendizado"),
              ("dificuldade_encontrada", "Dificuldade"), ("observacoes", "Observações")]
    for index, session in enumerate(sessions, 1):
        if not isinstance(session, dict) or not session.get("data"):
            raise ValueError(f"Sessão {index}: faltam dados ou data.")
        date = source_date(session["data"])
        lines = [f"Data do estudo: {date}"]
        for key, label in fields:
            value = session.get(key)
            if value is not None and value != "":
                if not isinstance(value, (str, int, float)) or isinstance(value, bool):
                    raise ValueError(f"Sessão {index}: campo {key} inválido.")
                lines.append(f"{label}: {value}")
        lines.append("Dados importados de um registro; não representam verificação independente. Ausência de registro não significa ausência de atividade.")
        content = clean_text("\n".join(lines), "Sessão", 40000)
        origin = str(session.get("id_origem", index))[:80]
        # Stable identity across exports; changed contents become a historical version.
        result.append({"title": f"Estudo · {session.get('materia', 'Sem matéria')} · {date}"[:180],
                       "content": content, "kind": "estudo", "source_at": date,
                       "source": f"Condution Time | sessão {origin}", "cloud_allowed": False})
    return result
