# JAR PNG Editor — Guia de Uso

Ferramenta para encontrar, exportar e substituir imagens PNG embutidas em arquivos `.jar` de jogos J2ME/mobile. Inspirado no **SJboy Halo**.

---

## Índice

- [O que o programa faz](#o-que-o-programa-faz)
- [Arquivos do projeto](#arquivos-do-projeto)
- [Android — Termux](#android--termux)
- [Windows](#windows)
- [Linux / macOS](#linux--macos)
- [Como usar o programa](#como-usar-o-programa)
- [Onde ficam os arquivos salvos](#onde-ficam-os-arquivos-salvos)
- [Dúvidas comuns](#dúvidas-comuns)

---

## O que o programa faz

Em jogos J2ME, as imagens PNG muitas vezes não ficam como arquivos `.png` separados — elas ficam **embutidas dentro de arquivos binários** (`.bin`, `.res`, etc.). O programa varre cada byte de cada arquivo dentro do JAR procurando a assinatura da PNG, encontra todas as imagens, permite exportá-las, editá-las externamente e reimportá-las. O resultado é um novo JAR com as imagens trocadas, sem modificar o original.

---

## Arquivos do projeto

| Arquivo | Função |
|---|---|
| `core.py` | Lógica de scan e substituição (sem interface) |
| `app_web.py` | Interface web via Flask — usar no **Termux / Android** |
| `jar_png_editor.py` | Interface desktop via tkinter — usar no **PC** |
| `create_test_jar.py` | Gera um JAR de teste com PNGs embutidas |
| `test_game.jar` | JAR de teste pronto para usar |

---

## Android — Termux

### Instalação (fazer só uma vez)

**1. Baixe o Termux pelo F-Droid** (não pela Play Store — a versão da Play está desatualizada):
> https://f-droid.org

**2. Abra o Termux e rode:**
```bash
pkg update && pkg upgrade
```
Quando perguntar `[y/N]` → digite `y` e Enter.

**3. Instale o Python:**
```bash
pkg install python
```

**4. Permita acesso ao armazenamento:**
```bash
termux-setup-storage
```
Aparece uma janela → toque em **Permitir**. Feche e abra o Termux novamente.

**5. Instale as bibliotecas de imagem e ferramentas de compilação:**
```bash
pkg install libjpeg-turbo libtiff libpng python-tkinter build-essential
```

**6. Instale as dependências Python:**
```bash
pip install flask Pillow
```

---

### Colocar os arquivos no Termux

Coloque `core.py` e `app_web.py` em uma pasta no armazenamento interno, por exemplo em `/sdcard/jar_editor/`.

No Termux, acesse a pasta:
```bash
cd /sdcard/jar_editor
ls
```
Deve aparecer `core.py` e `app_web.py` na lista.

---

### Rodar o programa

```bash
python app_web.py
```

Vai aparecer:
```
👉  http://localhost:5000
```

Abra o **Chrome ou qualquer navegador** do Android e acesse:
```
localhost:5000
```

> **Importante:** Não feche o Termux enquanto estiver usando. Deixe-o em segundo plano.

---

### Encerrar o programa

Volte ao Termux e pressione:
```
Ctrl + C
```

---

### Usar novamente

```bash
cd /sdcard/jar_editor
python app_web.py
```

Depois abra `localhost:5000` no navegador.

---

## Windows

### Instalação (fazer só uma vez)

Instale o Python em https://python.org (marque a opção **"Add to PATH"** durante a instalação).

Depois abra o **Prompt de Comando** e instale as dependências:
```bat
pip install Pillow
```

### Rodar

Clique duas vezes em `iniciar.bat`

ou pelo Prompt de Comando:
```bat
python jar_png_editor.py
```

---

## Linux / macOS

### Instalação (fazer só uma vez)

```bash
pip install Pillow --break-system-packages
```

### Rodar

```bash
python3 jar_png_editor.py
```

---

## Como usar o programa

O fluxo é o mesmo tanto na versão web (Termux) quanto na versão desktop (PC).

### ① Abrir o JAR

Clique/toque em **"Abrir JAR"** e selecione o arquivo `.jar` do jogo.

### ② Aguardar o scan

O programa varre todos os arquivos dentro do JAR procurando PNGs. Ao terminar, a lista mostra todas as imagens encontradas com preview. Para cada entrada são exibidos:

- Nome do arquivo onde a PNG está
- Offset (posição em bytes dentro do arquivo)
- Dimensões e modo de cor
- Tamanho em bytes

### ③ Exportar a PNG original

Selecione uma PNG na lista → clique em **📤 Exportar Original**.

A imagem será salva em disco. Abra-a no editor de sua preferência (Photoshop, GIMP, Paint.NET, etc.), faça as modificações e salve como `.png`.

### ④ Importar a PNG modificada

Selecione a mesma entrada na lista → clique em **📥 Importar PNG** → escolha o arquivo editado.

O painel mostra o preview da original ao lado da substituta para comparação.

### ⑤ Repetir para outras PNGs

Repita os passos ③ e ④ para quantas PNGs quiser substituir antes de salvar.

### ⑥ Salvar o JAR

Clique em **💾 Salvar JAR**.

Um novo arquivo é gerado com o sufixo `_modified.jar`. **O JAR original nunca é modificado.**

---

## Onde ficam os arquivos salvos

### Termux (Android)

| Tipo | Caminho |
|---|---|
| JAR modificado | `~/jar_png_output/nome_modified.jar` |
| PNGs exportadas (todas) | `~/jar_png_exports/nome_do_jar/` |

Para acessar pelo gerenciador de arquivos do Android:
```
/data/data/com.termux/files/home/jar_png_output/
```

### PC (Windows)

O programa pergunta onde salvar na hora de exportar/salvar.

---

## Dúvidas comuns

**`command not found` ao tentar rodar**

Não esqueça o `python` na frente:
```bash
python app_web.py
```

**`pip: command not found`**

Use:
```bash
python -m pip install flask Pillow
```

**Termux não acessa o `/sdcard/`**

Rode e aceite a permissão:
```bash
termux-setup-storage
```

**Erro de `libexpat` ou libs faltando**

```bash
pkg upgrade
pip install Pillow
```

**Nenhuma PNG encontrada**

O JAR pode usar um formato de imagem diferente ou as imagens podem estar comprimidas em um formato proprietário. Nem todos os jogos J2ME usam PNG padrão.

**O JAR modificado não funciona no jogo**

Verifique se a PNG substituta tem o mesmo modo de cor da original (ex: RGBA, RGB, P). Alguns jogos são sensíveis ao tamanho — tente manter as mesmas dimensões.

---

## Sobre

Inspirado no **SJboy Halo**, programa chinês de edição de recursos para jogos J2ME.


---

## Autor

Projeto criado por **Rafael**.
