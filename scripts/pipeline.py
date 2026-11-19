#!/usr/bin/env python3
"""YouTube/local video -> speech-ranked 9:16 subtitled clips + Publora manifests."""
from __future__ import annotations
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

EXCITING = {"wow", "amazing", "crazy", "unbelievable", "insane", "look", "watch", "what", "why", "how", "secret", "best", "never", "finally", "oh", "no", "yes", "whoa", "incredible", "funny", "listen", "important", "wait"}

def command(args: list[str], capture=False, cwd=None):
    p = subprocess.run(args, text=True, stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None, cwd=cwd)
    if p.returncode:
        raise RuntimeError(f"Command failed: {args[0]} ({p.stderr[-1500:] if capture else 'see above'})")
    return p.stdout if capture else ""

def ensure_binary(name: str):
    if not shutil.which(name):
        raise RuntimeError(f"Required executable not found: {name}. Install it and add it to PATH.")

def valid_youtube(url: str):
    u = urlparse(url)
    return u.scheme == "https" and (u.hostname or "").lower() in {"youtu.be", "youtube.com", "www.youtube.com", "m.youtube.com"}

def duration_of(path: Path):
    data = json.loads(command(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)], capture=True))
    return float(data["format"]["duration"])

def input_video(value: str, out: Path):
    p = Path(value).expanduser()
    if p.is_file():
        return p.resolve()
    if not valid_youtube(value):
        raise ValueError("Provide an existing local video file or a public HTTPS YouTube URL.")
    ensure_binary("yt-dlp")
    path_template = str(out / "source.%(ext)s")
    command(["yt-dlp", "--no-playlist", "--restrict-filenames", "--max-filesize", "2G", "-f", "bv*+ba/b", "--merge-output-format", "mp4", "-o", path_template, value])
    files = [p for p in out.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not files:
        raise RuntimeError("yt-dlp did not produce a video. Check availability, access rights and format support.")
    return max(files, key=lambda p: p.stat().st_size)

def transcribe(path: Path, model: str, language: str | None):
    try:
        from faster_whisper import WhisperModel
    except ImportError as ex:
        raise RuntimeError("Install dependencies with pip install -r requirements.txt") from ex
    speech_model = WhisperModel(model, device="cpu", compute_type="int8")
    segs, info = speech_model.transcribe(str(path), language=language, vad_filter=True, word_timestamps=True, beam_size=5)
    words = []
    for seg in segs:
        if seg.words:
            for w in seg.words:
                if w.word.strip():
                    words.append({"start": round(float(w.start), 3), "end": round(float(w.end), 3), "text": w.word.strip()})
        elif seg.text.strip():
            words.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()})
    return words, info.language

