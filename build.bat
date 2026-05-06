@echo off
REM ============================================================
REM  build.bat — Gera o WebexConnectSender.exe
REM  Pré-requisito: dependências instaladas no .venv da pasta
REM ============================================================

SET SCRIPT_DIR=%~dp0
SET VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe
SET VENV_PYINST=%SCRIPT_DIR%.venv\Scripts\pyinstaller.exe

echo [1/2] Verificando ambiente virtual...
IF NOT EXIST "%VENV_PYTHON%" (
    echo ERRO: .venv nao encontrado. Execute primeiro:
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt pyinstaller
    pause
    exit /b 1
)

echo [2/2] Gerando executavel...
"%VENV_PYINST%" send_message.spec ^
    --noconfirm ^
    --clean ^
    --distpath "%SCRIPT_DIR%dist"

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo FALHA na geracao do executavel. Veja o log acima.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Executavel gerado em:  dist\WebexConnectSender.exe
echo  Copie tambem o arquivo .env para a mesma pasta do .exe
echo ============================================================
pause
