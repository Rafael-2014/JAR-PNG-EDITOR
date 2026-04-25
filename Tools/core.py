"""
Módulo de lógica pura (sem GUI) — pode ser importado e testado independentemente.
"""
import zipfile, io, shutil, os
from PIL import Image

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


def find_pngs_in_bytes(data: bytes, jar_entry: str) -> list:
    results = []
    pos = 0
    while True:
        idx = data.find(PNG_SIG, pos)
        if idx == -1:
            break
        try:
            buf = io.BytesIO(data[idx:])
            img = Image.open(buf)
            img.load()
            iend_idx = data.find(b'IEND', idx)
            if iend_idx == -1:
                pos = idx + 1
                continue
            end = iend_idx + 12
            png_bytes = data[idx:end]
            entry = PngEntry(jar_entry, idx, end, png_bytes, img.copy())
            results.append(entry)
            pos = end
        except Exception:
            pos = idx + 1
    return results


def analyze_jar(jar_path: str, progress_cb=None) -> JarAnalysis:
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
                    entries = sorted(replacements_by_entry[info.filename],
                                     key=lambda e: e.offset, reverse=True)
                    new_data = bytearray(data)
                    for entry in entries:
                        new_png = entry.replacement
                        del new_data[entry.offset:entry.end]
                        new_data[entry.offset:entry.offset] = new_png
                        stats["replaced"] += 1
                    zf_out.writestr(info, bytes(new_data))
                else:
                    zf_out.writestr(info, data)
    except Exception as e:
        stats["errors"].append(str(e))
    return stats
