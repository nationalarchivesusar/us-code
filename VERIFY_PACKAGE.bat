@echo off
setlocal EnableExtensions
set "HERE=%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m pip install --disable-pip-version-check -r "%HERE%requirements.txt" || exit /b 1
%PY% "%HERE%verify_package.py"
exit /b %errorlevel%
