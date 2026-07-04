@echo off
setlocal EnableExtensions
chcp 65001 >nul
set "REPO=%~1"
if "%REPO%"=="" set "REPO=D:\us-code"
set "HERE=%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
if "%TRELLO_KEY%"=="" (
  echo TRELLO_KEY is not set.
  exit /b 1
)
if "%TRELLO_TOKEN%"=="" (
  echo TRELLO_TOKEN is not set.
  exit /b 1
)
%PY% -m pip install --disable-pip-version-check requests || exit /b 1
%PY% "%HERE%post_trello_comments.py" --repo "%REPO%" --post
exit /b %errorlevel%
