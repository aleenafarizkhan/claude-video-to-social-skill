#!/usr/bin/env python3
"""Off-center fullscreen 9:16 cutter for authorized gameplay and other video."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from pipeline import command, ensure_binary, duration_of, input_video, transcribe, candidates, write_ass, make_caption


def crop_filter(mode: str, x: int) -> str:
    """Scale to fill, then choose the left-biased or centered horizontal crop.

    Uses expressions that adapt to input resolution, preserving aspect ratio.
    """
    if mode not in ("character", "center"):
        raise ValueError("mode must be character or center")
    if x < 0:
        raise ValueError("crop-x must be nonnegative")
    # Scale to cover 1080x1920, force even dimensions for H.264.
    scale = "scale=1080:1920:force_original_aspect_ratio=increase:force_divisible_by=2"
    horizontal = f"min({x}\\,iw-1080)" if mode == "character" else "(iw-1080)/2"
    return f"{scale},crop=1080:1920:{horizontal}:(ih-1920)/2,setsar=1"


def hook_ass(path: Path, text: str, duration: float):
    """Render safe, escaped, upper-area hook via libass instead of drawtext path quoting."""
    from pipeline import ass_timestamp, ass_escape
    safe = ass_escape(re.sub(r"\s+", " ", text).strip())[:110]
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hook,Arial,55,&H00000000,&H00000000,&H00000000,&H0000FFFF,-1,0,0,0,100,100,0,0,3,0,0,8,50,50,245,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    path.write_text(header + f"Dialogue: 0,0:00:00.00,{ass_timestamp(min(duration, 4.0))},Hook,,0,0,0,,{safe}\n", encoding="utf-8")


def render(source: Path, start: float, end: float, dest: Path, *, mode="character", crop_x=300,
           captions: Path | None = None, hook: Path | None = None):
    vf = crop_filter(mode, crop_x)
    # Working directory contains .ass files: no absolute-path escaping issues on Windows.
    for path in (captions, hook):
        if path and path.exists():
            vf += f",subtitles={path.name}"
    command(["ffmpeg", "-nostdin", "-y", "-ss", f"{start:.3f}", "-i", str(source),
             "-t", f"{end-start:.3f}", "-vf", vf, "-map", "0:v:0", "-map", "0:a?",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
             "-profile:v", "high", "-level:v", "4.1", "-movflags", "+faststart",
             "-c:a", "aac", "-b:a", "128k", "-ar", "44100", str(dest)], cwd=dest.parent)


def run(a):
    ensure_binary("ffmpeg"); ensure_binary("ffprobe")
    out = Path(a.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    video = input_video(a.video, out)
    duration = duration_of(video)
    if duration < 4:
        raise ValueError("Source video must be at least 4 seconds")
    if a.start is not None:
        if a.start < 0 or a.start >= duration:
            raise ValueError("--start outside source duration")
        if a.end is not None and (a.end <= a.start or a.end > duration):
            raise ValueError("--end must be greater than --start and within source duration")
        picks = [{"start": a.start, "end": min(a.end or a.start + a.clip_length, duration), "score": None}]
    else:
        if a.transcript:
            words = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
        elif a.no_captions:
            raise ValueError("Automatic highlight selection needs speech: supply --start or remove --no-captions")
        else:
            words, _ = transcribe(video, a.model, a.language)
        picks = candidates(words, duration, a.clip_length, a.count)
    if a.no_captions:
        words = []
    elif a.transcript:
        words = json.loads(Path(a.transcript).read_text(encoding="utf-8"))
    elif a.start is not None:
        words, _ = transcribe(video, a.model, a.language)
    manifest = {"source": a.video, "skill": "video-to-shorts-cutter", "mode": a.mode, "crop_x": a.crop_x, "clips": []}
    for i, p in enumerate(picks, 1):
        stem = f"short_{i:02d}"
        subtitles = out / (stem + ".ass")
        hookfile = out / (stem + "_hook.ass")
        if words:
            write_ass(words, p["start"], p["end"], subtitles)
        if a.hook:
            hook_ass(hookfile, a.hook, p["end"] - p["start"])
        output = out / (stem + ".mp4")
        render(video, p["start"], p["end"], output, mode=a.mode, crop_x=a.crop_x,
               captions=subtitles if words else None, hook=hookfile if a.hook else None)
        manifest["clips"].append({"file": output.name, "start": p["start"], "end": p["end"],
                                   "score": p["score"], "caption": make_caption(words, p["start"], p["end"], a.video),
                                   "status": "ready_for_review"})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"manifest": str(out / "manifest.json"), "clips": len(picks)}, indent=2))


def cli():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", help="Authorized HTTPS YouTube URL or local video")
    p.add_argument("--output", default="output/shorts-cutter")
    p.add_argument("--mode", choices=["character", "center"], default="character")
    p.add_argument("--crop-x", type=int, default=300, help="horizontal pixel offset after scaling; character mode only")
    p.add_argument("--start", type=float, help="start time in seconds; skips automatic moment ranking")
    p.add_argument("--end", type=float, help="end time in seconds")
    p.add_argument("--count", type=int, default=3)
    p.add_argument("--clip-length", type=int, default=35)
    p.add_argument("--hook", help="optional top hook text")
    p.add_argument("--no-captions", action="store_true", help="render silent/no subtitle text; use with --start")
    p.add_argument("--transcript", help="optional existing word-level transcript JSON")
    p.add_argument("--model", default="small")
    p.add_argument("--language", default=None)
    a = p.parse_args()
    if not 1 <= a.count <= 20 or not 8 <= a.clip_length <= 180 or a.crop_x < 0 or (a.end is not None and a.start is None):
        p.error("count must be 1–20; clip-length 8–180; crop-x >= 0; --end needs --start")
    try:
        run(a)
    except (ValueError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    cli()
