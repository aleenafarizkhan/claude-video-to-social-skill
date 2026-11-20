#!/usr/bin/env python3
"""YouTube/local video -> speech-ranked 9:16 subtitled clips + Publora manifests."""
from __future__ import annotations
import argparse
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from bisect import bisect_left, bisect_right
from pathlib import Path
from urllib.parse import urlparse

EXCITING = {"wow", "amazing", "crazy", "unbelievable", "insane", "look", "watch", "what", "why", "how", "secret", "best", "never", "finally", "oh", "no", "yes", "whoa", "incredible", "funny", "listen", "important", "wait"}
DEFAULT_CLIP_COUNT = 5
MIN_CLIP_LENGTH = 20
MAX_CLIP_LENGTH = 55
CAPTION_STYLES = {
    "classic": (64, 1, 4, None),
    "highlight": (64, 1, 4, "&H00FFFF&"),
    "boxed": (68, 3, 8, "&H90FF90&"),
}

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

def candidates(words: list[dict], video_duration: float, clip_length: int | None, count: int):
    video_duration = int(video_duration * 1000) / 1000
    target = clip_length or 35
    starts = {0.0, max(0.0, video_duration - target)}
    words = sorted(words, key=lambda word: word["start"])
    word_starts = [word["start"] for word in words]
    word_ends = sorted({word["end"] for word in words})
    phrase_ends = []
    if clip_length is None and words:
        starts = {words[0]["start"]}
        for word, following in zip(words, words[1:]):
            if word["end"] <= following["start"] and (
                word["text"].rstrip('\"\u201d\u2019)').endswith((".", "!", "?", "।", "؟", "۔"))
                or following["start"] - word["end"] >= 0.4
            ):
                phrase_ends.append(word["end"])
                starts.add(following["start"])
        phrase_ends = sorted({*phrase_ends, words[-1]["end"]})
    else:
        starts.update(float(i) for i in range(0, int(video_duration), max(5, target // 4)))

    def end_for(start):
        ideal = min(video_duration, start + target)
        if clip_length is None:
            lower = round(start + MIN_CLIP_LENGTH, 3)
            upper = min(video_duration, round(start + MAX_CLIP_LENGTH, 3))
            for boundaries in (phrase_ends, word_ends):
                options = boundaries[bisect_left(boundaries, lower):bisect_right(boundaries, upper)]
                if options:
                    return min(options, key=lambda end: abs(end - ideal))
        return ideal

    pool = []
    for start in sorted(starts):
        end = end_for(start)
        if round(end - start, 3) < MIN_CLIP_LENGTH:
            continue
        selection = words[bisect_left(word_starts, start):bisect_left(word_starts, end)]
        if not selection:
            continue
        tokens = [re.sub(r"[^\w]", "", w["text"].lower()) for w in selection]
        rate = len(tokens) / max(1, end-start)
        excitement = sum(t in EXCITING for t in tokens)
        punctuation = sum(w["text"].endswith(("!", "?")) for w in selection)
        score = min(rate, 3.6)*2 + excitement*2.5 + punctuation*1.8 + min(len(tokens), 35)*0.02
        pool.append({"start": round(start, 3), "end": round(end, 3), "score": round(score, 2)})
    pool.sort(key=lambda x: x["score"], reverse=True)
    selected = []
    for c in pool:
        if all(max(0, min(c["end"], o["end"])-max(c["start"], o["start"])) < .2 * min(c["end"]-c["start"], o["end"]-o["start"]) for o in selected):
            selected.append(c)
            if len(selected) == count:
                break
    # Fill any remaining slots when speech is sparse or absent.
    for start in range(0, int(video_duration) - MIN_CLIP_LENGTH + 1, target):
        if len(selected) == count:
            break
        end = round(end_for(start), 3)
        if all(end <= clip["start"] or start >= clip["end"] for clip in selected):
            selected.append({"start": start, "end": end, "score": 0})
    return sorted(selected, key=lambda x: x["start"])


def signal_measurements(video: Path, stream: str, filters: str, metric: str):
    mapping, filter_option = ("0:v:0", "-vf") if stream == "video" else ("0:a:0", "-af")
    output = command(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
                      "-map", mapping, filter_option, filters, "-f", "null", "-"], capture=True)
    timestamp = None
    for line in output.splitlines():
        if match := re.search(r"\bpts_time:(\S+)", line):
            timestamp = float(match[1])
        elif timestamp is not None and line.startswith(metric + "="):
            yield timestamp, float(line.split("=", 1)[1])


def highlight_signals(video: Path, duration: float):
    scene_metric = "lavfi.scene_score"
    scenes = signal_measurements(
        video, "video",
        "scale=320:-2,select='gt(scene,0.35)',metadata=mode=print:file=-", scene_metric,
    )
    scene_changes = [{"time": round(time, 3), "score": round(score, 3)}
                     for time, score in scenes if 0 <= time < duration]

    audio_metric = "lavfi.astats.Overall.RMS_level"
    audio_stream = command(["ffprobe", "-v", "error", "-select_streams", "a:0",
                            "-show_entries", "stream=index", "-of", "csv=p=0", str(video)], capture=True)
    spikes = []
    if audio_stream.strip():
        levels = [(time, level) for time, level in signal_measurements(
            video, "audio", "aresample=8000,asetnsamples=n=4000:p=0,"
            "astats=metadata=1:reset=1:measure_perchannel=none:measure_overall=RMS_level,"
            f"ametadata=mode=print:key={audio_metric}:file=-", audio_metric,
        ) if 0 <= time < duration and level <= 0]
        if levels:
            baseline = sorted(level for _, level in levels)[len(levels) // 2]
            threshold = max(-45, baseline + 6)
            for time, level in levels:
                if level < threshold:
                    continue
                spike = {"time": round(time, 3), "rms_dbfs": round(level, 2)}
                if not spikes or time - spikes[-1]["time"] >= 2:
                    spikes.append(spike)
                elif spike["rms_dbfs"] > spikes[-1]["rms_dbfs"]:
                    spikes[-1] = spike
    return {"scene_changes": scene_changes, "audio_spikes": spikes}


def prepare_transcript(video, duration, words, language, out):
    transcript = out / "transcript.json"
    transcript.write_text(json.dumps(words, indent=2, ensure_ascii=False), encoding="utf-8")
    signals = out / "highlight-signals.json"
    signals.write_text(json.dumps(highlight_signals(video, duration), indent=2), encoding="utf-8")
    print(json.dumps({"video": str(video), "video_seconds": duration,
                      "language": language, "transcript": str(transcript),
                      "highlight_signals": str(signals)}, indent=2))


def reviewed_ranges(path, duration, count):
    ranges = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(ranges, list) or len(ranges) != count:
        raise ValueError(f"Ranges must be a JSON list of exactly {count} clips")
    picks = []
    for index, clip in enumerate(ranges, 1):
        if not isinstance(clip, dict) or any(type(clip.get(key)) not in (int, float) for key in ("start", "end")):
            raise ValueError(f"Range {index} needs numeric start and end in seconds")
        start, end = clip["start"], clip["end"]
        if not 0 <= start < end <= duration or not MIN_CLIP_LENGTH <= round(end - start, 3) <= MAX_CLIP_LENGTH:
            raise ValueError(f"Range {index} must be within the source and {MIN_CLIP_LENGTH}-{MAX_CLIP_LENGTH} seconds long")
        picks.append({"start": start, "end": end, "score": None})
    picks.sort(key=lambda clip: clip["start"])
    if any(first["end"] > second["start"] for first, second in zip(picks, picks[1:])):
        raise ValueError("Reviewed ranges must not overlap")
    return picks

def ass_timestamp(seconds: float):
    cs = round(seconds*100)
    return f"{cs//360000}:{(cs//6000)%60:02}:{(cs//100)%60:02}.{cs%100:02}"

def ass_escape(s: str):
    return s.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")

def write_ass(words: list[dict], start: float, end: float, path: Path, style: str = "classic"):
    size, border_style, outline, highlight = CAPTION_STYLES[style]
    subset = [w for w in words if start <= w["start"] < end]
    # Use libass whole-line bidirectional layout for RTL text with inline colors.
    encoding = -1 if any(unicodedata.bidirectional(char) in ("R", "AL")
                         for word in subset for char in word["text"]) else 1
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{size},&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,{border_style},{outline},1,2,72,72,260,{encoding}
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Keep the phrase on screen while changing the active word's color.
    lines = []
    for k in range(0, len(subset), 4):
        chunk = subset[k:k+4]
        s = max(0, chunk[0]["start"]-start)
        e = min(end-start, max(s+.25, chunk[-1]["end"]-start))
        if k + 4 < len(subset):
            e = min(e, subset[k + 4]["start"] - start)
        phrase = [ass_escape(word["text"]) for word in chunk]
        plain = " ".join(phrase)
        if highlight is None:
            append_caption_event(lines, s, e, plain)
            continue
        cursor = s
        for index, word in enumerate(chunk):
            onset = min(e, max(cursor, word["start"] - start))
            next_start = chunk[index + 1]["start"] - start if index + 1 < len(chunk) else e
            offset = max(onset, min(e, next_start, word["end"] - start))
            append_caption_event(lines, cursor, onset, plain)
            active = phrase.copy()
            active[index] = r"{\1c" + highlight + "}" + phrase[index] + r"{\1c}"
            append_caption_event(lines, onset, offset, " ".join(active))
            cursor = offset
        append_caption_event(lines, cursor, e, plain)
    path.write_text(header + "".join(lines), encoding="utf-8")


def append_caption_event(lines: list[str], start: float, end: float, text: str):
    if round(start * 100) < round(end * 100):
        lines.append(f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},Default,,0,0,0,,{text}\n")

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
    if duration < MIN_CLIP_LENGTH:
        raise ValueError(f"Video must be at least {MIN_CLIP_LENGTH} seconds long")
    if args.transcript:
        words = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
        language = args.language or "unknown"
    else:
        words, language = transcribe(video, args.model, args.language)
    if args.transcript_only:
        prepare_transcript(video, duration, words, language, out)
        return
    (out/"transcript.json").write_text(json.dumps(words, indent=2, ensure_ascii=False), encoding="utf-8")
    picks = (reviewed_ranges(args.ranges, duration, args.count) if args.ranges
             else candidates(words, duration, args.clip_length, args.count))
    if not picks:
        raise RuntimeError("No usable moments found")
    manifest = {"source":args.video,"language":language,"video_seconds":duration,"clips":[]}
    for i, p in enumerate(picks, 1):
        stem = f"clip_{i:02d}"
        ass = out/(stem+".ass"); mp4 = out/(stem+".mp4")
        if words:
            write_ass(words, p["start"], p["end"], ass, args.caption_style)
        export_clip(video, p["start"], p["end"], ass, mp4)
        manifest["clips"].append({"file":mp4.name,"start":p["start"],"end":p["end"],"rank_score":p["score"],"caption":make_caption(words,p["start"],p["end"],args.video),"status":"ready_for_review"})
    (out/"manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"output":str(out),"manifest":str(out/"manifest.json"),"clips":len(picks)}, indent=2))

def cli():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", help="YouTube HTTPS URL or local video path")
    p.add_argument("--output", default="output")
    p.add_argument("--count", type=int, default=DEFAULT_CLIP_COUNT)
    p.add_argument("--clip-length", type=int, help="Fixed target length in seconds; omit for speech-aware cuts")
    p.add_argument("--model", default="small", help="Faster Whisper model")
    p.add_argument("--language", default=None)
    p.add_argument("--transcript", default=None, help="Optional words JSON, for offline tests")
    p.add_argument("--caption-style", choices=CAPTION_STYLES, default="highlight")
    selection = p.add_mutually_exclusive_group()
    selection.add_argument("--transcript-only", action="store_true", help="Write the full transcript and highlight signals without rendering")
    selection.add_argument("--ranges", help="JSON file of reviewed start/end ranges in seconds")
    args=p.parse_args()
    if not 1 <= args.count <= 20 or (args.clip_length is not None and not MIN_CLIP_LENGTH <= args.clip_length <= MAX_CLIP_LENGTH):
        p.error(f"--count 1-20 and --clip-length {MIN_CLIP_LENGTH}-{MAX_CLIP_LENGTH} required")
    try: run(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr); sys.exit(1)

if __name__ == "__main__":cli()
