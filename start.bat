@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -m venv .venv
    if errorlevel 1 goto fail
)
call .venv\Scripts\activate.bat
python -m pip install -r requirements/dev.txt
if errorlevel 1 goto fail
python setup_local.py
if errorlevel 1 goto fail
set "BLOG_NEEDS_SEED="
if not exist db.sqlite3 set "BLOG_NEEDS_SEED=1"
python manage.py migrate
if errorlevel 1 goto fail
if defined BLOG_NEEDS_SEED (
    python manage.py seed
    if errorlevel 1 goto fail
)
echo.
echo Create an administrator if this is your first run.
echo If you already have one, answer N.
choice /C YN /M "Create administrator?"
if errorlevel 2 goto server
python manage.py createsuperuser
if errorlevel 1 goto fail
:server
echo Open http://127.0.0.1:8000/admin/
python manage.py runserver
pause
exit /b
:fail
echo Setup failed. Copy the error above and send it for help.
pause
exit /b 1
