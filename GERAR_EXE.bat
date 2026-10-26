@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute INSTALAR.bat primeiro.
  pause
  exit /b 1
)
echo Compilacao opcional no proprio Windows. O pacote entregue e codigo-fonte.
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.10,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --onedir --name NexusME run_nexus.py
if errorlevel 1 goto failed
echo Pronto. Execute dist\NexusME\NexusME.exe.
echo Para mover o app, copie a pasta dist\NexusME inteira.
pause
exit /b 0
:failed
echo Compilacao nao concluida. Revise a mensagem acima.
pause
exit /b 1
