from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .config import Settings, data_directory
from .service import NexusService
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Nexus ME — memória e conversa local")
    parser.add_argument("--data-dir", type=Path, help="Pasta alternativa para os dados")
    parser.add_argument("--doctor", action="store_true", help="Diagnóstico offline; não consulta provedores")
    parser.add_argument("--brief", action="store_true", help="Imprime resumo do projeto no terminal")
    parser.add_argument("--project", help="Nome exato do projeto para --brief")
    parser.add_argument("--version", action="version", version=f"Nexus ME {__version__}")
    args = parser.parse_args()
    directory = (args.data_dir or data_directory()).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        settings = Settings.load(directory)
        store = Store(directory / "nexus.sqlite3")
        store.seed()
    except Exception as exc:
        print(f"Não foi possível abrir o Nexus: {exc}", file=sys.stderr)
        return 1
    if args.doctor:
        with store.connection() as db:
            integrity = db.execute("PRAGMA quick_check").fetchone()[0]
        print(json.dumps({"app": "Nexus ME", "version": __version__, "python": sys.version.split()[0],
                          "data_directory": str(directory), "database": integrity,
                          "projects": len(store.projects()), "ollama_configured": bool(settings.ollama_model),
                          "openai_model_configured": bool(settings.openai_model), "cloud_sync": "not_implemented"}, ensure_ascii=False, indent=2))
        return 0 if integrity == "ok" else 1
    if args.brief:
        projects = store.projects()
        project = next((p for p in projects if not args.project or p["name"] == args.project), None)
        if not project:
            print("Projeto não encontrado.", file=sys.stderr)
            return 1
        print(NexusService(store, settings).brief(project["id"]))
        return 0
    try:
        from PySide6.QtCore import QLockFile
        from PySide6.QtWidgets import QApplication, QMessageBox
        from .ui import MainWindow
    except ImportError:
        print("Instale as dependências: python -m pip install -r requirements.txt", file=sys.stderr)
        return 1
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Nexus ME")
    app.setOrganizationName("ME")
    lock = QLockFile(str(directory / "nexus.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "Nexus ME", "O Nexus já está aberto para esta pasta de dados.")
        return 1
    window = MainWindow(store, settings, directory)
    window.show()
    result = app.exec()
    lock.unlock()
    return result


if __name__ == "__main__":
    raise SystemExit(main())
