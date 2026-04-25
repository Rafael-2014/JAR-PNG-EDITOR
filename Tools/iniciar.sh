#!/bin/bash
echo "JAR PNG Editor - Iniciando..."
if ! command -v python3 &> /dev/null; then
    echo "ERRO: Python3 não encontrado."
    exit 1
fi
python3 -c "from PIL import Image" 2>/dev/null || pip install Pillow --break-system-packages
python3 jar_png_editor.py
