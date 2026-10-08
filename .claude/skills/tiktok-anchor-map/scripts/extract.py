#!/usr/bin/env python3
"""Extrai tudo que a skill tiktok-anchor-map precisa de um vídeo do TikTok.

Uso: extract.py <url_ou_arquivo.mp4> <pasta_saida> [--threshold 0.25] [--model small] [--lang auto]

Gera em <pasta_saida>:
  video.mp4, meta.json, manifest.json, transcript.json, transcript.txt
  anchors/scene_NN_anchor.png   (1º frame limpo de cada cena = imagem âncora)
  anchors/scene_NN_mid.png / _end.png  (para descrever o movimento)
  contact_sheet.jpg             (visão geral de todas as âncoras)
"""
import argparse, json, os, re, shutil, subprocess, sys

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def download(url, out):
    os.makedirs(out, exist_ok=True)
    tmpl = os.path.join(out, "video.%(ext)s")
    r = run(["yt-dlp", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "--write-info-json",
             "--write-subs", "--write-auto-subs", "--sub-langs", "all", "-o", tmpl, url])
    if r.returncode:
        sys.exit("FALHA no yt-dlp (rede bloqueada? atualize: pip install -U yt-dlp):\n" + r.stderr[-1500:])
    info = {}
    ij = os.path.join(out, "video.info.json")
    if os.path.exists(ij):
        d = json.load(open(ij))
        info = {k: d.get(k) for k in ("id", "title", "description", "uploader", "uploader_id",
                "duration", "width", "height", "fps", "view_count", "like_count", "comment_count",
                "upload_date", "track", "artist", "tags", "webpage_url")}
    json.dump(info, open(os.path.join(out, "meta.json"), "w"), ensure_ascii=False, indent=2)
    return os.path.join(out, "video.mp4")

def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
             "-of", "json", path])
    d = json.loads(r.stdout)
    dur = float(d["format"]["duration"])
    has_audio = any(s["codec_type"] == "audio" for s in d["streams"])
    return dur, has_audio

def scene_cuts(path, thr, dur, min_len=0.6):
    r = run(["ffmpeg", "-hide_banner", "-i", path, "-vf", f"select='gt(scene,{thr})',showinfo",
             "-an", "-f", "null", "-"])
    cuts = [float(m) for m in re.findall(r"pts_time:([0-9.]+)", r.stderr)]
    bounds, last = [0.0], 0.0
    for c in cuts:
        if c - last >= min_len and dur - c >= min_len:
            bounds.append(c); last = c
    bounds.append(dur)
    return [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]

def grab(path, t, out):
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", path,
         "-frames:v", "1", out])

def transcribe(path, model, lang):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None, "faster-whisper não instalado (pip install faster-whisper)"
    try:
        m = WhisperModel(model, device="cpu", compute_type="int8")
        segs, info = m.transcribe(path, language=None if lang == "auto" else lang,
                                  word_timestamps=True, vad_filter=True)
        out = []
        for s in segs:
            out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                        "words": [{"w": w.word, "start": round(w.start, 2), "end": round(w.end, 2)} for w in (s.words or [])]})
        return {"language": info.language, "segments": out}, None
    except Exception as e:
        return None, f"transcrição falhou (modelo não baixou? huggingface.co bloqueado?): {e}"

def contact_sheet(files, out, cols=4, w=270, h=480):
    inputs = []
    for f in files:
        inputs += ["-i", f]
    n = len(files)
    fc = "".join(f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
                 f"drawtext=text='{i+1}':x=6:y=6:fontsize=28:fontcolor=white:box=1:boxcolor=black@0.6[v{i}];" for i in range(n))
    if n == 1:
        fc = fc.rstrip(";").replace("[v0]", "[o]")
    else:
        layout = "|".join(f"{(i % cols) * w}_{(i // cols) * h}" for i in range(n))
        fc += "".join(f"[v{i}]" for i in range(n)) + f"xstack=inputs={n}:layout={layout}[o]"
    r = run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", fc,
             "-map", "[o]", "-frames:v", "1", "-q:v", "3", out])
    return r.returncode == 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--threshold", type=float, default=0.25)
    ap.add_argument("--model", default="small"); ap.add_argument("--lang", default="auto")
    ap.add_argument("--no-transcribe", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if os.path.isfile(a.src):
        video = os.path.join(a.out, "video.mp4"); shutil.copy(a.src, video)
    else:
        video = download(a.src, a.out)
    dur, has_audio = probe(video)
    scenes = scene_cuts(video, a.threshold, dur)
    ad = os.path.join(a.out, "anchors"); os.makedirs(ad, exist_ok=True)
    manifest = []
    for i, (s, e) in enumerate(scenes, 1):
        # âncora = 1º frame estável após o corte (pula ~0.12s de fusão/transição)
        ta = min(s + 0.12, e - 0.05) if i > 1 else 0.0
        files = {"anchor": (ta, f"scene_{i:02d}_anchor.png"),
                 "mid": ((s + e) / 2, f"scene_{i:02d}_mid.png"),
                 "end": (max(s, e - 0.15), f"scene_{i:02d}_end.png")}
        for _, (t, fn) in files.items():
            grab(video, t, os.path.join(ad, fn))
        manifest.append({"scene": i, "start": round(s, 2), "end": round(e, 2), "duration": round(e - s, 2),
                         "anchor_time": round(ta, 2), **{k: f"anchors/{fn}" for k, (_, fn) in files.items()}})
    tr, err = (None, "ignorado (--no-transcribe)") if a.no_transcribe or not has_audio else transcribe(video, a.model, a.lang)
    if not has_audio: err = "vídeo sem trilha de áudio"
    if tr:
        json.dump(tr, open(os.path.join(a.out, "transcript.json"), "w"), ensure_ascii=False, indent=2)
        with open(os.path.join(a.out, "transcript.txt"), "w") as f:
            for s in tr["segments"]:
                f.write(f"[{s['start']:06.2f} - {s['end']:06.2f}] {s['text']}\n")
        for sc in manifest:  # associa cada fala à cena em que ela começa
            sc["narration"] = " ".join(s["text"] for s in tr["segments"]
                                       if sc["start"] - 0.05 <= s["start"] < sc["end"] - 0.05 or
                                       (s["start"] < sc["start"] and s["end"] > sc["start"] + 0.5 and sc["scene"] == 1))
    sheet_ok = contact_sheet([os.path.join(ad, f"scene_{m['scene']:02d}_anchor.png") for m in manifest[:60]],
                             os.path.join(a.out, "contact_sheet.jpg"))
    res = {"video": video, "duration": round(dur, 2), "has_audio": has_audio, "scene_count": len(manifest),
           "threshold": a.threshold, "transcription_error": err, "contact_sheet": sheet_ok, "scenes": manifest}
    json.dump(res, open(os.path.join(a.out, "manifest.json"), "w"), ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in res.items() if k != "scenes"}, ensure_ascii=False, indent=2))
    print(f"{len(manifest)} cenas -> {a.out}/manifest.json")

if __name__ == "__main__":
    main()