def candidates(words: list[dict], video_duration: float, clip_length: int, count: int):
    if not words:
        return [{"start": round(min(i*clip_length, max(0,video_duration-clip_length)), 2), "end": round(min(video_duration, (i+1)*clip_length),2), "score": 0} for i in range(min(count, max(1, math.ceil(video_duration/clip_length))))]
    step = max(5, clip_length//4)
    starts = {0.0, max(0.0, video_duration-clip_length)}
    starts.update(float(i) for i in range(0, int(video_duration), step))
    # sentence starts are more natural cut points than fixed windows
    starts.update(max(0, w["start"]-0.3) for w in words if w["text"][:1].isupper())
    pool = []
    for start in sorted(starts):
        end = min(video_duration, start+clip_length)
        if end-start < min(8, video_duration*.8):
            continue
        selection = [w for w in words if w["start"] >= start and w["start"] < end]
        if not selection:
            continue
        tokens = [re.sub(r"[^\w]", "", w["text"].lower()) for w in selection]
        rate = len(tokens) / max(1, end-start)
        excitement = sum(t in EXCITING for t in tokens)
        punctuation = sum(w["text"].endswith(("!", "?")) for w in selection)
        score = min(rate, 3.6)*2 + excitement*2.5 + punctuation*1.8 + min(len(tokens), 35)*0.02
        pool.append({"start": round(start, 2), "end": round(end, 2), "score": round(score, 2)})
    pool.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for c in pool:
        if all(max(0, min(c["end"], o["end"])-max(c["start"], o["start"])) < .2 * min(c["end"]-c["start"], o["end"]-o["start"]) for o in selected):
            selected.append(c)
            if len(selected) == count:
                break
    return sorted(selected, key=lambda x: x["start"])

def ass_timestamp(seconds: float):
    cs = round(seconds*100)
    return f"{cs//360000}:{(cs//6000)%60:02}:{(cs//100)%60:02}.{cs%100:02}"

def ass_escape(s: str):
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")

def write_ass(words: list[dict], start: float, end: float, path: Path):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,64,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,72,72,260,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    subset = [w for w in words if start <= w["start"] < end]
    # Group 3-5 words per subtitle for readability.
    lines = []
    for k in range(0, len(subset), 4):
        chunk = subset[k:k+4]
        s = max(0, chunk[0]["start"]-start)
        e = min(end-start, max(s+.25, chunk[-1]["end"]-start))
        content = ass_escape(" ".join(w["text"] for w in chunk))
        lines.append(f"Dialogue: 0,{ass_timestamp(s)},{ass_timestamp(e)},Default,,0,0,0,,{content}\n")
    path.write_text(header + "".join(lines), encoding="utf-8")

def export_clip(source: Path, start: float, end: float, ass: Path, dest: Path):
    # Use a stable portrait frame with centered smart-safe crop (no stretched aspect ratio).
    filt = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1"
    # Relative ASS file path and cwd avoid escaping FFmpeg special characters in Windows paths.
    vf = filt + f",subtitles={ass.name}" if ass.exists() else filt
    command(["ffmpeg", "-nostdin", "-y", "-ss", f"{start:.3f}", "-i", str(source), "-t", f"{end-start:.3f}", "-vf", vf, "-map", "0:v:0", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dest)], cwd=ass.parent)

def make_caption(words, start, end, source_url):
    chosen = [w["text"] for w in words if start <= w["start"] < end]
    hook = " ".join(chosen[:11]).strip(" ,.!?")
    if not hook:
        hook = "Watch this moment"
    text = (hook[:115] + ("..." if len(hook)>115 else ""))
    return f"{text}\n\nHighlights from the original video.\nSource: {source_url}"[:2000]

def run(args):
    ensure_binary("ffmpeg")
    ensure_binary("ffprobe")
    out = Path(args.output).resolve(); out.mkdir(parents=True, exist_ok=True)
    video = input_video(args.video, out)
    duration = duration_of(video)
    if duration < 4:
        raise ValueError("Video must be at least 4 seconds long")
    if args.transcript:
        words = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
        language = args.language or "unknown"
    else:
        words, language = transcribe(video, args.model, args.language)
    (out/"transcript.json").write_text(json.dumps(words, indent=2, ensure_ascii=False), encoding="utf-8")
    picks = candidates(words, duration, args.clip_length, args.count)
    if not picks:
        raise RuntimeError("No usable moments found")
    manifest = {"source":args.video,"language":language,"video_seconds":duration,"clips":[]}
    for i, p in enumerate(picks, 1):
        stem = f"clip_{i:02d}"
        ass = out/(stem+".ass"); mp4 = out/(stem+".mp4")
        if words:
            write_ass(words, p["start"], p["end"], ass)
        export_clip(video, p["start"], p["end"], ass, mp4)
        manifest["clips"].append({"file":mp4.name,"start":p["start"],"end":p["end"],"rank_score":p["score"],"caption":make_caption(words,p["start"],p["end"],args.video),"status":"ready_for_review"})
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output":str(out),"manifest":str(out/"manifest.json"),"clips":len(picks)}, indent=2))

def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", help="YouTube HTTPS URL or local video path")
    p.add_argument("--output", default="output")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--clip-length", type=int, default=35)
    p.add_argument("--model", default="small", help="Faster Whisper model")
    p.add_argument("--language", default=None)
    p.add_argument("--transcript", default=None, help="Optional words JSON, for offline tests")
    args=p.parse_args()
    if not 1 <= args.count <= 20 or not 8 <= args.clip_length <= 180:
        p.error("--count 1-20 and --clip-length 8-180 required")
    try: run(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":cli()
