@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "REPO=%~1"
if "%REPO%"=="" set "REPO=D:\us-code"
set "HERE=%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m pip install --disable-pip-version-check -r "%HERE%requirements.txt" || exit /b 1
if "%~2"=="" (
    %PY% "%HERE%mass_codifier.py" --repo "%REPO%" --preview-only --minimum-decisions 100 --max-source-holds 10
) else (
    %PY% "%HERE%mass_codifier.py" --repo "%REPO%" --board-json "%~2" --preview-only --minimum-decisions 100 --max-source-holds 10
)
exit /b %errorlevel%
