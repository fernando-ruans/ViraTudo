# Plano de Melhorias — Conversor Universal

**Goal:** Evoluir o app de conversor (FFmpeg + YouTube) com recursos de
altíssimo valor: corte de vídeo, controle de qualidade, fila paralela,
drag & drop, persistência de configurações, downloads de playlist e
empacotamento profissional.

**Architecture:** Camadas já separadas (converter/ = lógica pura,
ui/ = PySide6). Melhorias entram primeiro no core (com testes), depois
são expostas na GUI. Sem reescrita — evolução incremental.

**Tech Stack:** Python 3.13, PySide6 6.11, FFmpeg, yt-dlp, pytest,
PyInstaller.

---

## Visão geral das fases

| Fase | Tema | Entregas principais | Esforço |
|------|------|--------------------|---------|
| 0 | Fundação | Testes pytest no core + QSettings | M |
| 1 | Conversor avançado | Corte, qualidade, resolução, concat, GIF configurável | G |
| 2 | UX | Drag & drop, fila paralela, tema, abrir pasta, estimativa de tamanho | M |
| 3 | YouTube | Playlist seletiva, manter original, legenda, título antes de baixar, fila | M |
| 4 | Distribuição | PyInstaller, ícone, logs, aceleração por hardware | M |

Ordem sugerida: 0 → 1 → 2 → 3 → 4 (cada fase deixa o app utilizável).

---

## Fase 0 — Fundação de testes e configuração

Objetivo: criar rede de segurança (testes) e persistência de preferências
antes de mexer em comportamento.

### Task 0.1: Configurar pytest

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (fixture com vídeo de teste gerado via FFmpeg)
- Create: `tests/test_ffmpeg_core.py`
- Create: `tests/test_presets.py`
- Create: `tests/test_youtube.py`
- Modify: `requirements.txt` (adicionar `pytest`)

**Step 1:** Criar `tests/conftest.py` com fixture `sample_video` que gera
um MP4 de 2s (testsrc2 + sine) em tmp_path e o remove no fim.

**Step 2:** Testes iniciais (rodar: `python -m pytest tests -v`):
- `test_ffmpeg_core.py`: conversão mp4→mp3 gera arquivo válido (ffprobe
  confirma codec mp3); mp4→gif; png→jpg (regressão do bug `-vn`);
  `_build_command` não contém `-vn` para imagem; erro amigável quando
  entrada não existe; cancelamento marca status `cancelled`.
- `test_presets.py`: todas as chaves de OUTPUT_FORMATS têm label/ext;
  ALL_INPUT_EXT não tem duplicatas.
- `test_youtube.py`: `is_youtube_url` aceita watch/shorts/youtu.be/
  playlist e rejeita vimeo/google; `_humanize_ytdlp_error` cobre os
  casos conhecidos (bot, indisponível, rede).

**Step 3:** Adicionar `pytest` ao `requirements.txt`.

**Validation:** `python -m pytest tests -v` → todos verdes.

### Task 0.2: Persistência de configurações (QSettings)

**Files:**
- Modify: `ui/main_window.py` (injetar settings nas abas)
- Modify: `ui/convert_tab.py` (salvar/ler última pasta + formato)
- Modify: `ui/youtube_tab.py` (salvar/ler última pasta + formato + qualidade)

**Step 1:** Criar helper `ui/settings.py`:
```python
from PySide6.QtCore import QSettings
s = QSettings("ConversorUniversal", "ConversorUniversal")
s.value("convert/ultima_pasta", str(Path.home() / "Conversor"))
```
Wrapper fino com getters/setters tipados por seção.

**Step 2:** Na aba Converter: ao abrir, preencher `edit_dst` e `combo_format`
com valores salvos; ao iniciar conversão, salvar ambos.

**Step 3:** Na aba YouTube: idem para pasta, formato e qualidade.

**Validation:** abrir app, trocar pasta/formato, fechar, reabrir → valores
persistem. (Teste manual; QSettings não vale unit test.)

---

## Fase 1 — Conversor avançado (corte, qualidade, resolução, concat)

Objetivo: transformar o conversor de "formato a formato" em ferramenta de
edição básica. Tudo continua 100% offline via FFmpeg.

### Task 1.1: Opções de corte (início/fim) na conversão

**Files:**
- Modify: `converter/ffmpeg_core.py` (`ConversionJob` + `_build_command`)
- Modify: `converter/presets.py` (sem mudança de formatos)
- Modify: `ui/convert_tab.py` (campos "Início (s)" e "Fim (s)" por arquivo)
- Test: `tests/test_ffmpeg_core.py`

**Step 1:** Adicionar campos a `ConversionJob`:
```python
start_time: Optional[float] = None   # segundos
end_time: Optional[float] = None     # segundos
```

