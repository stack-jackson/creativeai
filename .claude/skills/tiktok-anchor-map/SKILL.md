---
name: tiktok-anchor-map
description: Mapeia 100% de um vídeo de TikTok criado com IA (imagens âncora animadas) e entrega um storyboard com imagens âncora, prompts de imagem/animação, transcrição exata e contexto. Use sempre que o usuário colar um link do TikTok (tiktok.com, vm.tiktok.com, vt.tiktok.com) ou pedir para "mapear/modelar/decupar" um vídeo de TikTok.
---

# TikTok → mapa de imagens âncora + storyboard

O usuário é criador de conteúdo IA. Os vídeos são feitos gerando primeiro uma **imagem âncora** por cena e animando-a depois (image-to-video). O objetivo é deixar o vídeo 100% mapeado para ele recriar a própria versão. Responda em **português do Brasil**.

## Fluxo

1. **Extrair** (um link = uma pasta nova em `./tiktok-maps/<video_id>/`):
   ```bash
   pip install -q -U "yt-dlp[default,curl-cffi]" faster-whisper   # curl-cffi é obrigatório p/ TikTok (impersonação de navegador)
   python3 -I .claude/skills/tiktok-anchor-map/scripts/extract.py "<URL>" tiktok-maps/<video_id> [--threshold 0.25] [--model small] [--lang auto]
   ```
   Gera `video.mp4`, `meta.json` (legenda, hashtags, música, métricas), `anchors/scene_NN_{anchor,mid,end}.jpg`, `contact_sheet.jpg`, `transcript.json/.txt` (com timestamps por palavra) e `manifest.json` (cenas + fala de cada cena).
   - Use `--model medium` se a transcrição sair com erros; `--lang pt` se o idioma for sabido.
2. **Validar os cortes**: leia `contact_sheet.jpg` e compare com `manifest.json`. Cenas demais (movimento de câmera/zoom contado como corte) → rode de novo com `--threshold 0.35–0.45`. Cenas faltando (cortes suaves/fusões entre imagens parecidas) → `--threshold 0.12–0.18`. Confira também a duração: cena < 1s costuma ser falso corte.
3. **Olhar de verdade** cada cena: abra com Read o `_anchor`, `_mid` e `_end` de todas as cenas (a âncora é o 1º frame limpo após o corte = a imagem estática que existia antes de animar; mid/end revelam o movimento). Nunca descreva cena que você não viu.
4. **Transcrição**: ⚠️ vídeo ASMR/sem voz faz o Whisper alucinar ("Thanks for watching!", "Obrigado por assistir"…). Confira `no_speech_prob` em `transcript.json` (> 0,5 ou frase de despedida genérica sozinha = alucinação) e, se não houver fala real, escreva "sem fala" no storyboard. Havendo fala, copie literalmente de `transcript.txt`; não parafraseie nem "corrija" gírias. Releia as palavras com baixa confiança/estranhas e sinalize `[?]`. Textos na tela (legendas queimadas, títulos) leia dos frames e registre à parte da fala.
5. **Escrever** `tiktok-maps/<video_id>/storyboard.md` (formato abaixo) e resumir no chat: nº de cenas, duração, estilo, hook, e onde estão os arquivos.

## Formato do storyboard.md

```
# <título> — @<autor> (<duração>s, <N> cenas)
Link · data · métricas · música/áudio

## Contexto geral
- Tema/nicho e promessa do vídeo · público-alvo
- Estrutura narrativa (hook 0–3s → desenvolvimento → payoff/CTA) e por que prende
- Voz: tipo (locução IA/humana), idioma, tom, ritmo (palavras/seg)
- Legendas: estilo, posição, destaque por palavra · trilha/SFX
- Ferramentas prováveis (imagem / vídeo / voz) — marque como *hipótese*

## Bíblia de estilo (reutilizável)
- Estilo visual, paleta, iluminação, lente/proporção (9:16), textura
- Personagens/objetos recorrentes com descrição fixa p/ consistência
- Prompt-base de estilo (colar no começo de todo prompt de imagem)

## Transcrição completa (exata)
[00:00.00] ... (segmentos com timestamp) — texto íntegro, sem edição

## Cenas
### Cena NN · 00:00.0–00:03.2 (3.2s)
- **Imagem âncora**: `anchors/scene_NN_anchor.jpg`
- **Narração (exata)**: "..."
- **Texto na tela**: ...
- **O que mostra**: composição, enquadramento, sujeito, fundo, luz
- **Prompt de imagem (reconstruído)**: <prompt-base de estilo> + descrição específica da cena
- **Animação**: movimento do sujeito + movimento de câmera (zoom in/out, pan, orbit, parallax…) + intensidade + prompt de image-to-video
- **Transição p/ próxima**: corte seco / fusão / whip / match cut
- **Notas**: SFX, música, ritmo, referência à fala (qual palavra dispara o corte)
```

## Regras

- Fidelidade acima de tudo: fala e texto na tela literais; o que for inferência (prompts, ferramentas) fica rotulado como reconstrução/hipótese.
- Mapeie **todas** as cenas, inclusive as de 1s. Se a mesma âncora reaparece, indique "reutiliza cena NN".
- Fade-in/fade-out: o script já pula frames escurecidos; confira a âncora da cena 1 e o último frame. Marca d'água de outro canal = sinal de repost; registre no contexto.
- Mudança de rosto/expressão dentro de uma cena (glitch de IA ou gag) → registre âncora inicial **e** frame final (start/end frame).
- Direitos autorais: se o personagem for IP de terceiros, sugira personagem original na versão do usuário.
- Âncora com texto/rosto gerado por IA com defeito? Anote — ajuda quem vai recriar.
- Várias URLs coladas: processe uma pasta por vídeo, na ordem.
- Se o vídeo for slideshow/foto-modo (sem `video.mp4`), mapeie as imagens do carrossel como âncoras.

## Se algo falhar (diagnóstico rápido)

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `CONNECT tunnel failed 403` / yt-dlp falha | rede do ambiente bloqueia o TikTok | Peça ao usuário para liberar em *Network access*: `tiktok.com`, `*.tiktok.com`, `*.tiktokcdn.com`, `*.tiktokcdn-us.com`, `*.tiktokv.com`, `*.muscdn.com`; ou que anexe o .mp4 e rode o script com o arquivo local |
| `403 Forbidden` na transcrição | `huggingface.co` bloqueado (download do modelo Whisper) | Liberar `huggingface.co` e `*.hf.co`; ou usar legendas baixadas pelo yt-dlp (`video.*.vtt`) / transcrever fora e passar o texto |
| yt-dlp: "Unexpected response from webpage request" | falta impersonação | `pip install -U "yt-dlp[default,curl-cffi]"` |
| yt-dlp: "Unable to extract" | TikTok mudou a API | `pip install -U yt-dlp` |
| `open() got an unexpected keyword argument 'metadata_errors'` | PyAV novo × faster-whisper | já contornado no script (áudio via ffmpeg) |
| Sem áudio | vídeo só música/sem voz | `transcription_error` explica; registre apenas textos na tela |

Nunca invente transcrição: se não conseguiu transcrever, diga isso claramente e entregue o storyboard visual com a fala marcada como `[pendente]`.
