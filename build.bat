@echo off
rem Builds dist\AgesenCamView\AgesenCamView.exe. Requires: pip install -r requirements.txt
cd /d "%~dp0"
python -m PyInstaller --noconfirm --clean --windowed --name AgesenCamView ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.QtWebEngineWidgets ^
  --exclude-module PySide6.Qt3DCore --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml ^
  --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf --exclude-module tkinter ^
  --exclude-module numpy --exclude-module PIL --exclude-module yaml --exclude-module cryptography ^
  run.py
if errorlevel 1 exit /b 1
echo.
echo Done: dist\AgesenCamView\AgesenCamView.exe
