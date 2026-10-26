from __future__ import annotations

import html
import json
import os
import queue
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QRectF, QLocale
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QRadialGradient
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QPushButton, QScrollArea, QSpinBox, QSplitter, QStackedWidget,
    QTableWidget, QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget,
)

from . import __version__
from .config import Settings
from .importers import prepare_import
from .providers import ModelResult, Ollama
from .service import NexusService
from .store import Store


STYLE = """
QWidget { background: #10171f; color: #e5edf2; font-family: 'Segoe UI'; font-size: 14px; }
QMainWindow { background: #10171f; }
QFrame#Sidebar { background: #0b1118; border-right: 1px solid #23303b; }
QFrame#Sidebar QLabel { background: transparent; }
QLabel#Brand { color: #f3fbfc; font-size: 27px; font-weight: 700; letter-spacing: 3px; }
QLabel#Title { font-size: 29px; font-weight: 600; color: #f0f6fa; }
QLabel#Subtitle { color: #93a5b3; font-size: 14px; }
QLabel#Eyebrow { color: #6ad8c1; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
QLabel#Metric { font-size: 32px; font-weight: 600; color: #f0f6fa; }
QLabel#CardTitle { font-size: 17px; font-weight: 600; }
QLabel#Status { color: #9aafbc; padding: 8px; }
QLabel#Badge { color: #6ad8c1; background: #15352f; border-radius: 6px; padding: 7px 11px; font-size: 12px; }
QFrame#Card { background: #17212b; border: 1px solid #293743; border-radius: 13px; }
QFrame#Card QLabel { background: transparent; }
QPushButton { background: #23323f; color: #dfedf2; border: 1px solid #354958; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #304655; border-color: #5b7a8e; }
QPushButton:pressed { background: #3a5767; }
QPushButton:disabled { background: #19232b; color: #637887; border-color: #263540; }
QPushButton#Primary { background: #66dac1; color: #06231e; border: 1px solid #66dac1; }
QPushButton#Primary:hover { background: #88ead4; }
QPushButton#Primary:disabled { background: #264a43; color: #90aaa3; border-color: #264a43; }
QPushButton#Nav { text-align: left; border: none; background: transparent; padding: 13px 17px; color: #9aaebd; }
QPushButton#Nav:checked { color: #79e4cc; background: #15342e; border-left: 3px solid #66dac1; }
QPushButton#Nav:hover { background: #1b2933; }
QPushButton#Danger { color: #efaaaa; background: #322329; border-color: #68404b; }
QLineEdit, QPlainTextEdit, QTextBrowser, QComboBox, QSpinBox { background: #0e1720; border: 1px solid #344652; border-radius: 7px; padding: 9px; selection-background-color: #316b60; }
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus { border: 1px solid #66dac1; }
QComboBox { padding-right: 25px; min-height: 23px; }
QComboBox QAbstractItemView { background: #172630; color: #e5edf2; selection-background-color: #28584d; }
QComboBox::drop-down { border: none; width: 24px; }
QListWidget, QTableWidget { background: #111c25; border: 1px solid #2c3f4b; border-radius: 8px; gridline-color: #2c3f4b; padding: 6px; }
QListWidget::item { padding: 13px 10px; border-bottom: 1px solid #253641; }
QListWidget::item:selected, QTableWidget::item:selected { background: #23493f; color: #baf2e4; }
QHeaderView::section { background: #192a35; color: #9eb2bf; border: none; padding: 10px; font-weight: 600; }
QScrollArea { border: none; }
QScrollBar:vertical { background: #111b24; width: 9px; }
QScrollBar::handle:vertical { background: #3a5361; border-radius: 4px; min-height: 35px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #4d6877; border-radius: 4px; background: #0e1720; }
QCheckBox::indicator:checked { background: #66dac1; border-color: #66dac1; }
QToolTip { color: #e5edf2; background: #1b2a35; border: 1px solid #496372; padding: 5px; }
"""


def label(text: str, name="", wrap=True):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)
    widget.setWordWrap(wrap)
    if name:
        widget.setObjectName(name)
    return widget


def button(text, action, primary=False, name=""):
    widget = QPushButton(text)
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.clicked.connect(action)
    if primary or name:
        widget.setObjectName("Primary" if primary else name)
    return widget


def column(parent=None, margins=0):
    layout = QVBoxLayout(parent)
    layout.setContentsMargins(margins, margins, margins, margins)
    layout.setSpacing(15)
    return layout