**Step 2:** Em `_build_command`, injetar `-ss <inicio>` antes de `-i`
(seek rápido) e `-to <fim>` após a entrada:
```python
if job.start_time: cmd.insert(cmd.index("-i"), "-ss", str(job.start_time))
# ordem: ffmpeg -ss X -i entrada -to Y -c:v ...
```

**Step 3:** Teste: converter mp4 de 2s com `start_time=0.5, end_time=1.5`;
ffprobe `duration` ≈ 1.0s ± 0.2.

**Step 4:** Na GUI, coluna/campos de início/fim ao lado de cada item da
fila (spinboxes de segundos, vazio = sem corte).

**Validation:** `pytest` verde; conversão com corte manual via CLI
`python app.py --cli in.mp4 mp3 --start 5 --end 10`.

### Task 1.2: Seletor de qualidade/bitrate por formato

**Files:**
- Modify: `converter/ffmpeg_core.py` (parâmetros de qualidade no job)
- Modify: `converter/presets.py` (perfis por formato: baixa/média/alta)
- Modify: `ui/convert_tab.py` (combo "Qualidade" ao lado do formato)
- Test: `tests/test_ffmpeg_core.py`

**Step 1:** Definir perfis no preset (ex.):
```python
"mp3": {"qualidades": {"128k": "-b:a 128k", "192k": "-b:a 192k", "320k": "-b:a 320k"}},
"mp4": {"qualidades": {"CRF 28 (menor)": "-crf 28", "CRF 20 (padrão)": "-crf 20", "CRF 16 (maior)": "-crf 16"}},
```

**Step 2:** `ConversionJob.quality: Optional[str] = None`; se definido,
substitui os valores default no comando.

**Step 3:** GUI: combo de qualidade só habilita os perfis do formato
selecionado (atualiza ao trocar formato).

**Step 4:** Teste: mp3 com `320k` → ffprobe `bit_rate` ≈ 320000.

**Validation:** `pytest` verde; dois MP3 com qualidades diferentes têm
tamanhos distintos.

### Task 1.3: Redimensionar/resolução de vídeo e imagem

**Files:**
- Modify: `converter/ffmpeg_core.py` (campo `scale`)
- Modify: `ui/convert_tab.py` (combo resolução: Original/720p/1080p/
  Personalizada WxH)
- Test: `tests/test_ffmpeg_core.py`

**Step 1:** `ConversionJob.scale: Optional[str]` (ex. "1280:720").

**Step 2:** Em `_build_command`, adicionar `-vf scale=WxH` (e `-aspect`
implícito) antes da codificação. Para imagem, `-vf scale` também vale.

**Step 3:** Teste: mp4 320x240 com scale "160:120" → ffprobe width=160.

**Validation:** `pytest` verde; arquivo de saída com resolução pedida.

### Task 1.4: Juntar múltiplos arquivos (concat)

**Files:**
- Create: `converter/concat.py` (concatenação via lista de concat demuxer)
- Modify: `ui/convert_tab.py` (botão "Juntar selecionados...")
- Test: `tests/test_concat.py`

**Step 1:** Função `concat_files(inputs: list[str], output: str, fmt: str)`:
gera lista temporária (`file 'caminho'` por linha, escapando aspas), roda
`ffmpeg -f concat -safe 0 -i lista.txt -c copy` quando codecs são
compatíveis, senão re-codifica (`-c:v libx264 -c:a aac`).

**Step 2:** Teste: juntar 2 MP4s de 1s → duração ≈ 2s.

**Step 3:** GUI: com 2+ itens selecionados na fila, botão vira
"Juntar selecionados" (habilita o diálogo de concat).

**Validation:** `pytest` verde; concat via CLI com 2 arquivos reais.

### Task 1.5: GIF configurável (fps, largura, duração máxima)

**Files:**
- Modify: `converter/ffmpeg_core.py` (filtro de paleta parametrizado)
- Modify: `ui/convert_tab.py` (opções quando formato == gif)
- Test: `tests/test_ffmpeg_core.py`

**Step 1:** Substituir `fps=15,scale=480:-1` fixos por valores do job:
```python
job.gif_fps: int = 15
job.gif_width: int = 480
```
Gerar `-vf` dinamicamente com paleta.

**Step 2:** Teste: gif com fps=10 → `ffprobe -show_entries stream=r_frame_rate`
≈ 10.

**Validation:** `pytest` verde; GIFs menores/maiores conforme opções.

---

## Fase 2 — UX (drag & drop, fila paralela, tema, feedback)

Objetivo: deixar o app agradável de usar no dia a dia.

### Task 2.1: Drag & drop de arquivos

**Files:**
- Modify: `ui/convert_tab.py` (subclasse QListWidget aceitando drops)

