@echo off
setlocal EnableExtensions
chcp 65001 >nul

set "REPO=%~1"
if "%REPO%"=="" set "REPO=D:\us-code"
set "HERE=%~dp0"

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
) else (
    set "PY=python"
)

echo.
echo ============================================================
echo  USAR PUBLIC-LAW FINALIZER
echo  Repository: %REPO%
echo ============================================================
echo.

%PY% -c "import lxml" >nul 2>&1
if errorlevel 1 (
    echo Installing required XML library...
    %PY% -m pip install --disable-pip-version-check lxml
    if errorlevel 1 goto :fail
)

%PY% "%HERE%finish_public_laws.py" --repo "%REPO%" --apply --cleanup
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  COMPLETE
echo  The replacement laws were incorporated and validated.
echo  Review FINAL-PUBLIC-LAWS-REPORT.md in codification\reports.
echo ============================================================
exit /b 0

:fail
echo.
echo ============================================================
echo  FAILED
echo  The finalizer restores changed Code files from its backup
echo  whenever failure occurs after a write.
echo  Read the newest report under codification\reports.
echo ============================================================
exit /b 1
