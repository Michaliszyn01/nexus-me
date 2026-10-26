from __future__ import annotations

import hashlib
import json
import sqlite3
import unicodedata
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .security import clean_text


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize(value: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", value.casefold()) if not unicodedata.combining(c))


def source_date(value: str | None) -> str:
    if not value:
        return now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise ValueError("Data da fonte inválida. Use YYYY-MM-DD ou ISO 8601.") from exc
    if len(value) == 10:
        return parsed.date().isoformat()
    if parsed.tzinfo is None:
        raise ValueError("Horário da fonte precisa incluir fuso; ou informe apenas a data.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds")


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, goal TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'Em andamento', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS memories (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL, content TEXT NOT NULL, kind TEXT NOT NULL,
 source TEXT NOT NULL, source_at TEXT NOT NULL, created_at TEXT NOT NULL,
 digest TEXT NOT NULL, cloud_allowed INTEGER NOT NULL DEFAULT 0,
 UNIQUE(project_id, digest)
);
CREATE INDEX IF NOT EXISTS memories_project ON memories(project_id, source_at DESC);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
 id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL REFERENCES projects(id),
 session_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL,
 provider TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS messages_session ON messages(project_id, session_id, id);
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
 entity_id TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("Banco criado por uma versão mais recente do Nexus ME.")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _audit(db, action: str, entity_id: str, details: dict | None = None):
        db.execute("INSERT INTO audit(action,entity_id,details,created_at) VALUES (?,?,?,?)",
                   (action, entity_id, json.dumps(details or {}), now()))

    def audit(self, action: str, entity_id: str, details: dict | None = None):
        with self.connection() as db:
            self._audit(db, action, entity_id, details)

    def projects(self):
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY created_at,name")]

    def project(self, project_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
        if not row:
            raise ValueError("Projeto não encontrado.")
        return dict(row)

    def add_project(self, name: str, goal: str) -> str:
        name = clean_text(name, "Nome", 100)
        goal = clean_text(goal, "Objetivo", 1200, required=False)
        ident = str(uuid.uuid4())
        with self.connection() as db:
            try:
                db.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (ident, name, goal, "Em andamento", now()))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Já existe um projeto com esse nome.") from exc
            self._audit(db, "project_created", ident)
        return ident

    def add_memory(self, project_id: str, title: str, content: str, kind: str = "nota",
                   source: str = "Registro manual", source_at: str | None = None,
                   cloud_allowed: bool = False) -> tuple[str, bool]:
        rows = self.add_memories(project_id, [{"title": title, "content": content, "kind": kind,
            "source": source, "source_at": source_at, "cloud_allowed": cloud_allowed}])
        return rows[0]

    def add_memories(self, project_id: str, entries: list[dict]) -> list[tuple[str, bool]]:
        self.project(project_id)
        if not 1 <= len(entries) <= 500:
            raise ValueError("Importe de 1 a 500 registros por vez.")
        prepared = []
        for e in entries:
            title = clean_text(e["title"], "Título", 180)
            content = clean_text(e["content"], "Conteúdo", 40000)
            kind = e.get("kind", "nota")
            if kind not in {"nota", "decisao", "estudo", "documento", "resumo"}:
                raise ValueError("Categoria inválida.")
            source = clean_text(e.get("source", "Registro manual"), "Fonte", 500)
            date = source_date(e.get("source_at"))
            # Import timestamps do not change identity. Source dates preserve historical versions.
            identity = [title, content, kind, source, e.get("source_at") or "manual"]
            digest = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
            prepared.append((str(uuid.uuid4()), project_id, title, content, kind, source,
                             date, now(), digest, int(bool(e.get("cloud_allowed", False)))))
        results = []
        with self.connection() as db:
            for row in prepared:
                duplicate = db.execute("SELECT id FROM memories WHERE project_id=? AND digest=?",
                                       (project_id, row[8])).fetchone()
                if duplicate:
                    results.append((duplicate[0], False))
                    continue
                db.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?,?,?,?)", row)
                self._audit(db, "memory_created", row[0], {"kind": row[4]})
                results.append((row[0], True))
        return results

    def memories(self, project_id: str, query: str = "", cloud_only: bool = False,
                 include_summaries: bool = True) -> list[dict]:
        self.project(project_id)
        sql = "SELECT * FROM memories WHERE project_id=?"
        if cloud_only:
            sql += " AND cloud_allowed=1"
        if not include_summaries:
            sql += " AND kind!='resumo'"
        sql += " ORDER BY source_at DESC,created_at DESC,id"
        with self.connection() as db:
            rows = [dict(r) for r in db.execute(sql, (project_id,))]
        terms = normalize(query).split()
        if terms:
            rows = [r for r in rows if all(t in normalize(r["title"]+" "+r["content"]) for t in terms)]
        return rows

    def memory(self, memory_id: str) -> dict:
        with self.connection() as db:
            row = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        if row is None:
            raise ValueError("Memória não encontrada.")
        return dict(row)

    def set_cloud_allowed(self, memory_id: str, allowed: bool):
        with self.connection() as db:
            cursor = db.execute("UPDATE memories SET cloud_allowed=? WHERE id=?", (int(allowed), memory_id))
            if cursor.rowcount != 1:
                raise ValueError("Memória não encontrada.")
            self._audit(db, "cloud_permission_changed", memory_id, {"allowed": allowed})

    def delete_memory(self, memory_id: str):
        with self.connection() as db:
            db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            self._audit(db, "memory_deleted", memory_id)

    def tasks(self, project_id: str):
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM tasks WHERE project_id=? ORDER BY done,created_at", (project_id,))]

    def add_task(self, project_id: str, title: str):
        self.project(project_id)
        title = clean_text(title, "Tarefa", 500)
        ident, stamp = str(uuid.uuid4()), now()
        with self.connection() as db:
            db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?)", (ident, project_id, title, 0, stamp, stamp))
            self._audit(db, "task_created", ident)
        return ident

    def set_task_done(self, task_id: str, done: bool):
        with self.connection() as db:
            if db.execute("UPDATE tasks SET done=?,updated_at=? WHERE id=?", (int(done), now(), task_id)).rowcount != 1:
                raise ValueError("Tarefa não encontrada.")
            self._audit(db, "task_status_changed", task_id, {"done": done})

    def add_message(self, project_id, session_id, role, content, provider):
        if role not in {"user", "assistant"}:
            raise ValueError("Papel de conversa inválido.")
        content = clean_text(content, "Mensagem", 40000)
        with self.connection() as db:
            db.execute("INSERT INTO messages(project_id,session_id,role,content,provider,created_at) VALUES (?,?,?,?,?,?)",
                       (project_id, session_id, role, content, provider, now()))

    def messages(self, project_id, session_id=None, limit=60):
        with self.connection() as db:
            if session_id:
                rows = db.execute("SELECT * FROM messages WHERE project_id=? AND session_id=? ORDER BY id DESC LIMIT ?",
                                  (project_id, session_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM messages WHERE project_id=? ORDER BY id DESC LIMIT ?",
                                  (project_id, limit)).fetchall()
        return [dict(r) for r in reversed(rows)]

    def latest_session(self, project_id):
        rows = self.messages(project_id, limit=1)
        return rows[0]["session_id"] if rows else str(uuid.uuid4())

    def events(self, limit=80):
        with self.connection() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,))]

    def backup(self, destination: Path):
        destination = Path(destination).resolve()
        if destination == self.path:
            raise ValueError("Escolha um arquivo diferente do banco em uso.")
        with self.connection() as source:
            dest = sqlite3.connect(destination)
            try:
                source.backup(dest)
            finally:
                dest.close()
        self.audit("backup_created", "local")

    def seed(self):
        if self.projects():
            return
        ident = self.add_project("Nexus ME", "Conectar conversa local, memória compartilhada e análises do GPT em um assistente pessoal.")
        self.add_memory(ident, "Divisão inicial do Nexus ME", (
            "Decisões informadas pelo usuário em 18/10/2026: aplicativo para Windows e ChatGPT com memória compartilhada. "
            "Modelo local para conversa e apresentação dos dados; GPT para análises sob demanda e futuros resumos. "
            "GitHub: código. Supabase: memória operacional. Windows: arquivos brutos. "
            "Notion: tarefas e planejamento. Obsidian: conhecimento. "
            "Gemma 4 E4B é um candidato, ainda depende de teste no computador do usuário."
        ), "decisao", "Conversa de planejamento com Marcos Eduardo", "2026-10-18")
        self.add_memory(ident, "Escopo da versão 0.1.0", (
            "Primeira entrega: interface desktop, projetos, tarefas, SQLite, busca textual, importação de notas e de sessões "
            "de estudo da Condution, relatório local e adaptadores HTTP para Ollama e OpenAI. "
            "A integração com Supabase, o MCP no ChatGPT, o microfone, o supervisor de pastas e o agendamento "
            "ainda serão implementados. Nenhuma conta externa está conectada automaticamente."
        ), "nota", "Manifesto desta versão do Nexus ME", "2026-10-19")
        for task in ("Testar o modelo local no Windows e registrar latência", "Conectar a memória ao Supabase com autenticação", "Disponibilizar consultas autenticadas pelo plugin", "Integrar microfone e reaproveitar o OrionXT após revisar seu código"):
            self.add_task(ident, task)
