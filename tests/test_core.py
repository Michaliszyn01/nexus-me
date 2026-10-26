import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexus_me.config import Settings, validate_local_url
from nexus_me.importers import prepare_import
from nexus_me.providers import ModelResult
from nexus_me.security import reject_secrets
from nexus_me.service import NexusService
from nexus_me.store import Store


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "test.sqlite3")
        self.first = self.store.add_project("Primeiro", "Meta um")
        self.second = self.store.add_project("Segundo", "Meta dois")
        self.settings = Settings(openai_model="modelo-configurado-pelo-usuario")
        self.service = NexusService(self.store, self.settings)

    def note(self, project=None, title="Decisão de teste", content="Validar encaixes", **kwargs):
        return self.store.add_memory(project or self.first, title, content, source_at="2026-08-01", **kwargs)

    def test_reopen_keeps_state_and_project_isolation(self):
        self.note(content="Informação privada do primeiro projeto")
        other = Store(self.store.path)
        self.assertEqual(len(other.memories(self.first)), 1)
        self.assertEqual(other.memories(self.second), [])
        answer, _ = self.service.memory_answer(self.second, "Informação privada")
        self.assertNotIn("Informação privada do primeiro", answer)

    def test_duplicate_and_changed_source_are_distinguished(self):
        ident, created = self.note()
        self.assertTrue(created)
        self.assertEqual(self.note(), (ident, False))
        self.note(content="Agora testar também as pernas")
        self.assertEqual(len(self.store.memories(self.first)), 2)

    def test_atomic_import_does_not_leave_partial_records(self):
        with self.assertRaises(ValueError):
            self.store.add_memories(self.first, [{"title": "Válida", "content": "ok"}, {"title": "", "content": "inválida"}])
        self.assertEqual(self.store.memories(self.first), [])

    def test_source_dates_are_not_replaced_by_import_date(self):
        ident, _ = self.note()
        self.assertEqual(self.store.memory(ident)["source_at"], "2026-08-01")
        self.assertIn("2026-08-01", self.service.brief(self.first))

    def test_cloud_payload_excludes_private_notes_tasks_and_history(self):
        self.note(content="PRIVATE_LOCAL_ONLY")
        self.note(title="Permitida", content="SHARED_DATA", cloud_allowed=True)
        self.store.add_task(self.first, "PRIVATE_TASK")
        self.store.add_message(self.first, "session", "user", "PRIVATE_HISTORY", "ollama")
        payload = self.service.preview_cloud(self.first, "Como está o projeto?").payload_json
        self.assertIn("SHARED_DATA", payload)
        for private in ["PRIVATE_LOCAL_ONLY", "PRIVATE_TASK", "PRIVATE_HISTORY"]:
            self.assertNotIn(private, payload)
        self.assertFalse(json.loads(payload)["store"])

    def test_changed_approval_blocks_network(self):
        request = self.service.preview_cloud(self.first, "Resumo")
        with patch("nexus_me.service.OpenAI.chat") as call:
            with self.assertRaises(ValueError):
                self.service.cloud_answer(request, "invalid", "unused")
            call.assert_not_called()

    def test_revocation_blocks_prepared_cloud_request(self):
        ident, _ = self.note(cloud_allowed=True)
        request = self.service.preview_cloud(self.first, "Resumo")
        self.store.set_cloud_allowed(ident, False)
        with patch("nexus_me.service.OpenAI.chat") as call:
            with self.assertRaises(ValueError):
                self.service.cloud_answer(request, request.digest, "unused")
            call.assert_not_called()

    def test_approved_request_uses_exact_reviewed_payload(self):
        request = self.service.preview_cloud(self.first, "Resumo")
        with patch("nexus_me.service.OpenAI.chat", return_value=ModelResult("Teste", "test")) as call:
            self.service.cloud_answer(request, request.digest, "unused")
        self.assertEqual(call.call_args.args[0], json.loads(request.payload_json))

    def test_secrets_blocked_before_database_write(self):
        secret = "sk-" + "Z" * 32
        with self.assertRaises(ValueError):
            self.note(content=secret)
        self.assertEqual(self.store.memories(self.first), [])
        with self.assertRaises(ValueError):
            self.service.preview_cloud(self.first, "Use " + secret)

    def test_local_endpoint_rejects_remote_credentials_and_paths(self):
        for url in ["https://example.com", "http://127.0.0.1.example.com:11434", "http://user:pass@127.0.0.1:11434", "http://127.0.0.1:11434/api", "http://localhost:11434", "http://127.0.0.1:99999"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_local_url(url)
        self.assertEqual(validate_local_url("http://127.0.0.1:11434/"), "http://127.0.0.1:11434")

    def test_condution_import_preview_is_readonly_and_idempotent(self):
        path = self.root / "export.json"
        data = {"sessoes_estudo": [{"id_origem": 7, "data": "2026-08-01", "materia": "Química", "duracao_minutos": 25}],
                "sessoes_sono": [{"observacoes": "SENSITIVE_SLEEP_DATA"}]}
        original = json.dumps(data).encode()
        path.write_bytes(original)
        prepared = prepare_import(path)
        self.assertNotIn("SENSITIVE_SLEEP_DATA", str(prepared))
        self.store.add_memories(self.first, prepared)
        self.store.add_memories(self.first, prepare_import(path))
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(len(self.store.memories(self.first)), 1)
        self.assertFalse(self.store.memories(self.first)[0]["cloud_allowed"])

    def test_unrecognized_json_fails_without_guessing(self):
        path = self.root / "unknown.json"
        path.write_text('{"items":[{"data":"2026-08-01"}]}')
        with self.assertRaises(ValueError):
            prepare_import(path)

    def test_invalid_dates_fail(self):
        for value in ["ontem", "2026-02-30", "2026-08-01T10:00:00"]:
            with self.assertRaises(ValueError):
                self.store.add_memory(self.first, "Teste", "Conteúdo", source_at=value)

    def test_backup_is_consistent_and_cannot_overwrite_live_database(self):
        self.note()
        destination = self.root / "backup.sqlite3"
        self.store.backup(destination)
        restored = Store(destination)
        self.assertEqual(restored.memories(self.first), self.store.memories(self.first))
        with restored.connection() as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with self.assertRaises(ValueError):
            self.store.backup(self.store.path)

    def test_history_stays_within_project_and_session(self):
        for project, session, text in [(self.first, "a", "FIRST_A"), (self.first, "b", "FIRST_B"), (self.second, "a", "SECOND_A")]:
            self.store.add_message(project, session, "user", text, "ollama")
        with patch("nexus_me.service.Ollama.chat", return_value=ModelResult("ok", "mock")) as call:
            self.service.local_answer(self.first, "a", "Resumo")
        sent = str(call.call_args.args[0])
        self.assertIn("FIRST_A", sent)
        self.assertNotIn("FIRST_B", sent)
        self.assertNotIn("SECOND_A", sent)

    def test_context_has_hard_character_budget(self):
        self.settings.context_chars = 1000
        for index in range(20):
            self.store.add_task(self.first, f"Tarefa {index} " + "a"*480)
            self.note(title=f"Nota {index}", content="conteúdo longo " * 200)
        context, _ = self.service.context(self.first, "status")
        self.assertLessEqual(len(context), 1000)

    def test_generated_summaries_do_not_feed_back_into_retrieval(self):
        self.note(kind="resumo", content="UNVERIFIED_MODEL_INFERENCE")
        context, _ = self.service.context(self.first, "resumo")
        self.assertNotIn("UNVERIFIED_MODEL_INFERENCE", context)

    def test_search_is_accent_insensitive(self):
        self.note(title="Decisão elétrica", content="Braço com bateria")
        self.assertEqual(len(self.store.memories(self.first, "decisao braco")), 1)

    def test_credentials_are_not_part_of_settings(self):
        self.settings.save(self.root)
        data = json.loads((self.root / "settings.json").read_text())
        self.assertFalse(any("key" in field or "token" in field and field != "max_output_tokens" for field in data))
        self.assertEqual(Settings.load(self.root), self.settings)

    def test_tasks_persist_without_becoming_verified_claims(self):
        ident = self.store.add_task(self.first, "Verificar braço")
        self.store.set_task_done(ident, True)
        self.assertTrue(Store(self.store.path).tasks(self.first)[0]["done"])
        self.assertIn("não evidência de testes", self.service.brief(self.first))


if __name__ == "__main__":
    unittest.main()
