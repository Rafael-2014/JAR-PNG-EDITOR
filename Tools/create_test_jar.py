"""Cria um JAR de teste com PNGs embutidas em arquivos binários."""
import zipfile, io, os
from PIL import Image, ImageDraw, ImageFont

def make_png(color, size=(32,32), text=""):
    img = Image.new("RGBA", size, color)
    if text:
        try:
            d = ImageDraw.Draw(img)
            d.text((2,2), text, fill=(255,255,255,200))
        except: pass
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def create_test_jar(output="test_game.jar"):
    png1 = make_png((220, 60, 80, 255),  (32,32),  "A")
    png2 = make_png((60, 120, 220, 255), (64,64),  "B")
    png3 = make_png((60, 200, 80, 255),  (16,16),  "C")
    png4 = make_png((200, 160, 40, 255), (128,128),"D")
    png5 = make_png((140, 60, 200, 255), (48,48),  "E")

    # Arquivo binário com 2 PNGs embutidas (com lixo antes/depois)
    bin1 = b'\x00\x01\x02JAR_BIN_HEADER\xFF' + png1 + b'\xAA\xBB' + png2 + b'\xCC\xDD\xEE'
    # Outro binário com 1 PNG
    bin2 = b'\x4A\x4D\x45\x00\x00' + b'\x00'*20 + png3 + b'\xFF'*10
    # Arquivo .res com PNG grande
    bin3 = b'RES\x00\x01' + b'\x00'*50 + png4 + b'\x00'*5 + png5 + b'\x00'*8
    # PNG direta (arquivo .png comum)
    png_direct = make_png((80,80,80,255), (24,24), "F")

    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nMain-Class: com.game.Main\n")
        zf.writestr("res/sprites.bin",    bin1)
        zf.writestr("res/tilemap.bin",    bin2)
        zf.writestr("res/ui.res",         bin3)
        zf.writestr("res/icon.png",       png_direct)
        zf.writestr("com/game/Main.class",b'\xCA\xFE\xBA\xBE' + b'\x00'*200)
        zf.writestr("com/game/Engine.class",b'\xCA\xFE\xBA\xBE' + b'\x00'*150)

    print(f"JAR de teste criado: {output}")
    print(f"  PNGs embutidas: 5 em binários + 1 direta = 6 total")
    print(f"  Arquivos: sprites.bin(2), tilemap.bin(1), ui.res(2), icon.png(1)")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    create_test_jar()
