"""
JAR PNG Editor - Versão Web (Flask)
====================================
Roda no Termux. Acesse pelo navegador do Android em:
http://localhost:5000
"""

import os, io, base64, json, tempfile, shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_file, render_template_string
from core import analyze_jar, apply_replacements, JarAnalysis
from PIL import Image

app = Flask(__name__)

@app.before_request
def bloquear_acesso_externo():
    ip = request.remote_addr
    if ip not in ("127.0.0.1", "::1"):
        return "Acesso negado.", 403

# ── Estado em memória ──────────────────────────────────────────────────────────
SESSION = {
    "analysis": None,       # JarAnalysis atual
    "jar_path": None,       # caminho do JAR aberto
    "tmp_files": [],        # temporários para limpar
}

# ── Utilidades ─────────────────────────────────────────────────────────────────
def img_to_b64(img: Image.Image, max_size=200) -> str:
    """Converte PIL Image para base64 PNG, redimensionando para preview."""
    try:
        img = img.convert("RGBA")
        w, h = img.size
        if w <= 0 or h <= 0:
            return ""
        scale = min(max_size / w, max_size / h, 1.0)
        if scale < 1.0:
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            img = img.resize((nw, nh), Image.NEAREST)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""

def bytes_to_b64(data: bytes) -> str:
    try:
        buf = io.BytesIO(data)
        img = Image.open(buf)
        return img_to_b64(img)
    except Exception:
        return ""

def entry_to_dict(e) -> dict:
    preview = img_to_b64(e.image)
    return {
        "uid":        e.uid,
        "jar_entry":  e.jar_entry,
        "filename":   os.path.basename(e.jar_entry) or e.jar_entry,
        "offset":     f"0x{e.offset:X}",
        "offset_int": e.offset,
        "size":       e.size_str,
        "mode":       e.image.mode,
        "bytes":      e.bytes_len,
        "replaced":   e.replacement is not None or e.replaced,
        "preview":    preview,
        "rep_preview": bytes_to_b64(e.replacement) if e.replacement else None,
        "invalid":    preview == "",
    }

# ── HTML Principal ─────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>JAR PNG Editor</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
:root {
  --bg:      #080b12;
  --panel:   #0d1117;
  --card:    #111722;
  --border:  #1e2a3a;
  --accent:  #00d4ff;
  --accent2: #ff3d6e;
  --green:   #00ff88;
  --yellow:  #ffd700;
  --text:    #cdd6e8;
  --muted:   #4a5568;
  --font-mono: 'JetBrains Mono', monospace;
  --font-ui:   'Syne', sans-serif;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-ui);
  min-height: 100vh;
  overflow-x: hidden;
}

/* ── Header ── */
header {
  background: var(--panel);
  border-bottom: 1px solid var(--border);
  padding: 14px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  position: sticky;
  top: 0;
  z-index: 100;
}
.logo {
  font-size: 22px;
  font-weight: 800;
  color: var(--accent);
  letter-spacing: -1px;
}
.logo span { color: var(--accent2); }
.jar-name {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--muted);
  margin-left: auto;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Layout ── */
.container { max-width: 900px; margin: 0 auto; padding: 20px 16px; }

/* ── Upload Zone ── */
.upload-zone {
  border: 2px dashed var(--border);
  border-radius: 16px;
  padding: 40px 20px;
  text-align: center;
  cursor: pointer;
  transition: all .2s;
  position: relative;
  background: var(--panel);
}
.upload-zone:hover, .upload-zone.drag { border-color: var(--accent); background: #0d1a2a; }
.upload-zone input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.upload-icon { font-size: 48px; margin-bottom: 12px; }
.upload-zone h2 { font-size: 18px; font-weight: 700; margin-bottom: 6px; }
.upload-zone p { font-size: 13px; color: var(--muted); font-family: var(--font-mono); }

/* ── Progress ── */
.progress-wrap { margin: 20px 0; display: none; }
.progress-label { font-family: var(--font-mono); font-size: 11px; color: var(--muted); margin-bottom: 6px; }
.progress-bar { height: 3px; background: var(--border); border-radius: 99px; overflow: hidden; }
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); width: 0; transition: width .3s; }

/* ── Stats bar ── */
.stats-bar {
  display: none;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 16px;
  margin: 16px 0;
  font-family: var(--font-mono);
  font-size: 12px;
  gap: 20px;
  flex-wrap: wrap;
  align-items: center;
}
.stat { display: flex; align-items: center; gap: 6px; }
.stat-val { color: var(--accent); font-weight: 700; }
.stat-val.green { color: var(--green); }
.stat-val.red { color: var(--accent2); }

