@echo off
setlocal
cd /d "%~dp0"
echo Nexus ME - Instalacao local
echo Requer Python 3.12 ou superior e internet para baixar PySide6.
echo.
if exist ".venv\Scripts\python.exe" goto dependencies
py -3 -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
if not errorlevel 1 goto create_with_py
python -c "import sys; assert sys.version_info >= (3,12)" >nul 2>&1
if errorlevel 1 goto missing_python
python -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:create_with_py
py -3 -m venv .venv
if errorlevel 1 goto failed
:dependencies
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo.
echo Instalado. Abra INICIAR_NEXUS.bat.
pause
exit /b 0
:missing_python
echo Instale o Python 3.12 ou superior pelo site python.org, com pip.
echo Depois execute este arquivo novamente.
pause
exit /b 1
:failed
echo A instalacao falhou. Confira a mensagem acima e sua conexao.
pause
exit /b 1
