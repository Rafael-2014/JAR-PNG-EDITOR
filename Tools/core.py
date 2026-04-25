"""
Módulo de lógica pura (sem GUI) — pode ser importado e testado independentemente.
"""
import zipfile, io, shutil, os, struct
from PIL import Image, ImageFile

# Aceita PNGs truncadas (sem IEND ou com dados incompletos)
ImageFile.LOAD_TRUNCATED_IMAGES = True

PNG_SIG = b'\x89PNG\r\n\x1a\n'


class PngEntry:
    def __init__(self, jar_entry, offset, end, original_data, image):
        self.jar_entry     = jar_entry
        self.offset        = offset
        self.end           = end
        self.original_data = original_data
        self.image         = image
        self.replacement   = None
        self.replaced      = False

    @property
    def uid(self):
        return f"{self.jar_entry}@{self.offset}"

    @property
    def size_str(self):
        return f"{self.image.size[0]}×{self.image.size[1]}"

    @property
    def bytes_len(self):
        return len(self.original_data)


class JarAnalysis:
    def __init__(self, jar_path):
        self.jar_path      = jar_path
        self.entries       = []
        self.scanned_files = 0
        self.total_files   = 0
        self.error         = None


def _read_png_chunks(data: bytes, start: int):
    """
    Lê os chunks PNG sequencialmente a partir de 'start'.
    Retorna (end, width, height) ou None se estrutura for completamente inválida.
    Aceita PNGs sem IEND (truncadas) se ao menos o IHDR for válido.
    """
    pos = start + 8  # pula assinatura de 8 bytes
    width = height = 0
    found_ihdr = False

    for _ in range(2048):
        if pos + 8 > len(data):
            # Dados acabaram sem IEND — aceita se tiver IHDR válido
            if found_ihdr:
                return pos, width, height
            return None

        try:
            length = struct.unpack('>I', data[pos:pos+4])[0]
        except Exception:
            return None

        # Tamanho de chunk absurdo = lixo
        if length > 0x7FFFFFFF:
            if found_ihdr:
                return pos, width, height
            return None

        chunk_type = data[pos+4:pos+8]

        # Tipo do chunk deve ser letras ASCII
        try:
            ct = chunk_type.decode('ascii')
            if not all(c.isalpha() for c in ct):
                if found_ihdr:
                    return pos, width, height
                return None
        except Exception:
            if found_ihdr:
                return pos, width, height
            return None

        chunk_end = pos + 4 + 4 + length + 4  # len + type + data + crc

        # Lê dimensões do IHDR
        if chunk_type == b'IHDR':
            if length >= 8 and pos + 8 + length <= len(data):
                try:
                    width  = struct.unpack('>I', data[pos+8 :pos+12])[0]
                    height = struct.unpack('>I', data[pos+12:pos+16])[0]
                    found_ihdr = True
                except Exception:
                    return None
            else:
                return None

        # IEND = fim oficial da PNG
        if chunk_type == b'IEND':
            return min(chunk_end, len(data)), width, height

        # Chunk ultrapassa os dados — aceita o que temos
        if chunk_end > len(data):
            if found_ihdr:
                return len(data), width, height
            return None

        pos = chunk_end

    # Muitos chunks — retorna o que tiver
    if found_ihdr:
        return pos, width, height
    return None


def find_pngs_in_bytes(data: bytes, jar_entry: str) -> list:
    """
    Scan agressivo: encontra TODAS as PNGs embutidas em 'data'.
    - Aceita PNGs sem IEND (truncadas)
    - Aceita PNGs com CRC incorreto
    - Usa dimensões do IHDR como fallback quando Pillow falha
    - Não pula PNGs consecutivas sem espaço entre elas
    """
    results = []
    pos = 0
    data_len = len(data)

    while pos < data_len:
        idx = data.find(PNG_SIG, pos)
        if idx == -1:
            break

        parsed = _read_png_chunks(data, idx)

        if parsed:
            end, w, h = parsed
            end = min(end, data_len)
            png_bytes = data[idx:end]

            # Tenta abrir com Pillow — modo tolerante
            img = None
            for attempt_data in [png_bytes, data[idx:]]:
                try:
                    buf = io.BytesIO(attempt_data)
                    candidate = Image.open(buf)
                    candidate.load()
                    if candidate.size[0] > 0 and candidate.size[1] > 0:
                        img = candidate.copy()
                        break
                except Exception:
                    pass

            # Pillow falhou mas IHDR tem dimensões válidas → placeholder cinza
            if img is None and w > 0 and h > 0:
                try:
                    img = Image.new("RGBA", (w, h), (100, 100, 100, 255))
                except Exception:
                    pass

            if img and img.size[0] > 0 and img.size[1] > 0:
                entry = PngEntry(jar_entry, idx, end, png_bytes, img)
                results.append(entry)
                pos = end  # avança para depois desta PNG
            else:
                pos = idx + 1
        else:
            pos = idx + 1

    return results


def analyze_jar(jar_path: str, progress_cb=None) -> JarAnalysis:
    """Abre o JAR e varre todos os arquivos em busca de PNGs."""
    analysis = JarAnalysis(jar_path)
    try:
        with zipfile.ZipFile(jar_path, 'r') as zf:
            names = zf.namelist()
            analysis.total_files = len(names)
            for i, name in enumerate(names):
                if progress_cb:
                    progress_cb(i, len(names), name)
                try:
                    data = zf.read(name)
                except Exception:
                    analysis.scanned_files += 1
                    continue
                found = find_pngs_in_bytes(data, name)
                analysis.entries.extend(found)
                analysis.scanned_files += 1
    except Exception as e:
        analysis.error = str(e)
    return analysis


def apply_replacements(analysis: JarAnalysis, output_path: str) -> dict:
    """Grava novo JAR com as PNGs substituídas."""
    stats = {"replaced": 0, "skipped": 0, "errors": []}
    replacements_by_entry = {}
    for e in analysis.entries:
        if e.replacement is not None:
            replacements_by_entry.setdefault(e.jar_entry, []).append(e)

    if not replacements_by_entry:
        stats["skipped"] = len(analysis.entries)
        shutil.copy2(analysis.jar_path, output_path)
        return stats

    try:
        with zipfile.ZipFile(analysis.jar_path, 'r') as zf_in, \
             zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf_out:
            for info in zf_in.infolist():
                data = zf_in.read(info.filename)
                if info.filename in replacements_by_entry:
                    # Ordena por offset decrescente para não deslocar offsets
                    entries = sorted(replacements_by_entry[info.filename],
                                     key=lambda e: e.offset, reverse=True)
                    new_data = bytearray(data)
                    for entry in entries:
                        del new_data[entry.offset:entry.end]
                        new_data[entry.offset:entry.offset] = entry.replacement
                        stats["replaced"] += 1
                    zf_out.writestr(info, bytes(new_data))
                else:
                    zf_out.writestr(info, data)
    except Exception as e:
        stats["errors"].append(str(e))
    return stats
