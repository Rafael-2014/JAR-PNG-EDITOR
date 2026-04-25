@echo off
echo JAR PNG Editor - Iniciando...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale Python 3.10+ em https://python.org
    pause
    exit /b 1
)
python -c "from PIL import Image" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencia Pillow...
    pip install Pillow
)
python jar_png_editor.py
