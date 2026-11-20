---
name: video-to-shorts-cutter
description: Convert authorized wide gameplay or livestream video into full-screen 9:16 character-locked Shorts without blurred borders; optionally burn speech subtitles, add top hook and prepare clips for Publora MCP.
---

# Video to Shorts Cutter

**Author:** aleenafarizkhan

This is an **independent, opt-in skill** alongside `video-to-social`. Do not silently choose it when the user explicitly selected the other skill. Ask which mode if ambiguous.

## Use cases
- `video-to-shorts-cutter`: full-screen 1080x1920 gameplay crops, left-offset framing, no blurred borders, optional title, MP4 output.
- `video-to-social`: general centered clips + transcript-based selection + Publora publishing workflow.

## Cutter usage
From plugin root:
```bash
python scripts/shorts_cutter.py "INPUT.mp4" --start 15 --end 42 --mode character --crop-x 300 --hook "EPIC GAMEPLAY"
python scripts/shorts_cutter.py "https://youtu.be/VIDEO_ID" --count 5 --clip-length 35 --mode character
python scripts/shorts_cutter.py "INPUT.mp4" --start 15 --end 42 --mode center
```

- Characters are not tracked by vision. Character mode uses a **fixed, adjustable left-biased crop**; check preview and adjust `--crop-x` to keep the subject visible. Source must be licensed/authorized for reuse; never bypass restrictions.
- Crop scales proportionally to cover 1080x1920, crops at x=max 0/min(requested x, available width) and adds **no blurred bars**. Source quality limits output fidelity.
- MP4 uses H.264 High@4.1, yuv420p, faststart and AAC 44.1kHz; output may fail if source has unsupported codecs/resolutions or installed FFmpeg lacks libass.
- Automatic mode yields 5 clips by default from a one-hour video. Each automatic or manual clip must be 20–55 seconds long. The default target is 35 seconds.
- Automatic mode ranks moments using speech and fills any remaining slots with unranked segments. Use `--start` and `--end` to cut a single specific moment.
- Use `--no-captions` to omit subtitles. Automatic selection with this flag uses unranked segments unless a transcript is supplied.
- Top hook is rendered as a libass overlay, not an external background or font-file dependency.
- Verify `manifest.json`, MP4 with `ffprobe`, and inspect crop before reporting success.

## Posting (optional)
If user also requests publishing through Publora, follow the existing `skills/video-to-social/SKILL.md` Publora MCP flow, including draft-first, upload, media validation, and explicit authorization before scheduling or publishing. Do not claim auto-posting was completed until confirmed in Publora. Never invent API/tool names or fabricate a success status.