**Step 1:** `dropEvent` aceita `application/x-qabstractitemmodeldatalist`
e `text/uri-list` (arrastar do Explorer/Nautilus):
```python
def dropEvent(self, event):
    for url in event.mimeData().urls():
        caminho = url.toLocalFile()
        if caminho: self._add_path(caminho)
```

**Step 2:** `dragEnterEvent` aceita se contém arquivos; também aceita
arrastar pasta? (não — manter simples, só arquivos).

**Validation:** arrastar 5 arquivos do Explorer → todos entram na fila.
(Teste manual.)

### Task 2.2: Fila paralela (N conversões simultâneas)

**Files:**
- Modify: `ui/convert_tab.py` (pool de threads)
- Modify: `converter/ffmpeg_core.py` (nenhuma mudança; já thread-safe)

**Step 1:** Trocar loop sequencial por `ThreadPoolExecutor(max_workers=N)`
com N = min(2, cpu_count // 2) padrão, configurável no settings.

**Step 2:** Barra de progresso mostra progresso global da fila (média dos
jobs ativos); label mostra "3/8 convertidos".

**Step 3:** Botão cancelar aborta todos os jobs ativos (já suportado por
`ConversionJob.cancel()`); pendentes viram `cancelled`.

**Validation:** adicionar 8 arquivos, converter → todos concluem; CPU usa
>1 núcleo (observável no Gerenciador de Tarefas). Teste manual.

### Task 2.3: Tema claro/escuro (Fusion + paleta)

**Files:**
- Modify: `ui/main_window.py` (menu Ver > Tema)
- Create: `ui/themes.py` (paletas QPalette para os dois temas)

**Step 1:** Funções `tema_escuro(app)` / `tema_claro(app)` aplicando
QPalette com cores consistentes (fundo, texto, destaque).

**Step 2:** Persistir escolha no QSettings (Task 0.2) e aplicar no boot
do `run_app()`.

**Validation:** alternar tema no menu → UI muda sem reiniciar. Manual.

### Task 2.4: Abrir pasta de destino ao concluir + notificação

**Files:**
- Modify: `ui/convert_tab.py` (ao terminar fila)
- Modify: `ui/youtube_tab.py` (já tem; padronizar)

**Step 1:** Ao concluir a fila, botão "Abrir pasta" (verde) ou pergunta
única "Abrir pasta agora?" (mesmo padrão da aba YouTube).

**Step 2:** `QSystemTrayIcon.showMessage` quando janela minimizada
(opcional, se tray disponível).

**Validation:** converter 1 arquivo → pergunta aparece → abre o Explorer.

### Task 2.5: Estimativa de tamanho do arquivo de saída

**Files:**
- Modify: `converter/ffmpeg_core.py` (função `estimar_tamanho`)
- Modify: `ui/convert_tab.py` (label "≈ 45 MB" ao escolher formato)

**Step 1:** Fórmula por formato:
- Áudio: `duração × bitrate / 8`
- Vídeo: `duração × bitrate_video_estimado (resolução/CRF heurístico) + áudio`
- Imagem: tamanho médio por resolução/codec (heurística simples)

**Step 2:** Atualiza ao trocar formato/qualidade/duração (ffprobe da
entrada já disponível).

**Validation:** MP3 192k de 3min mostra ≈ 4.3 MB. Manual + teste de
`estimar_tamanho` com valores conhecidos.

---

## Fase 3 — YouTube (playlist seletiva, manter original, legenda, prévia)

Objetivo: cobrir os fluxos de download mais pedidos.

### Task 3.1: Prévia do vídeo antes de baixar (título, duração, qualidade)

**Files:**
- Modify: `converter/youtube.py` (`preview_video(url) -> dict`)
- Modify: `ui/youtube_tab.py` (label "🎬 Título — 5:32 — 1080p" ao colar URL)

**Step 1:** `preview_video` chama `extract_info(download=False)` e devolve
`{titulo, duracao, uploader, resolucoes_disponiveis}`.

**Step 2:** GUI: debounce 600ms no campo de URL → mostra prévia (e trava
o combo de qualidade nas resoluções reais do vídeo).

**Validation:** colar URL → título/duração aparecem em <1s. Manual.

### Task 3.2: Playlist com seleção de faixas

**Files:**
- Modify: `converter/youtube.py` (listar faixas + `faixas` no job)
- Modify: `ui/youtube_tab.py` (diálogo com checkboxes ao marcar playlist)

**Step 1:** `listar_playlist(url)` retorna `[{index, titulo, duracao}]`.

**Step 2:** No job, `faixas: list[int] | None`; passa `playlist_items`
pro yt-dlp (ex. "1,3,5-8").

**Step 3:** GUI: ao marcar "É playlist", botão "Selecionar faixas..."
abre diálogo com checkboxes (limite 100 para não travar).

**Validation:** playlist com 5 vídeos → baixar só 2 → 2 arquivos. Manual.

### Task 3.3: Manter o arquivo original + opção "só áudio direto"

**Files:**
- Modify: `converter/youtube.py` (flag `manter_original`)
- Modify: `ui/youtube_tab.py` (checkbox "Manter arquivo original")

**Step 1:** Quando formato de saída ≠ nativo e `manter_original=True`,
converter copiando (não deletar o intermediário).

**Step 2:** Quando formato == áudio e qualidade == "Somente áudio",
usar `FFmpegExtractAudio` direto (sem baixar vídeo) — já cai no fluxo
atual; garantir que "manter original" não conflita.

**Validation:** baixar mp4 mantendo original → 2 arquivos na pasta
(original + convertido). Manual.

### Task 3.4: Baixar legendas (SRT/VTT) junto

**Files:**
- Modify: `converter/youtube.py` (opção `legendas: bool`)
- Modify: `ui/youtube_tab.py` (checkbox "Baixar legendas (se houver)")

**Step 1:** Adicionar `writesubtitles=True, subtitleslangs=["pt", "pt-BR", "en"]`,
`subtitlesformat="srt"`.

**Step 2:** Fallback: se não houver legenda, não é erro (apenas aviso no
status).

**Validation:** vídeo com legenda PT → .srt na pasta. Manual.

---

## Fase 4 — Distribuição e robustez

Objetivo: app instalável, com logs e desempenho melhor.

### Task 4.1: Empacotamento PyInstaller (Windows .exe)

**Files:**
- Create: `build_windows.bat` (ou spec file)
- Modify: `README.md` (instruções finais)

**Step 1:** `pyinstaller --noconfirm --windowed --name ConversorUniversal
--icon assets/icon.ico app.py`

**Step 2:** Testar o .exe em máquina sem Python instalado (o FFmpeg ainda
precisa existir — documentar; ou empacotar ffmpeg.exe via `--add-binary`).

**Validation:** .exe abre e converte em VM limpa.

### Task 4.2: Ícone do app

**Files:**
- Create: `assets/icon.ico` + `assets/icon.png` (gerar programaticamente
  com Pillow/QPainter: letra "U" num retângulo arredondado)
- Modify: `ui/main_window.py` (setWindowIcon) + spec do PyInstaller

**Validation:** ícone aparece na barra de tarefas e no .exe.

### Task 4.3: Logs em arquivo (debug)

**Files:**
- Create: `converter/logging_setup.py` (rotating file handler)
- Modify: `app.py` (iniciar logging no boot)

**Step 1:** Log para `~/Conversor/logs/app.log` com rotation de 1 MB,
nível INFO; exceções com traceback completo.

**Step 2:** Log de cada conversão (entrada, formato, duração, resultado)
e cada download (URL, formato, status).

**Validation:** rodar conversão com erro → log contém o traceback.

### Task 4.4: Aceleração por hardware (NVENC/QSV/VAAPI) quando disponível

**Files:**
- Modify: `converter/ffmpeg_core.py` (detectar encoders)
- Modify: `converter/presets.py` (perfis hw)
- Modify: `ui/convert_tab.py` (combo "Encoder: Auto/CPU/NVENC...")

**Step 1:** `encoders_disponiveis()` roda `ffmpeg -encoders` e filtra
`h264_nvenc`, `hevc_nvenc`, `h264_qsv`, `h264_vaapi`.

**Step 2:** Se formato é mp4/mkv/mov e encoder hw disponível, usar
`-c:v h264_nvenc -preset p4 -cq 20` (fallback automático se falhar →
CPU).

**Validation:** em máquina NVIDIA, conversão mp4 usa NVENC (log mostra).
Se não houver GPU, comportamento atual intacto.

---

## Riscos e tradeoffs

- **Concat com `-c copy`:** falha se codecs divergirem; plano já prevê
  fallback para re-codificação.
- **Fila paralela:** 2 conversões simultâneas podem saturar CPU em
  máquinas fracas; default conservador (2) + configurável.
- **Prévia do YouTube:** chamada `extract_info(download=False)` gasta
  requisição; usar debounce e cache curto (60s) para não estourar rate
  limit.
- **NVENC:** muda resultados (tamanho/qualidade) vs CPU; manter opção
  "CPU" explícita.
- **PyInstaller + FFmpeg:** não é trivial embutir ffmpeg.exe cross-
  platform; documentar ou usar `--add-binary` só no Windows.

## Open questions

1. Quer suporte a **PDF** (páginas → imagem, ou converter pra texto)?
   Isso adiciona dependência (Ghostscript/Poppler) — vale a pena?
2. Quer **renomear em lote** (regras de nome) junto com a conversão?
3. Prioridade: qual fase te interessa mais? (0-1 = poder de conversão,
   2 = conforto, 3 = YouTube, 4 = distribuição)

<!-- CONTINUA -->
