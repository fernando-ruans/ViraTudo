# 🎛️ ViraTudo — Conversor Universal

Conversor de mídia **nativo** (Qt6) para **Windows e Linux**, com conversão
100% **local e offline** + download do **YouTube** com conversão automática.

> Tudo vira o que você quer. 🪄

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Qt6](https://img.shields.io/badge/UI-Qt6-green) ![FFmpeg](https://img.shields.io/badge/FFmpeg-✓-orange)

---

## ✨ Funcionalidades

| Aba | O que faz |
|-----|-----------|
| 📁 **Converter Arquivos** | Converte vídeo, áudio e imagem entre 17 formatos, em lote, com fila e progresso em tempo real |
| ▶️ **YouTube** | Baixa vídeo/áudio do YouTube (até 4K, playlists inclusas) e converte localmente para o formato escolhido |

### Formatos suportados

- **Vídeo:** MP4 (H.264+AAC), MKV, WebM (VP9+Opus), AVI, MOV, MPEG, GIF animado
- **Áudio:** MP3 (192k), FLAC, WAV, OGG, Opus, M4A (AAC)
- **Imagem:** PNG, JPG, WebP, BMP, TIFF

### Por que "universal"

- **Nativo:** interface Qt6 de verdade — sem Electron, sem WebView, leve
- **Offline:** toda conversão roda no seu PC via FFmpeg (nada vai pra nuvem)
- **Cross-platform:** mesmo código roda em Windows e Linux
- **YouTube:** yt-dlp baixa o vídeo; o FFmpeg local converte pro formato que você quiser

---

## 🚀 Como rodar

### Pré-requisitos

1. **Python 3.10+** — [python.org](https://www.python.org/downloads/)
2. **FFmpeg** no PATH
   - **Windows:** baixe de [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (build full),
     extraia e adicione `...\ffmpeg\bin` ao PATH do sistema
   - **Linux:** `sudo apt install ffmpeg` (Debian/Ubuntu) ou
     `sudo dnf install ffmpeg` (Fedora) ou `sudo pacman -S ffmpeg` (Arch)

### Instalação

```bash
cd universal-converter
pip install -r requirements.txt
```

### Uso

```bash
python app.py                          # abre a interface gráfica

# Modo terminal (sem GUI):
python app.py --cli video.mp4 mp3      # converte video.mp4 -> video.mp3
python app.py --cli foto.png jpg       # converte imagem
python app.py --yt "URL_DO_YOUTUBE" mp3        # baixa e converte pra MP3
python app.py --yt "URL_DO_YOUTUBE" mp4 pasta/ # baixa vídeo 4K na pasta
```

---

## 📦 Empacotar como executável

### Windows (PyInstaller)

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "ViraTudo" app.py
# Resultado: dist\ViraTudo\ViraTudo.exe
```

> Dica: o FFmpeg precisa estar no PATH da máquina onde o .exe for rodar,
> ou use `--add-binary` para embutir o ffmpeg.exe no pacote.

### Linux (PyInstaller ou pacote .deb)

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name "viratudo" app.py
# Resultado: dist/viratudo/viratudo
```

---

## 🧠 Como funciona por dentro

```
converter/                 # lógica pura, testável por CLI
├── presets.py             # tabela de formatos e codecs
├── ffmpeg_core.py         # wrapper do FFmpeg (-progress pipe:1) + cancelamento
└── youtube.py             # yt-dlp com fallback anti-bot + cookies do navegador
ui/
├── main_window.py         # janela principal (abas, menu, status)
├── convert_tab.py         # fila de conversão com threads
└── youtube_tab.py         # download YouTube com progresso
app.py                     # entry point (GUI ou CLI)
```

### Detalhes técnicos

- **Progresso real:** o FFmpeg reporta `out_time_ms` via `-progress pipe:1`;
  a GUI parseia e atualiza a barra com velocidade e ETA
- **Conversão em lote:** cada arquivo roda numa thread da fila, com cancelamento
- **GIF de qualidade:** usa filtro de paleta (`palettegen`/`paletteuse`)
- **YouTube anti-bot:** tenta client padrão → cai para client `android`
  (contorna verificação) → último recurso usa cookies do navegador logado
- **Threads:** toda operação pesada roda fora da thread da GUI (nunca congela)

---

## ⚠️ Notas sobre o YouTube

- O download **precisa de internet** (óbvio); a conversão do arquivo baixado
  é 100% local
- O YouTube às vezes impõe **rate limit** ("Sign in to confirm you're not a bot")
  após muitos downloads seguidos do mesmo IP. Aguarde alguns minutos e tente
  de novo — o app já tenta contornar automaticamente
- Para maior estabilidade, fique logado no YouTube em um navegador (Chrome/Edge/
  Firefox); o app usa os cookies como último recurso

---

## 🗂️ Estrutura de pastas geradas

- Conversão: `~/Conversor/` (padrão, configurável na GUI)
- YouTube: `~/Downloads/YouTube/` (padrão, configurável na GUI)

---

## 🛠️ Testes manuais (CLI)

```bash
# Gera um vídeo de teste de 5s com áudio
ffmpeg -f lavfi -i testsrc2=size=320x240:rate=30:duration=5 \
       -f lavfi -i sine=frequency=440:duration=5 \
       -c:v libx264 -c:a aac -shortest test.mp4

python app.py --cli test.mp4 mp3     # extrai áudio
python app.py --cli test.mp4 webm    # vídeo VP9+Opus
python app.py --cli test.mp4 gif     # GIF animado com paleta
```

---

## 📄 Licença

MIT — use, modifique e distribua à vontade.
