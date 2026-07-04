@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 install_round2_plans.py --repo "%~dp0.."
) else (
  python install_round2_plans.py --repo "%~dp0.."
)
if errorlevel 1 (
  echo.
  echo Installation failed. No live Code changes should have been made.
  pause
  exit /b 1
)
echo.
echo Plans installed and scratch-tested successfully.
pause