/* ── Toolbar ── */
.toolbar {
  display: none;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.btn {
  background: var(--card);
  border: 1px solid var(--border);
  color: var(--text);
  font-family: var(--font-ui);
  font-size: 13px;
  font-weight: 700;
  padding: 9px 16px;
  border-radius: 8px;
  cursor: pointer;
  transition: all .15s;
  white-space: nowrap;
}
.btn:hover { border-color: var(--accent); color: var(--accent); }
.btn.primary { background: var(--accent); color: #000; border-color: var(--accent); }
.btn.primary:hover { background: #00b8e0; }
.btn.danger { border-color: var(--accent2); color: var(--accent2); }
.btn.danger:hover { background: var(--accent2); color: #fff; }
.btn:disabled { opacity: .4; cursor: not-allowed; }

/* ── Filter ── */
.filter-wrap { margin-bottom: 12px; display: none; }
.filter-input {
  width: 100%;
  background: var(--panel);
  border: 1px solid var(--border);
  color: var(--text);
  font-family: var(--font-mono);
  font-size: 13px;
  padding: 10px 14px;
  border-radius: 8px;
  outline: none;
}
.filter-input:focus { border-color: var(--accent); }
.filter-input::placeholder { color: var(--muted); }

/* ── PNG List ── */
.png-list { display: flex; flex-direction: column; gap: 8px; }
.png-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  cursor: pointer;
  transition: all .15s;
  display: flex;
  gap: 14px;
  align-items: center;
}
.png-card:hover { border-color: var(--accent); }
.png-card.selected { border-color: var(--accent); background: #0d1a2a; }
.png-card.replaced { border-color: var(--green); }
.png-thumb {
  width: 56px; height: 56px;
  border-radius: 6px;
  object-fit: contain;
  background: repeating-conic-gradient(#1a1a2e 0% 25%, #141428 0% 50%) 0 0 / 10px 10px;
  flex-shrink: 0;
  image-rendering: pixelated;
}
.png-info { flex: 1; min-width: 0; }
.png-name {
  font-weight: 700;
  font-size: 13px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: 3px;
}
.png-meta {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.badge {
  font-size: 10px;
  font-family: var(--font-mono);
  padding: 2px 8px;
  border-radius: 99px;
  font-weight: 700;
  flex-shrink: 0;
}
.badge.ok { background: #003322; color: var(--green); border: 1px solid var(--green); }
.badge.pending { background: #2a1500; color: var(--yellow); border: 1px solid var(--yellow); }
.badge.orig { background: var(--panel); color: var(--muted); border: 1px solid var(--border); }

/* ── Detail Panel ── */
.detail-panel {
  display: none;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 20px;
  margin-top: 20px;
}
.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 8px;
}
.detail-title {
  font-size: 14px;
  font-weight: 700;
  font-family: var(--font-mono);
  color: var(--accent);
  word-break: break-all;
}
.preview-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}
.preview-box {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px;
  text-align: center;
}
.preview-label {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
.preview-img {
  max-width: 100%;
  max-height: 140px;
  object-fit: contain;
  image-rendering: pixelated;
  background: repeating-conic-gradient(#1a1a2e 0% 25%, #141428 0% 50%) 0 0 / 8px 8px;
  border-radius: 4px;
}
.preview-empty {
  height: 100px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--muted);
  font-size: 12px;
  font-family: var(--font-mono);
}
.preview-info {
  font-family: var(--font-mono);
  font-size: 10px;
  color: var(--muted);
  margin-top: 6px;
}
.action-row { display: flex; gap: 8px; flex-wrap: wrap; }

/* ── Toast ── */
.toast {
  position: fixed;
  bottom: 24px; left: 50%;
  transform: translateX(-50%) translateY(80px);
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 20px;
  font-size: 13px;
  font-family: var(--font-mono);
  z-index: 999;
  transition: transform .3s;
  white-space: nowrap;
  max-width: 90vw;
}
.toast.show { transform: translateX(-50%) translateY(0); }
.toast.success { border-color: var(--green); color: var(--green); }
.toast.error   { border-color: var(--accent2); color: var(--accent2); }

/* ── Empty state ── */
.empty { text-align: center; padding: 40px 20px; color: var(--muted); font-family: var(--font-mono); font-size: 13px; }

@media (max-width: 500px) {
  .preview-row { grid-template-columns: 1fr; }
  .logo { font-size: 18px; }
}
</style>
</head>
<body>

<header>
  <div class="logo">JAR<span>PNG</span></div>
  <div style="font-size:11px;color:var(--muted);font-family:var(--font-mono)">Editor v1.0</div>
  <div class="jar-name" id="jarName">nenhum JAR aberto</div>
</header>

<div class="container">

  <!-- Upload -->
  <div class="upload-zone" id="uploadZone">
    <input type="file" accept=".jar" id="jarInput">
    <div class="upload-icon">📦</div>
    <h2>Abrir arquivo JAR</h2>
    <p>Toque para selecionar ou arraste um .jar</p>
  </div>

  <!-- Progress -->
  <div class="progress-wrap" id="progressWrap">
    <div class="progress-label" id="progressLabel">Analisando...</div>
    <div class="progress-bar"><div class="progress-fill" id="progressFill"></div></div>
  </div>

  <!-- Stats -->
  <div class="stats-bar" id="statsBar">
    <div class="stat">🗂 Arquivos: <span class="stat-val" id="statFiles">0</span></div>
    <div class="stat">🖼 PNGs: <span class="stat-val green" id="statPngs">0</span></div>
    <div class="stat">✔ Trocadas: <span class="stat-val" id="statReplaced">0</span></div>
  </div>

  <!-- Toolbar -->
  <div class="toolbar" id="toolbar">
    <button class="btn primary" id="btnSave">💾 Salvar JAR</button>
    <button class="btn" id="btnExportAll">📦 Exportar Todas</button>
    <button class="btn danger" id="btnNew">↩ Novo JAR</button>
  </div>

  <!-- Filter -->
  <div class="filter-wrap" id="filterWrap">
    <input class="filter-input" id="filterInput" placeholder="🔍  Filtrar por nome..." type="text">
  </div>

  <!-- PNG List -->
  <div class="png-list" id="pngList"></div>

  <!-- Detail Panel -->
  <div class="detail-panel" id="detailPanel">
    <div class="detail-header">
      <div class="detail-title" id="detailTitle"></div>
      <div style="font-family:var(--font-mono);font-size:10px;color:var(--muted)" id="detailMeta"></div>
    </div>
    <div class="preview-row">
      <div class="preview-box">
        <div class="preview-label">Original</div>
        <img class="preview-img" id="previewOrig" src="" alt="">
        <div class="preview-info" id="infoOrig"></div>
      </div>
      <div class="preview-box">
        <div class="preview-label">Substituição</div>
        <div id="previewNewWrap">
          <div class="preview-empty" id="previewEmpty">nenhuma substituta</div>
          <img class="preview-img" id="previewNew" src="" alt="" style="display:none">
        </div>
        <div class="preview-info" id="infoNew"></div>
      </div>
    </div>
    <div class="action-row">
      <button class="btn primary" id="btnImport">📥 Importar PNG</button>
      <input type="file" accept="image/png" id="pngInput" style="display:none">
      <button class="btn" id="btnExport">📤 Exportar Original</button>
      <button class="btn danger" id="btnClear" style="display:none">✖ Cancelar</button>
    </div>
  </div>

</div>

<!-- Toast -->
<div class="toast" id="toast"></div>

<script>
// ── Estado ──────────────────────────────────────────────────────────────────
let entries = [];
let selectedUid = null;
const entry = () => entries.find(e => e.uid === selectedUid);

// ── Toast ────────────────────────────────────────────────────────────────────
function toast(msg, type='success') {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = `toast ${type} show`;
  setTimeout(() => t.classList.remove('show'), 3000);
}

// ── Upload JAR ───────────────────────────────────────────────────────────────
document.getElementById('jarInput').addEventListener('change', async function() {
  if (!this.files[0]) return;
  const file = this.files[0];
  document.getElementById('jarName').textContent = file.name;
  
  const fd = new FormData();
  fd.append('jar', file);
  
  showProgress(true);
  document.getElementById('uploadZone').style.display = 'none';
  
  try {
    const res = await fetch('/api/open', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { toast(data.error, 'error'); resetUI(); return; }
    entries = data.entries;
    renderList(entries);
    document.getElementById('statFiles').textContent = data.scanned;
    document.getElementById('statPngs').textContent  = data.total;
    document.getElementById('statsBar').style.display = 'flex';
    document.getElementById('toolbar').style.display  = 'flex';
    document.getElementById('filterWrap').style.display = 'block';
    updateReplacedCount();
    if (entries.length === 0) toast('Nenhuma PNG encontrada neste JAR', 'error');
    else toast(`${data.total} PNG(s) encontrada(s)!`);
  } catch(e) { toast('Erro ao enviar JAR', 'error'); resetUI(); }
  
  showProgress(false);
});

// Drag & drop
const zone = document.getElementById('uploadZone');
zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag'));
zone.addEventListener('drop', e => {
  e.preventDefault(); zone.classList.remove('drag');
  const f = e.dataTransfer.files[0];
  if (f && f.name.endsWith('.jar')) {
    const dt = new DataTransfer(); dt.items.add(f);
    document.getElementById('jarInput').files = dt.files;
    document.getElementById('jarInput').dispatchEvent(new Event('change'));
  }
});

// ── Render Lista ─────────────────────────────────────────────────────────────
function renderList(list) {
  const container = document.getElementById('pngList');
  container.innerHTML = '';
  if (!list.length) {
    container.innerHTML = '<div class="empty">Nenhuma PNG encontrada</div>';
    return;
  }
  list.forEach(e => {
    const card = document.createElement('div');
    card.className = 'png-card' + (e.uid === selectedUid ? ' selected' : '') + (e.replaced ? ' replaced' : '');
    card.dataset.uid = e.uid;
    const badgeClass = e.replaced ? 'ok' : 'orig';
    const badgeText  = e.replaced ? '✔ trocada' : 'original';
    card.innerHTML = `
      <img class="png-thumb" src="data:image/png;base64,${e.preview}" alt="">
      <div class="png-info">
        <div class="png-name" title="${e.jar_entry}">${e.filename}</div>
        <div class="png-meta">
          <span>${e.jar_entry}</span>
          <span>${e.offset}</span>
          <span>${e.size} ${e.mode}</span>
          <span>${e.bytes}B</span>
        </div>
      </div>
      <div class="badge ${badgeClass}">${badgeText}</div>`;
    card.addEventListener('click', () => selectEntry(e.uid));
    container.appendChild(card);
  });
}

// ── Filtro ───────────────────────────────────────────────────────────────────
document.getElementById('filterInput').addEventListener('input', function() {
  const q = this.value.toLowerCase();
  const filtered = q ? entries.filter(e => e.jar_entry.toLowerCase().includes(q)) : entries;
  renderList(filtered);
});

// ── Selecionar Entrada ────────────────────────────────────────────────────────
function selectEntry(uid) {
  selectedUid = uid;
  const e = entry();
  if (!e) return;

  // Atualiza cards
  document.querySelectorAll('.png-card').forEach(c => {
    c.classList.toggle('selected', c.dataset.uid === uid);
  });

  // Preenche painel de detalhes
  document.getElementById('detailPanel').style.display = 'block';
  document.getElementById('detailTitle').textContent = e.jar_entry;
  document.getElementById('detailMeta').textContent =
    `offset ${e.offset}  |  ${e.size} ${e.mode}  |  ${e.bytes} bytes`;

  document.getElementById('previewOrig').src = `data:image/png;base64,${e.preview}`;
  document.getElementById('infoOrig').textContent = `${e.size} ${e.mode} — ${e.bytes}B`;

  if (e.rep_preview) {
    document.getElementById('previewNew').src = `data:image/png;base64,${e.rep_preview}`;
    document.getElementById('previewNew').style.display = '';
    document.getElementById('previewEmpty').style.display = 'none';
    document.getElementById('btnClear').style.display = '';
    document.getElementById('infoNew').textContent = 'substituta carregada';
  } else {
    document.getElementById('previewNew').style.display = 'none';
    document.getElementById('previewEmpty').style.display = '';
    document.getElementById('btnClear').style.display = 'none';
    document.getElementById('infoNew').textContent = '';
  }

  document.getElementById('detailPanel').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

// ── Importar PNG ──────────────────────────────────────────────────────────────
document.getElementById('btnImport').addEventListener('click', () => {
  document.getElementById('pngInput').click();
});

document.getElementById('pngInput').addEventListener('change', async function() {
  if (!this.files[0] || !selectedUid) return;
  const fd = new FormData();
  fd.append('png', this.files[0]);
  fd.append('uid', selectedUid);
  try {
    const res = await fetch('/api/replace', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { toast(data.error, 'error'); return; }
    // Atualiza entry local
    const e = entry();
    e.replaced    = true;
    e.rep_preview = data.rep_preview;
    renderList(document.getElementById('filterInput').value
      ? entries.filter(e2 => e2.jar_entry.toLowerCase().includes(document.getElementById('filterInput').value.toLowerCase()))
      : entries);
    selectEntry(selectedUid);
    updateReplacedCount();
    toast('PNG substituta carregada!');
  } catch { toast('Erro ao importar PNG', 'error'); }
  this.value = '';
});

// ── Cancelar Substituição ─────────────────────────────────────────────────────
document.getElementById('btnClear').addEventListener('click', async () => {
  if (!selectedUid) return;
  const res = await fetch('/api/clear', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ uid: selectedUid })
  });
  const data = await res.json();
  if (data.ok) {
    const e = entry();
    e.replaced = false; e.rep_preview = null;
    renderList(entries);
    selectEntry(selectedUid);
    updateReplacedCount();
    toast('Substituição cancelada');
  }
});

// ── Exportar PNG Original ─────────────────────────────────────────────────────
document.getElementById('btnExport').addEventListener('click', async () => {
  if (!selectedUid) return;
  window.location.href = `/api/export_one?uid=${encodeURIComponent(selectedUid)}`;
});

// ── Exportar Todas ────────────────────────────────────────────────────────────
document.getElementById('btnExportAll').addEventListener('click', async () => {
  if (!entries.length) return;
  toast('Exportando todas as PNGs...');
  const res = await fetch('/api/export_all', { method: 'POST' });
  const data = await res.json();
  if (data.error) { toast(data.error, 'error'); return; }
  toast(`${data.count} PNGs exportadas para ${data.folder}`);
});

// ── Salvar JAR ────────────────────────────────────────────────────────────────
document.getElementById('btnSave').addEventListener('click', async () => {
  const pending = entries.filter(e => e.replaced);
  if (!pending.length) { toast('Nenhuma substituição pendente', 'error'); return; }
  toast('Gerando JAR...');
  try {
    const res = await fetch('/api/save', { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      toast(data.error || 'Erro ao salvar', 'error');
      return;
    }
    // Dispara o download direto no navegador
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') || '';
    const match = disposition.match(/filename="?([^"]+)"?/);
    const filename = match ? match[1] : 'modified.jar';
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    toast('✔ Download iniciado!');
    // Marca entradas como salvas
    entries.forEach(e => { if (e.replaced) { e.replaced = true; } });
    renderList(entries);
  } catch(e) {
    toast('Erro ao gerar JAR', 'error');
  }
});

// ── Novo JAR ──────────────────────────────────────────────────────────────────
document.getElementById('btnNew').addEventListener('click', async () => {
  await fetch('/api/reset', { method: 'POST' });
  resetUI();
});

function resetUI() {
  entries = []; selectedUid = null;
  document.getElementById('uploadZone').style.display = '';
  document.getElementById('statsBar').style.display   = 'none';
  document.getElementById('toolbar').style.display    = 'none';
  document.getElementById('filterWrap').style.display = 'none';
  document.getElementById('detailPanel').style.display = 'none';
  document.getElementById('pngList').innerHTML = '';
  document.getElementById('jarName').textContent = 'nenhum JAR aberto';
  document.getElementById('filterInput').value = '';
}

function showProgress(show) {
  document.getElementById('progressWrap').style.display = show ? 'block' : 'none';
}

function updateReplacedCount() {
  document.getElementById('statReplaced').textContent = entries.filter(e => e.replaced).length;
}
</script>
</body>
</html>"""

# ── Rotas API ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/open", methods=["POST"])
def api_open():
    f = request.files.get("jar")
    if not f:
        return jsonify(error="Nenhum arquivo enviado")

    # Salva JAR em temporário
    tmp = tempfile.NamedTemporaryFile(suffix=".jar", delete=False)
    f.save(tmp.name)
    tmp.close()

    # Limpa temporários antigos
    for p in SESSION["tmp_files"]:
        try: os.unlink(p)
        except: pass
    SESSION["tmp_files"] = [tmp.name]
    SESSION["jar_path"]  = tmp.name

    analysis = analyze_jar(tmp.name)
    if analysis.error:
        return jsonify(error=analysis.error)

    SESSION["analysis"] = analysis
    return jsonify(
        entries=[entry_to_dict(e) for e in analysis.entries],
        scanned=analysis.scanned_files,
        total=len(analysis.entries),
    )


@app.route("/api/replace", methods=["POST"])
def api_replace():
    uid = request.form.get("uid")
    f   = request.files.get("png")
    if not uid or not f:
        return jsonify(error="Dados inválidos")

    analysis: JarAnalysis = SESSION.get("analysis")
    if not analysis:
        return jsonify(error="Nenhum JAR aberto")

    entry = next((e for e in analysis.entries if e.uid == uid), None)
    if not entry:
        return jsonify(error="Entrada não encontrada")

    raw = f.read()
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except Exception as ex:
        return jsonify(error=f"PNG inválida: {ex}")

    entry.replacement = raw
    entry.replaced    = False
    rep_b64 = img_to_b64(img)
    return jsonify(ok=True, rep_preview=rep_b64)


@app.route("/api/clear", methods=["POST"])
def api_clear():
    data = request.get_json()
    uid  = data.get("uid") if data else None
    analysis: JarAnalysis = SESSION.get("analysis")
    if not analysis or not uid:
        return jsonify(ok=False)
    entry = next((e for e in analysis.entries if e.uid == uid), None)
    if entry:
        entry.replacement = None
        entry.replaced    = False
    return jsonify(ok=True)


@app.route("/api/export_one")
def api_export_one():
    uid      = request.args.get("uid")
    analysis = SESSION.get("analysis")
    if not analysis or not uid:
        return "Não encontrado", 404
    entry = next((e for e in analysis.entries if e.uid == uid), None)
    if not entry:
        return "Não encontrado", 404

    fname = f"png_0x{entry.offset:X}.png"
    return send_file(
        io.BytesIO(entry.original_data),
        mimetype="image/png",
        as_attachment=True,
        download_name=fname,
    )


@app.route("/api/export_all", methods=["POST"])
def api_export_all():
    analysis = SESSION.get("analysis")
    if not analysis or not analysis.entries:
        return jsonify(error="Nenhuma PNG disponível")

    jar_stem  = Path(analysis.jar_path).stem
    out_folder = Path.home() / "jar_png_exports" / jar_stem
    out_folder.mkdir(parents=True, exist_ok=True)

    count = 0
    for e in analysis.entries:
        safe = e.jar_entry.replace("/", "_").replace("\\", "_")
        fname = f"{safe}__0x{e.offset:X}.png"
        (out_folder / fname).write_bytes(e.original_data)
        count += 1

    return jsonify(count=count, folder=str(out_folder))


@app.route("/api/save", methods=["POST"])
def api_save():
    analysis = SESSION.get("analysis")
    if not analysis:
        return jsonify(error="Nenhum JAR aberto")

    pending = [e for e in analysis.entries if e.replacement]
    if not pending:
        return jsonify(error="Nenhuma substituição pendente")

    jar_stem = Path(analysis.jar_path).stem
    filename = f"{jar_stem}_modified.jar"

    # Grava em memória para enviar direto ao navegador
    buf = io.BytesIO()

    # apply_replacements adaptado para buffer
    import zipfile as zf_mod, shutil as sh_mod
    replacements_by_entry = {}
    for e in analysis.entries:
        if e.replacement is not None:
            replacements_by_entry.setdefault(e.jar_entry, []).append(e)

    try:
        with zf_mod.ZipFile(analysis.jar_path, "r") as zf_in,              zf_mod.ZipFile(buf, "w", compression=zf_mod.ZIP_DEFLATED) as zf_out:
            for info in zf_in.infolist():
                data = zf_in.read(info.filename)
                if info.filename in replacements_by_entry:
                    entries_sorted = sorted(
                        replacements_by_entry[info.filename],
                        key=lambda e: e.offset, reverse=True)
                    new_data = bytearray(data)
                    for entry in entries_sorted:
                        del new_data[entry.offset:entry.end]
                        new_data[entry.offset:entry.offset] = entry.replacement
                    zf_out.writestr(info, bytes(new_data))
                else:
                    zf_out.writestr(info, data)
    except Exception as ex:
        return jsonify(error=str(ex))

    # Marca entradas como salvas
    for e in analysis.entries:
        if e.replacement:
            e.replaced    = True
            e.replacement = None

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/java-archive",
        as_attachment=True,
        download_name=filename,
    )


@app.route("/api/reset", methods=["POST"])
def api_reset():
    SESSION["analysis"] = None
    SESSION["jar_path"] = None
    return jsonify(ok=True)


# ── Main ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  JAR PNG Editor - Versão Web")
    print("=" * 50)
    print()
    print("  Abra no navegador do Android:")
    print("  👉  http://localhost:5000")
    print()
    print("  Para encerrar: Ctrl+C")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5000, debug=False)
