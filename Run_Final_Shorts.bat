@echo off
setlocal
cd /d "%~dp0"

rem The isolated Pillow wheel must be on Python's path before Streamlit imports PIL.
if exist ".deps\raqm_pillow\python_executable.txt" (
    set /p "FACTORY_PYTHON=" < ".deps\raqm_pillow\python_executable.txt"
)

if defined FACTORY_PYTHON (
    set "PYTHONPATH=%CD%\.deps\raqm_pillow;%PYTHONPATH%"
    "%FACTORY_PYTHON%" -m streamlit run app.py
) else (
    streamlit run app.py
)

if errorlevel 1 pause
