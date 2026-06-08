@echo off
echo Creating venv...
python -m venv venv

call venv\Scripts\activate

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo Done.
pause