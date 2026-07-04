@echo off
setlocal
set "HERE=%~dp0.."
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m pip install --disable-pip-version-check -r "%HERE%\requirements.txt" || exit /b 1
%PY% -m unittest discover -s "%HERE%\tests" -p "test_*.py" -v
exit /b %errorlevel%
