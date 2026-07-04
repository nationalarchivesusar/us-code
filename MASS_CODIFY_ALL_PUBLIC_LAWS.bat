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
echo  USAR MASS PUBLIC-LAW CODIFICATION
echo  Repository: %REPO%
echo  Scope: every canonical law card on the NARA public-law board
echo ============================================================
echo.

%PY% -m pip install --disable-pip-version-check -r "%HERE%requirements.txt"
if errorlevel 1 goto :fail

if exist "%REPO%\.git" (
    where git >nul 2>&1
    if not errorlevel 1 (
        git -C "%REPO%" lfs pull >nul 2>&1
    )
)

if "%~2"=="" (
    %PY% "%HERE%mass_codifier.py" ^
        --repo "%REPO%" ^
        --apply ^
        --repair-repo ^
        --minimum-decisions 100 ^
        --max-source-holds 10
) else (
    %PY% "%HERE%mass_codifier.py" ^
        --repo "%REPO%" ^
        --board-json "%~2" ^
        --apply ^
        --repair-repo ^
        --minimum-decisions 100 ^
        --max-source-holds 10
)
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo  MASS CODIFICATION COMPLETE
echo.
echo  Reports:
echo  %REPO%\codification\mass_migration\latest\reports
echo.
echo  Review MASTER-CODIFICATION-REPORT.md and then commit/push.
echo  Trello comments may be posted only after the commit is pushed.
echo ============================================================
exit /b 0

:fail
echo.
echo ============================================================
echo  MASS CODIFICATION DID NOT COMPLETE
echo.
echo  No Code write occurs before the completeness gate passes.
echo  If a later transactional step failed, changed title files were
echo  restored from the run backup.
echo.
echo  Review the newest FAILURE report under:
echo  %REPO%\codification\mass_migration\latest\reports
echo ============================================================
exit /b 1
