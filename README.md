<div align="center">

<img src="ViraTudo.png" alt="ViraTudo" width="160"/>

# ViraTudo

**Conversor de mídia universal e open-source para Windows e Linux.**

Tudo vira o que você quer. Conversão 100% local, sem nuvem, sem telemetria — seus arquivos nunca saem da sua máquina.

`Python` `PySide6 (Qt6)` `FFmpeg` `yt-dlp`

</div>

---

## Sumário

- [Recursos](#recursos)
- [Como funciona por dentro](#como-funciona-por-dentro)
- [Onde os arquivos ficam](#onde-os-arquivos-ficam)
- [Formatos suportados](#formatos-suportados)
- [Qualidade e conversão](#qualidade-e-conversão)
- [YouTube](#youtube)
- [Build](#build)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Testes](#testes)
- [Roadmap](#roadmap)
- [Licença](#licença)

---

## Recursos

### Conversão de arquivos
- **18 formatos de saída** entre vídeo, áudio e imagem — MP4, MKV, WebM, AVI, MOV, MPEG, GIF, MP3, FLAC, WAV, OGG, Opus, M4A, PNG, JPG, WebP, BMP e TIFF.
- **Fila paralela**: vários arquivos convertidos ao mesmo tempo (2 por padrão, configurável), cada um na sua thread — a interface nunca congela.
- **Corte de trecho** com seek rápido (`-ss` + `-t`): extraia só o pedaço que interessa, com duração determinística.
- **Perfis de qualidade** por formato: bitrate de áudio (128k/192k/320k...), CRF de vídeo e níveis de compressão.
- **Redimensionamento** em um clique: 4K, Full HD, HD, SD ou resolução personalizada.
- **Foto → vídeo/GIF**: transforme imagens em vídeo com duração configurável (usa `-loop 1`).
- **Validação de combinações**: combinações impossíveis (áudio→vídeo, imagem→áudio) são bloqueadas com mensagem clara antes de chamar o FFmpeg — nada de erro criptográfico no meio da conversão.
- **GIF de qualidade** com filtro de paleta (`palettegen`/`paletteuse`), fps e largura ajustáveis.
- **Drag & drop**: arraste arquivos direto do Explorer/Nautilus para a fila.
- **Estimativa de tamanho** do arquivo de saída, calculada em background (não trava a interface).

### YouTube
- **Download até 4K** (2160p/1440p/1080p/720p/480p/360p ou "melhor disponível").
- **Prévia automática** com debounce: título, duração, resoluções disponíveis e **thumbnail** do vídeo.
- **Playlists completas** com seleção de faixas por checkboxes (e ranges tipo `1-5,7`).
- **Conversão automática**: o vídeo baixado em MP4 é convertido localmente para o formato pedido (MKV, WebM, GIF...) quando necessário — com **progresso real na barra** (fase "Convertendo...").
- **Baixar direto (sem converter)**: baixa o **stream nativo** do YouTube (MP4 ou WebM) com merge `-c copy` — sem recodificação, quase instantâneo. WebM (VP9/Opus) costuma estar disponível em qualquer qualidade, inclusive 4K. Se o formato+qualidade não existir nativamente, o app avisa.
- **Qualidade e formato sincronizados**: "Somente áudio" só aceita formatos de áudio — combinações impossíveis nem aparecem.
- **Legendas** (.srt) em português e inglês quando disponíveis.
- **Anti-bot resiliente**: tenta o client padrão → cai para o client `android` → último recurso usa cookies do navegador logado.

### Experiência
- **Nativo e leve**: interface Qt6 de verdade — sem Electron, sem WebView.
- **Temas** Dark / Light / Sistema com persistência.
- **Aceleração por hardware** (NVENC/QSV/VAAPI/AMF) com fallback automático para CPU.
- **Logs** rotativos em `~/ViraTudo/logs/app.log`.
- **Modo terminal** para quem prefere a linha de comando ou automação.

---

## Como funciona por dentro

```
┌─────────────────────────────────────────────────────┐
│                 ViraTudo (PySide6/Qt6)              │
│  ┌─────────────────────┐   ┌─────────────────────┐  │
│  │   ConverterFiles    │   │      YouTubeTab     │  │
│  │   (fila paralela)   │   │ (prévia + download) │  │
│  └──────────┬──────────┘   └──────────┬──────────┘  │
│             │                        │             │
│  ┌──────────▼──────────┐   ┌──────────▼──────────┐  │
│  │     ffmpeg_core     │   │       youtube       │  │
│  │ (subprocess FFmpeg) │   │     (yt-dlp)        │  │
│  │  -progress pipe:1   │   │  postprocessors     │  │
│  └──────────┬──────────┘   └──────────┬──────────┘  │
│             │                        │             │
│        ┌────▼────────────────────────▼────┐        │
│        │        presets + settings        │        │
│        │  (formatos, perfis, QSettings)   │        │
│        └──────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

| Camada | Tecnologia |
|--------|-----------|
| Interface | PySide6 (Qt6) com estilo Fusion — idêntico em Windows e Linux |
| Conversão | FFmpeg via subprocess, progresso real por `out_time_ms` |
| Downloads | yt-dlp com fallback de clientes e cookies |
| Persistência | QSettings (registro no Windows, `~/.config` no Linux) |
| Logs | `logging` rotativo em `~/ViraTudo/logs/` |

O progresso é real: o FFmpeg reporta `out_time_ms` via `-progress pipe:1` e a GUI atualiza a barra com **velocidade (MB/s)** e **tempo restante estimado**.

---

## Onde os arquivos ficam

| Tipo | Local padrão |
|------|--------------|
| Conversões | `~/Conversor/` (configurável na GUI) |
| Downloads do YouTube | `~/Downloads/YouTube/` (configurável na GUI) |
| Logs | `~/ViraTudo/logs/app.log` |

> 💡 As preferências (pasta, formato, qualidade) são lembradas entre sessões.

---

## Formatos suportados

| Categoria | Formatos |
|-----------|----------|
| 🎬 Vídeo | MP4 (H.264+AAC), MKV, WebM (VP9+Opus), AVI, MOV, MPEG, GIF animado |
| 🎵 Áudio | MP3 (128k/192k/320k), FLAC, WAV, OGG, Opus, M4A (AAC) |
| 🖼️ Imagem | PNG, JPG, WebP, BMP, TIFF |

**Entradas aceitas**: praticamente qualquer mídia que o FFmpeg entenda — MP4, MKV, WebM, AVI, MOV, WMV, FLV, MPG, M4V, TS, 3GP, VOB, MP3, WAV, FLAC, OGG, Opus, M4A, AAC, WMA, AC3, AIFF, ALAC, AMR, APE, MKA, PNG, JPG, WebP, BMP, TIFF, GIF, SVG, HEIC, ICO, PSD, RAW, AVIF...

---

## Qualidade e conversão

- **Vídeo**: perfis CRF (menor tamanho ↔ maior qualidade) para MP4, MKV, MOV e WebM; aceleração por hardware quando disponível.
- **Áudio**: bitrate configurável (ex.: MP3 128k/192k/320k), FLAC com nível de compressão, WAV PCM 16/24-bit.
- **Imagem**: qualidade JPG (q2/q5/q8), PNG sem perdas com compressão.
- **Corte**: defina início e fim em segundos — a duração da saída é exatamente `fim − início`.
- **Foto → vídeo**: escolha a duração (0,5 s a 10 min); o app repete o frame com `-loop 1`.

---

## YouTube

O fluxo é **baixar + converter localmente**:

```
URL do vídeo/playlist
        │
        ▼  yt-dlp (extract_info)
   prévia: título, duração, resoluções, thumbnail
        │
        ▼  download do melhor stream (até 4K)
        │
        ▼  FFmpeg local
   formato pedido (MP3, M4A, FLAC, MKV, GIF...)
```

- Qualidade **"Somente áudio"** baixa o melhor stream de áudio e converte para o formato escolhido.
- **Playlists** podem ser baixadas inteiras ou com faixas selecionadas por checkboxes.
- Se o YouTube pedir verificação anti-bot, o app tenta automaticamente clientes alternativos e, como último recurso, usa os cookies do navegador logado.

---

## Build, release e instalação

A versão do app fica centralizada em `converter/__init__.py` (`__version__`) e é
exibida no título da janela, no menu **Ajuda → Sobre** e em `python app.py --version`.
Atualize sempre esse único lugar antes de gerar um release.

### Pré-requisitos

| Requisito | Windows | Linux (Ubuntu/Debian) |
|-----------|---------|------------------------|
| Python    | **3.10+** instalado com "Add to PATH" | `sudo apt install python3 python3-venv python3-pip` |
| FFmpeg    | baixar do [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) e adicionar o `bin` ao PATH | `sudo apt install ffmpeg` |
| Libs Qt6  | — (embutidas no PyInstaller) | `sudo apt install libxcb-cursor0 libxkbcommon-x11-0 libgl1 libegl1` |

Verifique antes de prosseguir:

```bash
python --version      # Windows: python --version
ffmpeg -version       # deve mostrar a versão do FFmpeg
```

### Rodar em desenvolvimento

Crie um ambiente virtual e instale as dependências (o `python app.py` abre a GUI):

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

> 💡 Só precisa repetir `pip install` quando o `requirements.txt` mudar.

### Rodar os testes

```bash
python -m pytest
```

### Release — Windows (PyInstaller)

**Opção A — script de 1 clique:**

```bat
build_windows.bat
```

O script faz, em ordem:
1. `python -m assets.gerar_icone` → gera `assets\icon.png` e `assets\icon.ico` a partir da logo `ViraTudo.png`.
2. `pip install pyinstaller` (se necessário).
3. `python -m PyInstaller --noconfirm --clean --windowed --name ViraTudo --icon assets\icon.ico --add-data "assets;assets" --hidden-import yt_dlp app.py`.
4. Cria o atalho `ViraTudo.lnk` na raiz do projeto.

Resultado: `dist\ViraTudo\ViraTudo.exe`.

**Opção B — comando manual (equivalente):**

```bat
pip install -r requirements.txt pyinstaller
python -m assets.gerar_icone
python -m PyInstaller --noconfirm --clean --windowed --name ViraTudo ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --hidden-import yt_dlp ^
  app.py
```

**Empacotar o release (ZIP):**

```powershell
Compress-Archive -Path dist\ViraTudo\* -DestinationPath dist\ViraTudo_1.3.0_win64.zip
```

> Substitua `1.3.0` pela versão atual (veja `converter/__init__.py`).

### Release — Linux (PyInstaller)

**Opção A — script de 1 clique:**

```bash
chmod +x build_linux.sh
./build_linux.sh
```

O script cria/usa `.venv-linux`, instala as dependências, gera o ícone e empacota com PyInstaller.

Resultado: `dist/viratudo/viratudo`.

**Opção B — comando manual (equivalente):**

```bash
python3 -m venv .venv-linux
source .venv-linux/bin/activate
pip install -r requirements.txt pyinstaller
python -m assets.gerar_icone
python -m PyInstaller --noconfirm --clean --windowed --name viratudo \
  --icon assets/icon.png \
  --add-data "assets:assets" \
  --hidden-import yt_dlp \
  app.py
```

**Empacotar o release (tar.gz):**

```bash
tar -C dist -czf dist/viratudo_1.3.0_linux.tar.gz viratudo
```

> Substitua `1.3.0` pela versão atual.

### Instalação/execução da máquina de destino

O executável empacota o Python e o Qt6, mas **depende do FFmpeg no PATH**:

- **Windows**: coloque o `ffmpeg.exe` no PATH (ou embuta no pacote com
  `--add-binary "ffmpeg.exe;."` no PyInstaller).
- **Linux**: `sudo apt install ffmpeg` (ou instale as libs Qt6 listadas acima
  se rodar em outra distro).

O app verifica o FFmpeg na barra de status ao abrir; sem ele, conversões e
downloads não funcionam.

### Ícone

`assets/icon.png` e `assets/icon.ico` são gerados a partir da logo oficial
(`ViraTudo.png` na raiz). Para regenerar (ou após trocar a logo):

```bash
python -m assets.gerar_icone      # via QPainter/Pillow
python scripts/aplicar_logo.py    # alternativa usando apenas Pillow
```

### Modo terminal

O app também funciona sem GUI (útil para automação):

```bash
python app.py --version                            # mostra a versão
python app.py --cli video.mp4 mp3                  # converte video.mp4 -> video.mp3
python app.py --cli foto.png mp4                   # foto -> vídeo (5s)
python app.py --cli foto.png jpg                   # converte imagem
python app.py --yt "URL_DO_YOUTUBE" mp3            # baixa e converte para MP3
python app.py --yt "URL_DO_YOUTUBE" mp4 pasta/     # baixa vídeo na pasta
```

---

## Estrutura do projeto

```
.
├── app.py                  # entry point (GUI ou CLI: --cli / --yt)
├── converter/              # lógica pura, testável por CLI
│   ├── presets.py          # tabela de formatos, perfis de qualidade, escalas
│   ├── ffmpeg_core.py      # wrapper do FFmpeg (-progress pipe:1) + HW encoders
│   ├── concat.py           # concatenação com fallback de codec
│   ├── youtube.py          # yt-dlp: prévia, playlists, legendas, anti-bot
│   └── logging_setup.py    # logs rotativos em ~/ViraTudo/logs
├── ui/                     # widgets PySide6 (sem lógica de conversão)
│   ├── main_window.py      # janela principal (abas, menu, tema, ícone)
│   ├── convert_tab.py      # fila paralela, corte, qualidade, drag & drop
│   ├── youtube_tab.py      # download YouTube com prévia e thumbnail
│   ├── themes.py           # paletas claro/escuro/auto
│   └── settings.py         # persistência QSettings
├── assets/
│   ├── icon.png / icon.ico # ícones gerados da logo oficial
│   └── gerar_icone.py      # gera os ícones a partir do ViraTudo.png
├── scripts/
│   └── aplicar_logo.py     # copia ViraTudo.png -> assets e gera o .ico
├── tests/                  # 114 testes pytest (core + GUI offscreen)
├── ViraTudo.png            # logo oficial
├── ViraTudo.spec           # spec do PyInstaller
├── build_windows.bat       # build Windows em 1 clique
├── build_linux.sh          # build Linux em 1 clique
└── abrir_app.bat           # lança o app no Windows
```

---

## Testes

```bash
python -m pytest
```

114 testes cobrem: conversões reais com FFmpeg (vídeo, áudio, imagem, GIF, corte, qualidade, escala, **foto→vídeo**), concatenação, download do YouTube (lógica sem rede), **validação de combinações**, coerção de formato, sincronização qualidade↔formato da UI e testes offscreen da interface (janela, abas, combos).

---

## Roadmap

- **Fase 6** — Concatenação de arquivos exposta na GUI (módulo pronto no core), fila de downloads do YouTube (vários vídeos de uma vez)
- **Fase 7** — Perfis de conversão salvos pelo usuário, verificação de integridade pós-conversão, conversão de URLs genéricas (não só YouTube)
- **Fase 8** — CI/CD multi-plataforma, assinatura do executável Windows, versão portable sem instalação

---

## Licença

Distribuído sob a licença **MIT** — use, modifique e distribua à vontade.

---

<div align="center">

Feito com 🐍, ⚡ e FFmpeg.

</div>
