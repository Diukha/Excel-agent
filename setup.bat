@echo off

if exist venv\Scripts\activate.bat (
    echo Existing venv found.
) else (
    echo Creating venv...
    python -m venv venv
)

call venv\Scripts\activate

echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo Done.
pause