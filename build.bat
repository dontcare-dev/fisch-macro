@echo off
setlocal
cd /d "%~dp0"
py -3.11 -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean --onefile --windowed --name "Fish Macro" --collect-all cv2 --collect-all PySide6 main.py
echo.
echo Build complete. Executable: dist\Fish Macro.exe
pause
