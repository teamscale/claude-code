@echo off
setlocal

rem Windows counterpart of the extensionless `ts-agent-helper` launcher.
rem Windows has no shebang support and resolves a bare command name through
rem PATHEXT, which contains .CMD by default, so `ts-agent-helper` in a skill
rem instruction finds this file. Keep it in sync with the bash launcher next
rem to it; see ../../../CLAUDE.md for the convention.
rem
rem This launcher stays thin: it locates an interpreter, sets PYTHONPATH and
rem hands off to the Python package. Every line of logic here has to exist
rem twice, once in batch and once in the bash launcher, and the two dialects
rem differ enough that the copies drift apart. Put new logic in
rem scripts\ts_agent_helper\ instead.

set "SCRIPTS_DIR=%~dp0..\scripts"
if defined PYTHONPATH (
    set "PYTHONPATH=%SCRIPTS_DIR%;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%SCRIPTS_DIR%"
)

rem `py` is the python.org launcher and selects the newest installed Python 3
rem itself, so it is preferred over whichever `python` happens to come first
rem on PATH. The minimum version is enforced inside the package, in
rem scripts\ts_agent_helper\__init__.py.
where /q py.exe && goto :run_py
where /q python.exe && goto :run_python

echo Error: neither 'py' nor 'python' found in PATH>&2
exit /b 1

rem `exit /b %ERRORLEVEL%` is read after the command above has run, because
rem each top-level line is parsed separately. The skills stop and surface
rem stderr on a non-zero exit, so the status must not be swallowed here.
:run_py
py -3 -m ts_agent_helper %*
exit /b %ERRORLEVEL%

:run_python
python -m ts_agent_helper %*
exit /b %ERRORLEVEL%