def card(title=""):
    frame = QFrame()
    frame.setObjectName("Card")
    layout = column(frame, 22)
    if title:
        layout.addWidget(label(title, "CardTitle"))
    return frame, layout


class CoreMark(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(184, 184)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        glow = QRadialGradient(92, 92, 84)
        glow.setColorAt(0, QColor(72, 178, 153, 100))
        glow.setColorAt(1, QColor(40, 130, 116, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(8, 8, 168, 168))
        for radius, alpha in [(73, 45), (57, 95), (42, 170)]:
            p.setPen(QPen(QColor(102, 218, 193, alpha), 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(92-radius, 92-radius, radius*2, radius*2))
        p.setPen(QPen(QColor("#8cebd4"), 3))
        p.drawArc(QRectF(35, 35, 114, 114), 20*16, 95*16)
        p.drawArc(QRectF(35, 35, 114, 114), 200*16, 95*16)
        p.setPen(QColor("#c3fff0"))
        p.setFont(QFont("Segoe UI", 29, QFont.Weight.DemiBold))
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "N")


class TextDialog(QDialog):
    def __init__(self, parent, title, text, accept_label="Fechar", description="", cancel=False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(860, 650)
        layout = column(self, 22)
        layout.addWidget(label(title, "CardTitle"))
        if description:
            layout.addWidget(label(description, "Subtitle"))
        editor = QPlainTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(text)
        layout.addWidget(editor, 1)
        row = QHBoxLayout()
        row.addStretch()
        if cancel:
            row.addWidget(button("Cancelar", self.reject))
        row.addWidget(button(accept_label, self.accept, primary=True))
        layout.addLayout(row)


class MemoryDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Nova memória")
        self.resize(660, 590)
        layout = column(self, 22)
        layout.addWidget(label("Registrar conhecimento", "CardTitle"))
        form = QFormLayout()
        self.title = QLineEdit()
        self.title.setMaxLength(180)
        self.kind = QComboBox()
        for text, value in [("Nota", "nota"), ("Decisão", "decisao"), ("Documento", "documento")]:
            self.kind.addItem(text, value)
        self.source = QLineEdit("Registro manual de Marcos Eduardo")
        self.date = QLineEdit()
        self.date.setPlaceholderText("AAAA-MM-DD; deixe vazio para usar agora")
        form.addRow("Título", self.title)
        form.addRow("Tipo", self.kind)
        form.addRow("Fonte", self.source)
        form.addRow("Data da fonte", self.date)
        layout.addLayout(form)
        self.content = QPlainTextEdit()
        self.content.setPlaceholderText("Registre o fato, a decisão ou a pendência e de onde veio essa informação.")
        layout.addWidget(self.content, 1)
        self.cloud = QCheckBox("Permitir incluir esta memória em consultas ao GPT após revisar o envio")
        layout.addWidget(self.cloud)
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.button(QDialogButtonBox.StandardButton.Save).setText("Salvar memória")
        controls.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        controls.accepted.connect(self.validate_and_accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def values(self):
        return {"title": self.title.text(), "content": self.content.toPlainText(), "kind": self.kind.currentData(),
                "source": self.source.text(), "source_at": self.date.text().strip() or None,
                "cloud_allowed": self.cloud.isChecked()}

    def validate_and_accept(self):
        from .security import clean_text
        from .store import source_date
        try:
            values = self.values()
            for key, limit in [("title", 180), ("content", 40000), ("source", 500)]:
                clean_text(values[key], key, limit)
            source_date(values["source_at"])
        except ValueError as exc:
            QMessageBox.warning(self, "Revise o registro", str(exc))
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, store: Store, settings: Settings, directory: Path):
        super().__init__()
        self.store, self.settings, self.directory = store, settings, directory
        self.service = NexusService(store, settings)
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.busy = False
        self.results = queue.Queue()
        self.sessions = {}
        self.last_answer = ""
        self.speech = None
        self.setWindowTitle(f"Nexus ME · {__version__}")
        self.resize(1320, 900)
        self.setMinimumSize(1020, 720)
        self.setStyleSheet(STYLE)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side = column(sidebar, 18)
        side.addSpacing(15)
        side.addWidget(label("NEXUS", "Brand"))
        side.addWidget(label("M E  /  PERSONAL INTELLIGENCE", "Eyebrow"))
        side.addSpacing(35)
        self.nav = []
        for index, name in enumerate(["01   Visão geral", "02   Conversa", "03   Memória", "04   Tarefas", "05   Conexões", "06   Atividade"]):
            b = button(name, lambda checked=False, i=index: self.navigate(i), name="Nav")
            b.setCheckable(True)
            self.nav.append(b)
            side.addWidget(b)
        side.addStretch()
        side.addWidget(label("NÚCLEO LOCAL", "Eyebrow"))
        side.addWidget(label("Sua memória, no seu dispositivo.\n\nPrimeira versão · 0.1.0", "Subtitle"))
        side.addSpacing(12)
        root.addWidget(sidebar)
        main = QWidget()
        body = column(main, 28)
        top = QHBoxLayout()
        space_label = label("ESPAÇO DE TRABALHO", "Eyebrow", wrap=False)
        top.addWidget(space_label)
        top.addStretch()
        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(220)
        self.project_combo.setMaximumWidth(380)
        self.project_combo.currentIndexChanged.connect(self.change_project)
        top.addWidget(self.project_combo)
        self.new_project_button = button("+ Projeto", self.safe(self.add_project))
        top.addWidget(self.new_project_button)
        body.addLayout(top)
        self.stack = QStackedWidget()
        body.addWidget(self.stack, 1)
        self.status = label("Pronto. Escolha um projeto para começar.", "Status")
        body.addWidget(self.status)
        root.addWidget(main, 1)
        self.make_dashboard()
        self.make_chat()
        self.make_memory()
        self.make_tasks()
        self.make_connections()
        self.make_activity()
        self.load_projects()
        self.navigate(0)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll_results)
        self.timer.start(100)

    def safe(self, action):
        def wrapped(*args):
            try:
                return action()
            except Exception as exc:
                self.error(exc)
        return wrapped

    def error(self, exc):
        message = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else f"Não foi possível concluir ({type(exc).__name__}). Verifique o arquivo e as permissões."
        self.status.setText(message)
        QMessageBox.warning(self, "Nexus ME", message)

    @property
    def project_id(self):
        return self.project_combo.currentData()

    def session_id(self):
        if self.project_id not in self.sessions:
            self.sessions[self.project_id] = self.store.latest_session(self.project_id)
        return self.sessions[self.project_id]

    def page(self, title, subtitle):
        page = QWidget()
        layout = column(page)
        layout.addSpacing(12)
        layout.addWidget(label(title, "Title"))
        layout.addWidget(label(subtitle, "Subtitle"))
        self.stack.addWidget(page)
        return layout

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, btn in enumerate(self.nav):
            btn.setChecked(i == index)
        if self.project_id:
            self.refresh()

    def load_projects(self, selected=None):
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        for project in self.store.projects():
            self.project_combo.addItem(project["name"], project["id"])
        if selected:
            self.project_combo.setCurrentIndex(self.project_combo.findData(selected))
        self.project_combo.blockSignals(False)
        self.change_project()

    def change_project(self, *_):
        if not self.project_id:
            return
        self.last_answer = ""
        if self.speech:
            self.speech.stop()
        self.refresh()
        self.load_chat()

    def add_project(self):
        name, ok = QInputDialog.getText(self, "Novo projeto", "Nome do projeto:")
        if not ok or not name.strip():
            return
        goal, ok = QInputDialog.getMultiLineText(self, "Objetivo", "O que esse projeto deve alcançar?")
        if ok:
            ident = self.store.add_project(name, goal)
            self.load_projects(ident)
            self.status.setText("Projeto criado. Adicione suas primeiras memórias.")

    def make_dashboard(self):
        layout = self.page("Tudo começa com contexto.", "Um lugar para conversar, registrar decisões e acompanhar o que vem a seguir.")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        inner = column(content)
        hero, hero_box = card()
        hero_row = QHBoxLayout()
        intro = QVBoxLayout()
        intro.setSpacing(13)
        intro.addWidget(label("NEXUS ME  /  01", "Eyebrow"))
        intro.addWidget(label("Seu assistente.\nCom memória e origem.", "Title"))
        intro.addWidget(label("Consulte o que foi registrado, mantenha decisões por projeto e escolha quando chamar uma IA.", "Subtitle"))
        actions = QHBoxLayout()
        actions.addWidget(button("Abrir conversa  →", lambda: self.navigate(1), primary=True))
        actions.addWidget(button("Registrar memória", self.safe(self.add_memory)))
        actions.addStretch()
        intro.addLayout(actions)
        hero_row.addLayout(intro, 1)
        hero_row.addWidget(CoreMark())
        hero_box.addLayout(hero_row)
        inner.addWidget(hero)
        metrics = QHBoxLayout()
        self.metric_labels = []
        for caption in ["memórias neste projeto", "tarefas pendentes", "permitidas para GPT"]:
            tile, stack = card()
            val = label("0", "Metric")
            self.metric_labels.append(val)
            stack.addWidget(val)
            stack.addWidget(label(caption, "Subtitle"))
            metrics.addWidget(tile)
        inner.addLayout(metrics)
        lower = QHBoxLayout()
        recent, rec = card("Últimos registros")
        self.recent_text = label("", "Subtitle")
        rec.addWidget(self.recent_text)
        rec.addStretch()
        rec.addWidget(button("Ver memória", lambda: self.navigate(2)))
        lower.addWidget(recent, 3)
        connection, con = card("Estado das conexões")
        self.connection_text = label("", "Subtitle")
        con.addWidget(self.connection_text)
        con.addStretch()
        con.addWidget(button("Configurar IA", lambda: self.navigate(4)))
        lower.addWidget(connection, 2)
        inner.addLayout(lower)
        inner.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

    def make_chat(self):
        layout = self.page("Converse com o Nexus.", "A conversa usa somente o projeto selecionado. Cada resposta identifica o modo utilizado.")
        options = QHBoxLayout()
        self.mode = QComboBox()
        self.mode.addItem("Consultar registros · sem IA", "memory")
        self.mode.addItem("Conversa local · Ollama", "ollama")
        self.mode.addItem("Análise sob demanda · GPT", "openai")
        options.addWidget(self.mode)
        options.addStretch()
        options.addWidget(button("Nova conversa", self.new_conversation))
        options.addWidget(button("Ouvir resposta", self.safe(self.speak)))
        layout.addLayout(options)
        self.chat_view = QTextBrowser()
        self.chat_view.setOpenExternalLinks(False)
        self.chat_view.setOpenLinks(False)
        self.chat_view.setStyleSheet("QTextBrowser { padding: 20px; border: 1px solid #293e4a; background: #121e27; }")
        layout.addWidget(self.chat_view, 1)
        self.prompt = QPlainTextEdit()
        self.prompt.setPlaceholderText("Ex.: Como está o Nexus ME? Que decisões estão registradas?")
        self.prompt.setMaximumHeight(105)
        layout.addWidget(self.prompt)
        bottom = QHBoxLayout()
        bottom.addWidget(label("As respostas da IA podem errar. Confira as fontes recuperadas.", "Subtitle"))
        bottom.addStretch()
        self.send = button("Consultar  →", self.safe(self.send_message), primary=True)
        bottom.addWidget(self.send)
        layout.addLayout(bottom)

    def new_conversation(self):
        if self.busy:
            self.status.setText("Aguarde a resposta atual para iniciar outra conversa.")
            return
        self.sessions[self.project_id] = str(uuid.uuid4())
        self.last_answer = ""
        self.load_chat()

    def load_chat(self):
        rows = self.store.messages(self.project_id, self.session_id())
        if not rows:
            self.chat_view.setHtml("<h2 style='color:#c3f7e8'>Pronto quando você estiver.</h2><p style='color:#9fb1bf'>Comece consultando as memórias do projeto. Para conversar com uma IA, configure o Ollama ou a API nas Conexões.</p>")
            return
        output = []
        names = {"memory": "REGISTROS · SEM IA", "ollama": "NEXUS · OLLAMA", "openai": "NEXUS · GPT"}
        for row in rows:
            heading = "VOCÊ" if row["role"] == "user" else names.get(row["provider"], "NEXUS")
            color = "#9fb1bf" if row["role"] == "user" else "#76e0c7"
            body = html.escape(row["content"]).replace("\n", "<br>")
            output.append(f"<p style='color:{color};font-size:11px;'><b>{heading}</b> · {html.escape(row['created_at'][:16].replace('T',' '))} UTC</p><p style='line-height:1.55'>{body}</p><hr style='color:#243946'>")
        self.chat_view.setHtml("".join(output))
        bar = self.chat_view.verticalScrollBar()
        bar.setValue(bar.maximum())

    def run_job(self, task, success, description):
        if self.busy:
            raise ValueError("Já existe uma operação em andamento. Aguarde sua conclusão.")
        self.busy = True
        self.send.setEnabled(False)
        self.project_combo.setEnabled(False)
        self.new_project_button.setEnabled(False)
        self.status.setText(description)
        def worker():
            try:
                self.results.put((success, task(), None))
            except Exception as exc:
                self.results.put((success, None, exc))
        threading.Thread(target=worker, daemon=True, name="nexus-request").start()

    def poll_results(self):
        try:
            callback, result, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        self.send.setEnabled(True)
        self.project_combo.setEnabled(True)
        self.new_project_button.setEnabled(True)
        if error:
            self.error(error)
        else:
            try:
                callback(result)
            except Exception as exc:
                self.error(exc)

    def send_message(self):
        from .security import clean_text
        question = clean_text(self.prompt.toPlainText(), "Pergunta", 4000)
        project, session, provider = self.project_id, self.session_id(), self.mode.currentData()
        # Freeze settings during background calls and review.
        service = NexusService(self.store, Settings(**vars(self.settings)))
        def finish(value):
            result, refs = value
            if isinstance(result, ModelResult):
                response = result.text
                response += "\n\nFontes recuperadas para esta resposta (não são validação automática):\n"
                response += "\n".join(f"[{r['id'][:8]}] {r['title']} · {r['source_at']}" for r in refs) or "Nenhuma."
            else:
                response = result
            service.record_exchange(project, session, question, response, provider, result if isinstance(result, ModelResult) else None)
            self.last_answer = response
            if self.prompt.toPlainText().strip() == question:
                self.prompt.clear()
            self.load_chat()
            self.refresh()
            self.status.setText("Consulta concluída. A resposta ficou no histórico; não foi salva automaticamente como memória.")
        if provider == "memory":
            finish(service.memory_answer(project, question))
        elif provider == "ollama":
            self.run_job(lambda: service.local_answer(project, session, question), finish, "O modelo local está preparando a resposta…")
        else:
            if not self.api_key:
                raise ValueError("Configure uma chave de API em Conexões antes de consultar o GPT.")
            request = service.preview_cloud(project, question)
            dialog = TextDialog(self, "Revisar envio ao GPT", request.payload_json, "Enviar esta consulta", (
                "Este é o conteúdo exato que será enviado à API da OpenAI e poderá gerar custo. "
                "Inclui sua pergunta e apenas memórias permitidas. O histórico local e as tarefas não são enviados."
            ), cancel=True)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.status.setText("Envio cancelado. Nenhuma chamada ao GPT foi feita.")
                return
            key = self.api_key
            self.run_job(lambda: service.cloud_answer(request, request.digest, key), finish, "Consulta enviada à API da OpenAI. Aguardando resposta…")

    def make_memory(self):
        layout = self.page("Memória com evidência.", "Registros locais, com fonte e data. Uma resposta da IA só vira memória se você decidir registrá-la.")
        row = QHBoxLayout()
        self.memory_search = QLineEdit()
        self.memory_search.setPlaceholderText("Buscar título ou conteúdo…")
        self.memory_search.textChanged.connect(self.refresh_memory)
        row.addWidget(self.memory_search, 1)
        row.addWidget(button("Importar arquivo", self.safe(self.import_file)))
        row.addWidget(button("+ Memória", self.safe(self.add_memory), primary=True))
        layout.addLayout(row)
        split = QSplitter()
        self.memory_list = QListWidget()
        self.memory_list.currentItemChanged.connect(self.show_memory)
        split.addWidget(self.memory_list)
        details = QWidget()
        detail = column(details, 8)
        self.memory_meta = label("Selecione um registro.", "Subtitle")
        detail.addWidget(self.memory_meta)
        self.memory_text = QPlainTextEdit()
        self.memory_text.setReadOnly(True)
        detail.addWidget(self.memory_text, 1)
        self.cloud_checkbox = QCheckBox("Permitir incluir em consultas ao GPT")
        detail.addWidget(self.cloud_checkbox)
        controls = QHBoxLayout()
        controls.addWidget(button("Salvar permissão", self.safe(self.save_permission)))
        controls.addWidget(button("Excluir", self.safe(self.delete_memory), name="Danger"))
        detail.addLayout(controls)
        split.addWidget(details)
        split.setSizes([310, 580])
        layout.addWidget(split, 1)
        actions = QHBoxLayout()
        actions.addWidget(button("Ver resumo dos registros", self.safe(self.view_brief)))
        actions.addWidget(button("Exportar resumo .md", self.safe(self.export_brief)))
        actions.addStretch()
        layout.addLayout(actions)

    def refresh_memory(self, *_):
        if not self.project_id:
            return
        previous = self.memory_list.currentItem()
        selected = previous.data(Qt.ItemDataRole.UserRole) if previous else None
        self.memory_list.clear()
        for memory in self.store.memories(self.project_id, self.memory_search.text()):
            item = QListWidgetItem(f"{memory['title']}\n{memory['source_at'][:10]}  ·  {memory['kind']}")
            item.setData(Qt.ItemDataRole.UserRole, memory["id"])
            self.memory_list.addItem(item)
            if memory["id"] == selected:
                self.memory_list.setCurrentItem(item)
        if self.memory_list.count() and not self.memory_list.currentItem():
            self.memory_list.setCurrentRow(0)

    def show_memory(self, item=None, previous=None):
        if item is None:
            self.memory_meta.setText("Selecione um registro.")
            self.memory_text.clear()
            self.cloud_checkbox.setChecked(False)
            return
        memory = self.store.memory(item.data(Qt.ItemDataRole.UserRole))
        self.memory_meta.setText(f"[{memory['id'][:8]}] {memory['title']}\nFonte: {memory['source']}\nData da fonte: {memory['source_at']}\nRegistrado em: {memory['created_at']}")
        self.memory_text.setPlainText(memory["content"])
        self.cloud_checkbox.setChecked(bool(memory["cloud_allowed"]))

    def add_memory(self):
        dialog = MemoryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            _, created = self.store.add_memory(self.project_id, **dialog.values())
            self.refresh()
            self.status.setText("Memória registrada." if created else "Registro idêntico já existe; nenhuma duplicata foi criada.")

    def save_permission(self):
        item = self.memory_list.currentItem()
        if not item:
            raise ValueError("Selecione uma memória.")
        self.store.set_cloud_allowed(item.data(Qt.ItemDataRole.UserRole), self.cloud_checkbox.isChecked())
        self.refresh()
        self.status.setText("Permissão atualizada. Nada foi enviado à nuvem.")

    def delete_memory(self):
        item = self.memory_list.currentItem()
        if item and QMessageBox.question(self, "Excluir memória", "Excluir este registro do Nexus? O arquivo original e backups existentes permanecem intactos.") == QMessageBox.StandardButton.Yes:
            self.store.delete_memory(item.data(Qt.ItemDataRole.UserRole))
            self.refresh()
            self.status.setText("Memória excluída do banco local.")

    def import_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Importar registro", "", "Notas e exportações (*.md *.txt *.json)")
        if not path:
            return
        entries = prepare_import(Path(path))
        preview = "\n\n".join(f"{e['title']}\nData: {e['source_at']}\nFonte: {e['source']}\n{e['content']}" for e in entries)
        dialog = TextDialog(self, f"Revisar {len(entries)} registro(s)", preview, "Importar no projeto", (
            "O arquivo original será apenas lido. Os registros entram como locais, sem permissão para GPT. "
            "Em exports da Condution, somente sessões de estudo são importadas."
        ), cancel=True)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            results = self.store.add_memories(self.project_id, entries)
            created = sum(int(new) for _, new in results)
            self.refresh()
            self.status.setText(f"Importação concluída: {created} novo(s); {len(results)-created} já existente(s).")

    def view_brief(self):
        TextDialog(self, "Resumo local do projeto", self.service.brief(self.project_id), description="Compilação dos registros. Não executa análise por IA nem agenda tarefas.").exec()

    def export_brief(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar resumo", "nexus_resumo.md", "Markdown (*.md)")
        if path:
            Path(path).write_text(self.service.brief(self.project_id), encoding="utf-8")
            self.store.audit("brief_exported", self.project_id)
            self.status.setText("Resumo exportado com fontes e datas.")

    def make_tasks(self):
        layout = self.page("O próximo passo, claro.", "Tarefas deste projeto. Marcar como concluída registra sua decisão; não executa a tarefa.")
        row = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setMaxLength(500)
        self.task_input.setPlaceholderText("Qual é a próxima ação?")
        self.task_input.returnPressed.connect(self.safe(self.add_task))
        row.addWidget(self.task_input, 1)
        row.addWidget(button("Adicionar tarefa", self.safe(self.add_task), primary=True))
        layout.addLayout(row)
        self.task_table = QTableWidget(0, 3)
        self.task_table.setHorizontalHeaderLabels(["Estado", "Tarefa", "Atualização (UTC)"])
        self.task_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.task_table.setColumnWidth(0, 110)
        self.task_table.setColumnWidth(2, 180)
        self.task_table.verticalHeader().setVisible(False)
        self.task_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.task_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.task_table, 1)
        layout.addWidget(button("Alternar pendente / concluída", self.safe(self.toggle_task)))

    def add_task(self):
        self.store.add_task(self.project_id, self.task_input.text())
        self.task_input.clear()
        self.refresh()
        self.status.setText("Tarefa registrada.")

    def toggle_task(self):
        row = self.task_table.currentRow()
        if row < 0:
            raise ValueError("Selecione uma tarefa.")
        data = self.task_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        self.store.set_task_done(data["id"], not data["done"])
        self.refresh()

    def make_connections(self):
        layout = self.page("Conecte quando fizer sentido.", "A memória funciona offline. Serviços externos precisam de configuração própria neste aplicativo.")
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        inner = column(content)
        local, loc = card("Ollama · conversa local")
        form = QFormLayout()
        self.ollama_url = QLineEdit(self.settings.ollama_url)
        self.ollama_model = QComboBox()
        self.ollama_model.setEditable(True)
        self.ollama_model.setCurrentText(self.settings.ollama_model)
        self.ollama_model.lineEdit().setPlaceholderText("Selecione ou digite o nome exato instalado")
        form.addRow("Endereço local", self.ollama_url)
        form.addRow("Modelo", self.ollama_model)
        loc.addLayout(form)
        loc.addWidget(label("Instale o Ollama separadamente e baixe o modelo escolhido. O Nexus não baixa modelos. Configure OLLAMA_NO_CLOUD=1 no Ollama para desabilitar os recursos de nuvem do serviço.", "Subtitle"))
        self.ollama_status = label("Conexão ainda não testada nesta sessão.", "Subtitle")
        loc.addWidget(self.ollama_status)
        loc.addWidget(button("Buscar modelos instalados", self.safe(self.test_ollama)))
        inner.addWidget(local)
        cloud, cl = card("GPT · análise sob demanda")
        form = QFormLayout()
        self.openai_model = QLineEdit(self.settings.openai_model)
        self.openai_model.setPlaceholderText("ID do modelo disponível na sua conta de API")
        self.key_input = QLineEdit(self.api_key)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Chave de API · mantida apenas nesta sessão")
        form.addRow("Modelo", self.openai_model)
        form.addRow("API key", self.key_input)
        self.output_tokens = QSpinBox()
        self.output_tokens.setRange(256, 4096)
        self.output_tokens.setValue(self.settings.max_output_tokens)
        self.context_budget = QSpinBox()
        self.context_budget.setRange(1000, 12000)
        self.context_budget.setValue(self.settings.context_chars)
        form.addRow("Máximo de tokens de saída", self.output_tokens)
        form.addRow("Caracteres de contexto recuperado", self.context_budget)
        cl.addLayout(form)
        cl.addWidget(label("A assinatura do ChatGPT não configura esta API. Cada envio mostra o conteúdo para revisão e pode gerar custo. A chave não é escrita no banco ou no arquivo de configurações. store=false não substitui as políticas de retenção do provedor.", "Subtitle"))
        inner.addWidget(cloud)
        future, fut = card("Próximas conexões")
        fut.addWidget(label("Supabase / MCP no ChatGPT — ainda não implementados\nNotion / GitHub / Obsidian — ainda não conectados\nMicrofone / OrionXT — aguardam integração\nRelatórios diários — sem agendamento nesta versão", "Subtitle"))
        inner.addWidget(future)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        layout.addWidget(button("Salvar configurações", self.safe(self.save_settings), primary=True))

    def settings_from_form(self):
        settings = Settings(self.ollama_url.text(), self.ollama_model.currentText(), self.openai_model.text(),
                            self.context_budget.value(), self.output_tokens.value())
        settings.validate()
        return settings

    def save_settings(self):
        self.settings = self.settings_from_form()
        self.settings.save(self.directory)
        self.api_key = self.key_input.text().strip()
        self.service = NexusService(self.store, self.settings)
        self.refresh()
        self.status.setText("Preferências salvas. A chave de API fica só na memória desta sessão.")

    def test_ollama(self):
        settings = self.settings_from_form()
        def done(models):
            current = self.ollama_model.currentText()
            self.ollama_model.clear()
            self.ollama_model.addItems(models)
            if current in models:
                self.ollama_model.setCurrentText(current)
            self.ollama_status.setText(f"Serviço alcançado. {len(models)} modelo(s) listado(s). A geração ainda depende de um teste de conversa.")
            self.status.setText("Escolha o modelo e salve as configurações." if models else "O serviço respondeu, mas não listou modelos locais. Instale um no Ollama.")
        self.run_job(lambda: Ollama(settings).models(), done, "Consultando os modelos do Ollama local…")

    def make_activity(self):
        layout = self.page("Atividade rastreável.", "Histórico das operações do aplicativo. Logs não guardam chaves nem o conteúdo das memórias.")
        self.audit_text = QPlainTextEdit()
        self.audit_text.setReadOnly(True)
        layout.addWidget(self.audit_text, 1)
        row = QHBoxLayout()
        row.addWidget(button("Criar backup do banco", self.safe(self.backup)))
        row.addWidget(button("Sobre os dados locais", self.data_info))
        row.addStretch()
        layout.addLayout(row)

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Backup do Nexus ME", "nexus_backup.sqlite3", "SQLite (*.sqlite3)")
        if path:
            self.store.backup(Path(path))
            self.refresh()
            self.status.setText("Backup consistente criado. Guarde-o em um local protegido.")

    def data_info(self):
        TextDialog(self, "Seus dados", f"Pasta de dados:\n{self.directory}\n\nBanco:\n{self.store.path}\n\nO banco contém projetos, memórias, tarefas e histórico das conversas. Não há criptografia própria do banco nesta versão. Use a proteção da sua conta do Windows e do disco.\n\nConfigurações não guardam API keys. Backups incluem o histórico local. A restauração deve ser feita com o aplicativo fechado; consulte o README.").exec()

    def speak(self):
        if not self.last_answer:
            raise ValueError("Faça uma consulta nesta conversa antes de usar a leitura em voz alta.")
        from PySide6.QtTextToSpeech import QTextToSpeech
        if not self.speech:
            engines = QTextToSpeech.availableEngines()
            if not engines:
                raise ValueError("Nenhum mecanismo de voz do sistema está disponível. A conversa por texto continua funcionando.")
            self.speech = QTextToSpeech(engines[0], self)
            voices = self.speech.availableVoices()
            portuguese = [v for v in voices if v.locale().language() == QLocale.Language.Portuguese]
            if portuguese:
                self.speech.setVoice(portuguese[0])
        self.speech.stop()
        self.speech.say(self.last_answer[:6000])
        self.status.setText("Leitura solicitada ao mecanismo de voz do sistema.")

    def refresh(self):
        project = self.project_id
        rows, tasks = self.store.memories(project), self.store.tasks(project)
        for item, value in zip(self.metric_labels, [len(rows), sum(not t["done"] for t in tasks), sum(r["cloud_allowed"] for r in rows)]):
            item.setText(str(value))
        self.recent_text.setText("\n\n".join(f"{r['title']}\n{r['source_at'][:10]} · {r['kind']}" for r in rows[:3]) or "Ainda não há memórias neste projeto. Registre uma decisão ou importe um documento.")
        self.connection_text.setText("Memória SQLite  ·  disponível\n\nOllama  ·  " + ("modelo configurado" if self.settings.ollama_model else "aguarda configuração") + "\n\nGPT  ·  " + ("configurado; não testado" if self.api_key and self.settings.openai_model else "aguarda configuração") + "\n\nSupabase  ·  etapa seguinte")
        self.refresh_memory()
        self.task_table.setRowCount(len(tasks))
        for i, task in enumerate(tasks):
            for col, text in enumerate(["Concluída" if task["done"] else "Pendente", task["title"], task["updated_at"][:16].replace("T", " ")]):
                item = QTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, task)
                self.task_table.setItem(i, col, item)
            self.task_table.setRowHeight(i, 52)
        self.audit_text.setPlainText("\n\n".join(f"{e['created_at']}  |  {e['action']}\nID: {e['entity_id']}  {e['details']}" for e in self.store.events()))

    def closeEvent(self, event):
        if self.busy:
            answer = QMessageBox.question(self, "Consulta em andamento", "Fechar agora descarta a resposta local. Uma chamada já enviada ao GPT ainda pode gerar cobrança. Deseja fechar?")
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if self.speech:
            self.speech.stop()
        self.api_key = ""
        self.key_input.clear()
        self.timer.stop()
        event.accept()
