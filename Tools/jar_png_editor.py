"""
JAR PNG Editor
==============
Analisa arquivos .jar para encontrar PNGs embutidas em arquivos binários,
permite visualizá-las e substituí-las por versões modificadas.

Inspirado no SJboy Halo.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import io
import os
import threading
from pathlib import Path
from PIL import Image, ImageTk

# Lógica de scan/replace separada no módulo core
from core import PngEntry, JarAnalysis, analyze_jar, apply_replacements

# ─────────────────────────────────────────────
#  CONSTANTES
# ─────────────────────────────────────────────
APP_TITLE = "JAR PNG Editor"
APP_VERSION = "1.0"
THEME_BG      = "#0e0e14"
THEME_PANEL   = "#16161f"
THEME_CARD    = "#1c1c28"
THEME_BORDER  = "#2a2a3a"
THEME_ACCENT  = "#7c5cfc"
THEME_ACCENT2 = "#fc5c7c"
THEME_TEXT    = "#e8e8f0"
THEME_MUTED   = "#6a6a80"
THEME_SUCCESS = "#5cfca0"
THEME_WARN    = "#fccc5c"


# ─────────────────────────────────────────────
#  INTERFACE GRÁFICA
# ─────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1200x760")
        self.minsize(900, 600)
        self.configure(bg=THEME_BG)

        self.analysis: JarAnalysis | None = None
        self.selected_entry: PngEntry | None = None
        self._tk_images: dict[str, ImageTk.PhotoImage] = {}

        self._setup_styles()
        self._build_ui()

    # ── Estilos ──────────────────────────────
    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=THEME_BG)
        style.configure("Card.TFrame", background=THEME_CARD)
        style.configure("Panel.TFrame", background=THEME_PANEL)

        style.configure("TLabel",
            background=THEME_BG, foreground=THEME_TEXT,
            font=("Segoe UI", 10))
        style.configure("Title.TLabel",
            background=THEME_BG, foreground=THEME_TEXT,
            font=("Segoe UI", 18, "bold"))
        style.configure("Sub.TLabel",
            background=THEME_BG, foreground=THEME_MUTED,
            font=("Segoe UI", 9))
        style.configure("Card.TLabel",
            background=THEME_CARD, foreground=THEME_TEXT,
            font=("Segoe UI", 10))
        style.configure("CardMuted.TLabel",
            background=THEME_CARD, foreground=THEME_MUTED,
            font=("Segoe UI", 9))
        style.configure("Accent.TLabel",
            background=THEME_BG, foreground=THEME_ACCENT,
            font=("Segoe UI", 10, "bold"))
        style.configure("Success.TLabel",
            background=THEME_CARD, foreground=THEME_SUCCESS,
            font=("Segoe UI", 9, "bold"))
        style.configure("Warn.TLabel",
            background=THEME_CARD, foreground=THEME_WARN,
            font=("Segoe UI", 9, "bold"))

        style.configure("TButton",
            background=THEME_CARD, foreground=THEME_TEXT,
            font=("Segoe UI", 9), relief="flat",
            borderwidth=0, padding=(12, 7))
        style.map("TButton",
            background=[("active", THEME_BORDER)],
            foreground=[("active", THEME_TEXT)])

        style.configure("Accent.TButton",
            background=THEME_ACCENT, foreground="white",
            font=("Segoe UI", 10, "bold"), padding=(14, 8))
        style.map("Accent.TButton",
            background=[("active", "#6a4ae8")])

        style.configure("Danger.TButton",
            background=THEME_ACCENT2, foreground="white",
            font=("Segoe UI", 9, "bold"), padding=(12, 7))
        style.map("Danger.TButton",
            background=[("active", "#e84a6a")])

        style.configure("Treeview",
            background=THEME_CARD, foreground=THEME_TEXT,
            fieldbackground=THEME_CARD,
            font=("Segoe UI", 9), rowheight=28,
            borderwidth=0, relief="flat")
        style.configure("Treeview.Heading",
            background=THEME_PANEL, foreground=THEME_MUTED,
            font=("Segoe UI", 9, "bold"), relief="flat")
        style.map("Treeview",
            background=[("selected", THEME_ACCENT)],
            foreground=[("selected", "white")])

        style.configure("TProgressbar",
            troughcolor=THEME_PANEL,
            background=THEME_ACCENT,
            borderwidth=0, thickness=4)

        style.configure("TSeparator", background=THEME_BORDER)

    # ── Layout Principal ──────────────────────
    def _build_ui(self):
        # Barra superior
        top = tk.Frame(self, bg=THEME_PANEL, height=56)
        top.pack(fill="x", side="top")
        top.pack_propagate(False)

        tk.Label(top, text="⬡", bg=THEME_PANEL, fg=THEME_ACCENT,
                 font=("Segoe UI", 22, "bold")).pack(side="left", padx=(18, 6), pady=12)
        tk.Label(top, text="JAR PNG Editor", bg=THEME_PANEL, fg=THEME_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", pady=12)
        tk.Label(top, text=f"v{APP_VERSION}", bg=THEME_PANEL, fg=THEME_MUTED,
                 font=("Segoe UI", 9)).pack(side="left", padx=(4, 0), pady=18)

        self._jar_label = tk.Label(top, text="Nenhum JAR aberto",
                                   bg=THEME_PANEL, fg=THEME_MUTED,
                                   font=("Segoe UI", 9))
        self._jar_label.pack(side="right", padx=18)

        # Progress bar (escondida)
        self._pbar = ttk.Progressbar(self, mode="determinate",
                                     style="TProgressbar")

        # Corpo principal
        body = tk.Frame(self, bg=THEME_BG)
        body.pack(fill="both", expand=True)

        # ── Painel esquerdo (lista de PNGs) ───
        left = tk.Frame(body, bg=THEME_PANEL, width=380)
        left.pack(fill="y", side="left")
        left.pack_propagate(False)

        # Toolbar de ações do JAR
        toolbar = tk.Frame(left, bg=THEME_PANEL)
        toolbar.pack(fill="x", padx=12, pady=(14, 6))

        self._btn_open = tk.Button(toolbar, text="📂  Abrir JAR",
            bg=THEME_ACCENT, fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=7,
            cursor="hand2", command=self._open_jar)
        self._btn_open.pack(side="left")

        self._btn_save = tk.Button(toolbar, text="💾  Salvar JAR",
            bg=THEME_CARD, fg=THEME_TEXT, relief="flat",
            font=("Segoe UI", 9), padx=12, pady=7,
            cursor="hand2", state="disabled", command=self._save_jar)
        self._btn_save.pack(side="left", padx=(8, 0))

        # Stats bar
        self._stats_label = tk.Label(left, text="",
            bg=THEME_PANEL, fg=THEME_MUTED, font=("Segoe UI", 8))
        self._stats_label.pack(fill="x", padx=14)

        # Separador
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=6)

        # Filtro
        filt_frame = tk.Frame(left, bg=THEME_PANEL)
        filt_frame.pack(fill="x", padx=12, pady=(0, 6))
        tk.Label(filt_frame, text="🔍", bg=THEME_PANEL, fg=THEME_MUTED,
                 font=("Segoe UI", 10)).pack(side="left")
        self._filter_var = tk.StringVar()
        self._filter_var.trace_add("write", lambda *_: self._apply_filter())
        filter_entry = tk.Entry(filt_frame, textvariable=self._filter_var,
            bg=THEME_CARD, fg=THEME_TEXT, insertbackground=THEME_TEXT,
            relief="flat", font=("Segoe UI", 9), bd=0)
        filter_entry.pack(side="left", fill="x", expand=True, padx=6, ipady=5)

        # Tree
        tree_frame = tk.Frame(left, bg=THEME_PANEL)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        cols = ("arquivo", "offset", "tamanho", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings",
                                  selectmode="browse")
        self._tree.heading("arquivo", text="Arquivo / Entrada")
        self._tree.heading("offset",  text="Offset")
        self._tree.heading("tamanho", text="Tamanho")
        self._tree.heading("status",  text="Status")

        self._tree.column("arquivo", width=180, minwidth=100)
        self._tree.column("offset",  width=70,  minwidth=60)
        self._tree.column("tamanho", width=70,  minwidth=60)
        self._tree.column("status",  width=70,  minwidth=60)

        sb = ttk.Scrollbar(tree_frame, orient="vertical",
                           command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.tag_configure("replaced", foreground=THEME_SUCCESS)
        self._tree.tag_configure("pending",  foreground=THEME_TEXT)

        # ── Painel direito (detalhes e ações) ─
        right = tk.Frame(body, bg=THEME_BG)
        right.pack(fill="both", expand=True, side="left")

        # Preview área
        preview_outer = tk.Frame(right, bg=THEME_BG)
        preview_outer.pack(fill="both", expand=True, padx=16, pady=16)

        # Topo do painel direito
        right_header = tk.Frame(preview_outer, bg=THEME_BG)
        right_header.pack(fill="x", pady=(0, 12))

        tk.Label(right_header, text="Visualizador de PNG",
            bg=THEME_BG, fg=THEME_TEXT,
            font=("Segoe UI", 12, "bold")).pack(side="left")

        self._entry_info = tk.Label(right_header, text="",
            bg=THEME_BG, fg=THEME_MUTED, font=("Segoe UI", 9))
        self._entry_info.pack(side="right")

        # Cards de preview (original | novo)
        preview_row = tk.Frame(preview_outer, bg=THEME_BG)
        preview_row.pack(fill="both", expand=True)

        # Original
        orig_card = tk.Frame(preview_row, bg=THEME_CARD,
                             highlightbackground=THEME_BORDER,
                             highlightthickness=1)
        orig_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(orig_card, text="ORIGINAL", bg=THEME_CARD, fg=THEME_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(pady=(10, 0))

        self._orig_canvas = tk.Canvas(orig_card, bg=THEME_CARD,
                                      highlightthickness=0)
        self._orig_canvas.pack(fill="both", expand=True, padx=12, pady=12)

        self._orig_info = tk.Label(orig_card, text="",
            bg=THEME_CARD, fg=THEME_MUTED, font=("Segoe UI", 8))
        self._orig_info.pack(pady=(0, 8))

        # Novo
        new_card = tk.Frame(preview_row, bg=THEME_CARD,
                            highlightbackground=THEME_BORDER,
                            highlightthickness=1)
        new_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        tk.Label(new_card, text="SUBSTITUIÇÃO", bg=THEME_CARD, fg=THEME_MUTED,
                 font=("Segoe UI", 8, "bold")).pack(pady=(10, 0))

        self._new_canvas = tk.Canvas(new_card, bg=THEME_CARD,
                                     highlightthickness=0)
        self._new_canvas.pack(fill="both", expand=True, padx=12, pady=12)

        self._new_info = tk.Label(new_card, text="",
            bg=THEME_CARD, fg=THEME_MUTED, font=("Segoe UI", 8))
        self._new_info.pack(pady=(0, 8))

        # Painel de ações (abaixo dos previews)
        action_panel = tk.Frame(preview_outer, bg=THEME_BG)
        action_panel.pack(fill="x", pady=(12, 0))

        self._btn_import = tk.Button(action_panel, text="📥  Importar PNG",
            bg=THEME_ACCENT, fg="white", relief="flat",
            font=("Segoe UI", 9, "bold"), padx=14, pady=8,
            cursor="hand2", state="disabled", command=self._import_png)
        self._btn_import.pack(side="left")

        self._btn_export = tk.Button(action_panel, text="📤  Exportar Original",
            bg=THEME_CARD, fg=THEME_TEXT, relief="flat",
            font=("Segoe UI", 9), padx=14, pady=8,
            cursor="hand2", state="disabled", command=self._export_png)
        self._btn_export.pack(side="left", padx=(8, 0))

        self._btn_clear = tk.Button(action_panel, text="✖  Cancelar Substituição",
            bg=THEME_CARD, fg=THEME_ACCENT2, relief="flat",
            font=("Segoe UI", 9), padx=14, pady=8,
            cursor="hand2", state="disabled", command=self._clear_replacement)
        self._btn_clear.pack(side="left", padx=(8, 0))

        # Export all
        self._btn_export_all = tk.Button(action_panel, text="📦  Exportar Todas",
            bg=THEME_CARD, fg=THEME_TEXT, relief="flat",
            font=("Segoe UI", 9), padx=14, pady=8,
            cursor="hand2", state="disabled", command=self._export_all)
        self._btn_export_all.pack(side="right")

        # Status bar
        self._status_bar = tk.Label(self, text="Pronto.",
            bg=THEME_PANEL, fg=THEME_MUTED, font=("Segoe UI", 8),
            anchor="w", padx=12)
        self._status_bar.pack(fill="x", side="bottom")

    # ── Ações Principais ─────────────────────
    def _open_jar(self):
        path = filedialog.askopenfilename(
            title="Abrir arquivo JAR",
            filetypes=[("Arquivos JAR", "*.jar"), ("Todos", "*.*")])
        if not path:
            return

        self._jar_label.config(text=os.path.basename(path))
        self._start_scan(path)

    def _start_scan(self, jar_path: str):
        self._tree.delete(*self._tree.get_children())
        self._clear_preview()
        self._set_status(f"Analisando {os.path.basename(jar_path)}...")
        self._pbar.pack(fill="x")
        self._pbar["value"] = 0
        self._btn_open.config(state="disabled")

        def run():
            def progress(i, total, name):
                pct = (i / total) * 100 if total else 0
                self.after(0, lambda: self._pbar.configure(value=pct))
                self.after(0, lambda: self._set_status(
                    f"Varrendo [{i}/{total}]: {name}"))

            analysis = analyze_jar(jar_path, progress_cb=progress)
            self.after(0, lambda: self._on_scan_done(analysis))

        threading.Thread(target=run, daemon=True).start()

    def _on_scan_done(self, analysis: JarAnalysis):
        self._pbar.pack_forget()
        self._btn_open.config(state="normal")

        if analysis.error:
            messagebox.showerror("Erro", f"Falha ao abrir JAR:\n{analysis.error}")
            return

        self.analysis = analysis
        self._populate_tree(analysis.entries)

        n = len(analysis.entries)
        self._stats_label.config(
            text=f"{n} PNG(s) encontrada(s) em {analysis.scanned_files} arquivo(s)")
        self._set_status(
            f"Concluído. {n} PNG(s) encontrada(s).")

        if n > 0:
            self._btn_save.config(state="normal")
            self._btn_export_all.config(state="normal")
        else:
            messagebox.showinfo("Resultado",
                "Nenhuma PNG encontrada nos arquivos deste JAR.")

    def _populate_tree(self, entries: list[PngEntry], filter_text: str = ""):
        self._tree.delete(*self._tree.get_children())
        ft = filter_text.lower()
        for e in entries:
            if ft and ft not in e.jar_entry.lower():
                continue
            short_name = os.path.basename(e.jar_entry) or e.jar_entry
            tag = "replaced" if e.replaced or e.replacement else "pending"
            status = "✔ Trocada" if (e.replaced or e.replacement) else "original"
            self._tree.insert("", "end",
                iid=e.uid,
                values=(short_name, f"0x{e.offset:X}",
                        f"{e.bytes_len//1024 or 1}KB", status),
                tags=(tag,))

    def _apply_filter(self):
        if not self.analysis:
            return
        self._populate_tree(self.analysis.entries, self._filter_var.get())

    def _on_select(self, _event=None):
        sel = self._tree.selection()
        if not sel or not self.analysis:
            return
        uid = sel[0]
        entry = next((e for e in self.analysis.entries if e.uid == uid), None)
        if not entry:
            return
        self.selected_entry = entry
        self._show_entry(entry)
        self._btn_import.config(state="normal")
        self._btn_export.config(state="normal")
        if entry.replacement:
            self._btn_clear.config(state="normal")

    def _show_entry(self, entry: PngEntry):
        # Info no cabeçalho
        self._entry_info.config(
            text=f"{entry.jar_entry}  |  offset 0x{entry.offset:X}  |  {entry.size_str}  |  {entry.mode}")

        # Original
        self._draw_on_canvas(self._orig_canvas, entry.image,
                             f"{entry.size_str} {entry.mode} — {entry.bytes_len} bytes",
                             self._orig_info)

        # Substituição
        if entry.replacement:
            try:
                rep_img = Image.open(io.BytesIO(entry.replacement))
                self._draw_on_canvas(self._new_canvas, rep_img,
                                     f"{rep_img.size[0]}×{rep_img.size[1]} {rep_img.mode} "
                                     f"— {len(entry.replacement)} bytes",
                                     self._new_info)
            except Exception:
                self._clear_canvas(self._new_canvas)
                self._new_info.config(text="Erro ao carregar substituição")
        else:
            self._clear_canvas(self._new_canvas)
            self._new_info.config(text="Nenhuma substituição definida")

    def _draw_on_canvas(self, canvas: tk.Canvas, img: Image.Image,
                        info_text: str, info_label: tk.Label):
        canvas.update_idletasks()
        cw = canvas.winfo_width()  or 300
        ch = canvas.winfo_height() or 300

        # Fundo xadrez para transparência
        checker = self._make_checker(cw, ch)

        # Escala a imagem preservando aspect ratio
        img_rgba = img.convert("RGBA")
        scale = min((cw - 20) / img_rgba.width, (ch - 20) / img_rgba.height, 4.0)
        nw = max(1, int(img_rgba.width  * scale))
        nh = max(1, int(img_rgba.height * scale))
        img_scaled = img_rgba.resize((nw, nh), Image.NEAREST if scale >= 2 else Image.LANCZOS)

        # Compõe sobre o xadrez
        x_off = (cw - nw) // 2
        y_off = (ch - nh) // 2
        checker.paste(img_scaled, (x_off, y_off), img_scaled)

        tk_img = ImageTk.PhotoImage(checker)
        uid = id(canvas)
        self._tk_images[uid] = tk_img

        canvas.delete("all")
        canvas.create_image(0, 0, anchor="nw", image=tk_img)
        info_label.config(text=info_text)

    def _make_checker(self, w: int, h: int, cell: int = 8) -> Image.Image:
        img = Image.new("RGB", (w, h))
        c1, c2 = (180, 180, 190), (220, 220, 230)
        pix = img.load()
        for y in range(h):
            for x in range(w):
                pix[x, y] = c1 if ((x // cell) + (y // cell)) % 2 == 0 else c2
        return img

    def _clear_canvas(self, canvas: tk.Canvas):
        canvas.delete("all")

    def _clear_preview(self):
        self._orig_canvas.delete("all")
        self._new_canvas.delete("all")
        self._orig_info.config(text="")
        self._new_info.config(text="")
        self._entry_info.config(text="")
        self.selected_entry = None
        self._btn_import.config(state="disabled")
        self._btn_export.config(state="disabled")
        self._btn_clear.config(state="disabled")

    # ── Importar PNG de substituição ─────────
    def _import_png(self):
        if not self.selected_entry:
            return
        path = filedialog.askopenfilename(
            title="Selecionar PNG substituta",
            filetypes=[("PNG", "*.png"), ("Todos", "*.*")])
        if not path:
            return

        try:
            with open(path, "rb") as f:
                raw = f.read()
            # Valida que é uma PNG válida
            img = Image.open(io.BytesIO(raw))
            img.load()
        except Exception as e:
            messagebox.showerror("Erro", f"Arquivo inválido:\n{e}")
            return

        entry = self.selected_entry
        entry.replacement = raw
        entry.replaced    = False  # será marcado ao salvar

        # Atualiza tree
        short = os.path.basename(entry.jar_entry) or entry.jar_entry
        self._tree.item(entry.uid, values=(
            short, f"0x{entry.offset:X}",
            f"{entry.bytes_len//1024 or 1}KB", "⏳ Pendente"),
            tags=("replaced",))

        self._show_entry(entry)
        self._btn_clear.config(state="normal")
        self._set_status(f"PNG substituta carregada para {entry.jar_entry}")

    # ── Exportar PNG original ─────────────────
    def _export_png(self):
        if not self.selected_entry:
            return
        entry = self.selected_entry
        default_name = f"png_{entry.offset:08X}.png"
        path = filedialog.asksaveasfilename(
            title="Salvar PNG original",
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG", "*.png")])
        if not path:
            return
        try:
            with open(path, "wb") as f:
                f.write(entry.original_data)
            self._set_status(f"PNG exportada: {path}")
        except Exception as e:
            messagebox.showerror("Erro", str(e))

    # ── Exportar todas as PNGs ────────────────
    def _export_all(self):
        if not self.analysis or not self.analysis.entries:
            return
        folder = filedialog.askdirectory(title="Selecionar pasta de destino")
        if not folder:
            return

        jar_name = Path(self.analysis.jar_path).stem
        exported = 0
        for entry in self.analysis.entries:
            safe_jar_entry = entry.jar_entry.replace("/", "_").replace("\\", "_")
            fname = f"{jar_name}__{safe_jar_entry}__0x{entry.offset:X}.png"
            out_path = os.path.join(folder, fname)
            try:
                with open(out_path, "wb") as f:
                    f.write(entry.original_data)
                exported += 1
            except Exception:
                pass

        messagebox.showinfo("Exportação Concluída",
            f"{exported} PNG(s) exportada(s) para:\n{folder}")
        self._set_status(f"{exported} PNGs exportadas.")

    # ── Cancelar substituição ─────────────────
    def _clear_replacement(self):
        if not self.selected_entry:
            return
        entry = self.selected_entry
        entry.replacement = None
        entry.replaced    = False

        short = os.path.basename(entry.jar_entry) or entry.jar_entry
        self._tree.item(entry.uid, values=(
            short, f"0x{entry.offset:X}",
            f"{entry.bytes_len//1024 or 1}KB", "original"),
            tags=("pending",))

        self._show_entry(entry)
        self._btn_clear.config(state="disabled")
        self._set_status("Substituição cancelada.")

    # ── Salvar JAR ────────────────────────────
    def _save_jar(self):
        if not self.analysis:
            return

        pending = [e for e in self.analysis.entries if e.replacement]
        if not pending:
            messagebox.showinfo("Aviso",
                "Nenhuma substituição pendente.\nImporte ao menos uma PNG antes de salvar.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Salvar JAR modificado",
            initialfile=Path(self.analysis.jar_path).stem + "_modified.jar",
            defaultextension=".jar",
            filetypes=[("JAR", "*.jar"), ("Todos", "*.*")])
        if not out_path:
            return

        self._set_status("Gravando JAR...")
        self._btn_save.config(state="disabled")

        def run():
            stats = apply_replacements(self.analysis, out_path)
            self.after(0, lambda: self._on_save_done(stats, out_path))

        threading.Thread(target=run, daemon=True).start()

    def _on_save_done(self, stats: dict, out_path: str):
        self._btn_save.config(state="normal")

        if stats["errors"]:
            messagebox.showerror("Erro ao Salvar",
                "\n".join(stats["errors"]))
            return

        # Marca entradas como salvas
        for entry in self.analysis.entries:
            if entry.replacement:
                entry.replaced    = True
                entry.replacement = None
                short = os.path.basename(entry.jar_entry) or entry.jar_entry
                self._tree.item(entry.uid, values=(
                    short, f"0x{entry.offset:X}",
                    f"{entry.bytes_len//1024 or 1}KB", "✔ Trocada"),
                    tags=("replaced",))

        msg = (f"JAR salvo com sucesso!\n\n"
               f"• {stats['replaced']} PNG(s) substituída(s)\n"
               f"• Arquivo: {out_path}")
        messagebox.showinfo("Salvo!", msg)
        self._set_status(f"JAR salvo: {out_path}")

    # ── Utilitários ───────────────────────────
    def _set_status(self, msg: str):
        self._status_bar.config(text=msg)


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()
