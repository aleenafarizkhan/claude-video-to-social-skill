---
name: video-to-shorts-cutter
description: Convert authorized wide gameplay or livestream video into 9:16 Shorts with a full-fill crop or blurred top and bottom, with optional speech subtitles and a hook.
---

# Video to Shorts Cutter

**Author:** aleenafarizkhan

This is an **independent, opt-in skill** alongside `video-to-social`. Do not silently choose it when the user explicitly selected the other skill. Ask which mode if ambiguous.

## Use cases
- `video-to-shorts-cutter`: 1080x1920 gameplay clips with a left-offset or centered full-fill crop, or a centered source with blurred top and bottom.
- `video-to-social`: general centered clips + transcript-based selection + Publora publishing workflow.

## Cutter usage

Use one skill and one 9:16 layout for each source video. Apply the selected skill and layout to every Short from that source, from the first frame to the last. Switch skill or layout only when the user explicitly asks, and apply the change only to the clips or time ranges they specify.

From plugin root:
```bash
python scripts/shorts_cutter.py "INPUT.mp4" --start 15 --end 42 --mode character --crop-x 300 --hook "EPIC GAMEPLAY"
python scripts/shorts_cutter.py "https://youtu.be/VIDEO_ID" --count 5 --clip-length 35 --mode character
python scripts/shorts_cutter.py "INPUT.mp4" --start 15 --end 42 --mode center
```

- Characters are not tracked by vision. Character mode uses a **fixed, adjustable left-biased crop**; check preview and adjust `--crop-x` to keep the subject visible. Source must be licensed/authorized for reuse; never bypass restrictions.
- The full-fill layout scales proportionally to cover 1080x1920 and clamps the horizontal crop to the available width. Source quality limits output fidelity.
- MP4 uses H.264 High@4.1, yuv420p, faststart and AAC 44.1kHz; output may fail if source has unsupported codecs/resolutions or installed FFmpeg lacks libass.
- Automatic mode yields 5 clips by default from a one-hour video. Each automatic or manual clip must be 20–55 seconds long. The default target is 35 seconds.
- Automatic mode ranks moments using speech and fills any remaining slots with unranked segments. Use `--start` and `--end` to cut a single specific moment.
- Use `--no-captions` to omit subtitles. Automatic selection with this flag uses unranked segments unless a transcript is supplied.
- Verify `manifest.json`, MP4 with `ffprobe`, and inspect crop before reporting success.

### Caption language and text placement

- Produce one caption in the selected language. Supported languages are English, Roman Hindi, and Roman Urdu. Honor an explicit language choice. Otherwise use the spoken language for the clip if supported, with English as the fallback. For spoken Hindi, automatically use Roman Hindi. For spoken Urdu, use Roman Urdu. Write Hindi and Urdu in Latin letters in captions, hooks, and subtitles. Add relevant emojis to the post caption and keep on-video subtitles faithful to the speech.
- Before burning subtitles, review the transcript and romanize the text while keeping the original timestamps. Review and update the manifest caption before handing off drafts or publishing.
- For a full-fill layout, preview representative frames across the entire clip. Choose a fixed position for a short, clip-specific hook in available space that stays clear of faces, gameplay HUD, key action, and subtitles while the hook is visible. Keep the text within the portrait frame's safe margins.
- For a blurred layout, fit the horizontal source in the center of the 1080×1920 canvas and fill the top and bottom with a blurred copy of the source. Put the hook in the upper blurred area and subtitles in the lower blurred area. Check readability and spacing in the rendered preview.
- If the bundled render command lacks the requested layout or text positioning, use it for clip selection and render the same time ranges from the source with FFmpeg and positioned ASS overlays. Verify the final MP4s and update the manifest before delivery.

## Posting (optional)
If user also requests publishing through Publora, follow the existing `skills/video-to-social/SKILL.md` Publora MCP flow, including draft-first, upload, media validation, and explicit authorization before scheduling or publishing. Do not claim auto-posting was completed until confirmed in Publora. Never invent API/tool names or fabricate a success status.
