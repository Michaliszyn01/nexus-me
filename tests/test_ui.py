import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from nexus_me.config import Settings
from nexus_me.providers import ModelResult
from nexus_me.store import Store
from nexus_me.ui import MainWindow, MemoryDialog


class UiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root / "db.sqlite3")
        self.store.seed()
        self.window = MainWindow(self.store, Settings(), self.root)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.busy = False
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def wait_job(self):
        start = time.monotonic()
        while self.window.busy and time.monotonic() - start < 5:
            QTest.qWait(20)
        self.assertFalse(self.window.busy, "Operação da interface não terminou")

    def test_all_screens_open_and_local_chat_persists(self):
        for index in range(6):
            QTest.mouseClick(self.window.nav[index], Qt.MouseButton.LeftButton)
            self.assertEqual(self.window.stack.currentIndex(), index)
        self.window.navigate(1)
        self.window.prompt.setPlainText("Como está o Nexus ME?")
        with patch("nexus_me.service.Ollama.chat") as local, patch("nexus_me.service.OpenAI.chat") as cloud:
            QTest.mouseClick(self.window.send, Qt.MouseButton.LeftButton)
            local.assert_not_called()
            cloud.assert_not_called()
        messages = self.store.messages(self.window.project_id)
        self.assertEqual(len(messages), 2)
        self.assertIn("CONSULTA AOS REGISTROS", self.window.chat_view.toPlainText())
        self.window.new_conversation()
        self.assertIn("Pronto quando", self.window.chat_view.toPlainText())
        self.assertEqual(len(self.store.messages(self.window.project_id)), 2)

    def test_task_and_permission_controls(self):
        self.window.task_input.setText("Teste pela interface")
        self.window.add_task()
        row = self.window.task_table.rowCount() - 1
        self.window.task_table.selectRow(row)
        self.window.toggle_task()
        self.assertTrue(any(t["title"] == "Teste pela interface" and t["done"] for t in self.store.tasks(self.window.project_id)))
        memory_id = self.window.memory_list.currentItem().data(Qt.ItemDataRole.UserRole)
        self.window.cloud_checkbox.setChecked(True)
        self.window.save_permission()
        self.assertTrue(self.store.memory(memory_id)["cloud_allowed"])

    def test_import_dialog_keeps_original_and_deduplicates(self):
        source = self.root / "nota.md"
        source.write_text("Uma nota local de teste.", encoding="utf-8")
        initial = len(self.store.memories(self.window.project_id))
        with patch("nexus_me.ui.QFileDialog.getOpenFileName", return_value=(str(source), "")), patch("nexus_me.ui.TextDialog.exec", return_value=QDialog.DialogCode.Accepted):
            self.window.import_file()
            self.window.import_file()
        self.assertEqual(len(self.store.memories(self.window.project_id)), initial+1)
        self.assertEqual(source.read_text(), "Uma nota local de teste.")

    def test_cloud_cancel_prevents_request_and_history_write(self):
        self.window.api_key = "test-only"
        self.window.settings.openai_model = "configured"
        self.window.mode.setCurrentIndex(2)
        self.window.prompt.setPlainText("Faça uma análise")
        with patch("nexus_me.ui.TextDialog.exec", return_value=QDialog.DialogCode.Rejected), patch("nexus_me.service.OpenAI.chat") as call:
            self.window.send_message()
            call.assert_not_called()
        self.assertEqual(self.store.messages(self.window.project_id), [])

    def test_local_model_runs_in_background_and_restores_controls(self):
        self.window.mode.setCurrentIndex(1)
        self.window.prompt.setPlainText("Olá")
        with patch("nexus_me.service.Ollama.chat", return_value=ModelResult("Resposta simulada de contrato", "local-test")):
            self.window.send_message()
            self.wait_job()
        self.assertTrue(self.window.send.isEnabled())
        self.assertTrue(self.window.project_combo.isEnabled())
        self.assertIn("Resposta simulada", self.window.chat_view.toPlainText())

    def test_saving_settings_does_not_persist_api_key(self):
        self.window.key_input.setText("NOT_A_REAL_KEY_123")
        self.window.save_settings()
        contents = (self.root / "settings.json").read_text()
        self.assertNotIn("NOT_A_REAL_KEY_123", contents)
        self.assertEqual(self.window.api_key, "NOT_A_REAL_KEY_123")


if __name__ == "__main__":
    unittest.main()
