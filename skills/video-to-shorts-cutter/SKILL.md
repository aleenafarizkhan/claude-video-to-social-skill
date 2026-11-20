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
python scripts/shorts_cutter.py "https://youtu.be/VIDEO_ID" --transcript-only
python scripts/shorts_cutter.py "LOCAL_SOURCE_PATH" --transcript output/shorts-cutter/transcript.json --ranges output/shorts-cutter/ranges.json --mode character
python scripts/shorts_cutter.py "INPUT.mp4" --start 15 --end 42 --mode center
```

- Characters are not tracked by vision. Character mode uses a **fixed, adjustable left-biased crop**; check preview and adjust `--crop-x` to keep the subject visible. Source must be licensed/authorized for reuse; never bypass restrictions.
- The full-fill layout scales proportionally to cover 1080x1920 and clamps the horizontal crop to the available width. Source quality limits output fidelity.
- MP4 uses H.264 High@4.1, yuv420p, faststart and AAC 44.1kHz; output may fail if source has unsupported codecs/resolutions or installed FFmpeg lacks libass.
- Automatic mode yields 5 clips by default from a one-hour video. Each automatic or manual clip must be 20–55 seconds long. The default target is 35 seconds.
- Use the full-transcript review for automatic highlight jobs. Use `--start` and `--end` to cut a single specific moment.
- Use `--no-captions` to omit subtitles. Automatic selection with this flag uses unranked segments unless a transcript is supplied.
- Verify `manifest.json`, MP4 with `ffprobe`, and inspect crop before reporting success.

### Full-transcript review

1. Run the selected script with `--transcript-only`. It writes the full timestamped `transcript.json` and a `highlight-signals.json` file with audio loudness spikes and scene-change timestamps. Both use seconds from the start of the source.
2. Review the entire transcript with AI, from the first entry to the last, alongside the matching time ranges in `highlight-signals.json`. If the materials exceed the AI's context window, review every consecutive part with original timestamps and compare candidates across all parts before selecting. Use clustered spikes and cuts as clues for gameplay or action, and preview those moments in the source to confirm what happened before selecting them. Loudness alone cannot identify laughter or screams. Select five distinct, non-overlapping ranges for a one-hour video, each 20–55 seconds long, with enough context for the hook and payoff.
3. Save the selected ranges as a JSON array of objects with numeric `start` and `end` in seconds, such as `{"start": 128, "end": 165}`. Render from the reported local source with `--ranges` and `--transcript` so the exact selections and transcript are reused. If the transcript contains too little speech for five credible moments, use the video preview or user-supplied timestamps to complete the review.

### Caption language and text placement

- Produce one caption in the selected language. Supported choices are English, Roman Hindi, Roman Urdu, and Urdu script on explicit request. Otherwise use the supported spoken language with English as the fallback. Use Roman Hindi for spoken Hindi and Roman Urdu for spoken Urdu. Add relevant emojis to the post caption and keep on-video subtitles faithful to the speech.
- Use `--caption-style highlight` (the default) for yellow word-by-word emphasis, `--caption-style boxed` for green emphasis on a dark box, or `--caption-style classic` for static text. Keep each word's timestamp when editing the transcript and pass the edited transcript with `--transcript`.
- For Urdu script, keep words in natural reading order in UTF-8. Let libass shape the right-to-left text and verify letter joining, word order, and highlighted word timing in the rendered preview.
- Before burning subtitles, review the transcript and romanize the text while keeping the original timestamps. Review and update the manifest caption before handing off drafts or publishing.
- For a full-fill layout, preview representative frames across the entire clip. Choose a fixed position for a short, clip-specific hook in available space that stays clear of faces, gameplay HUD, key action, and subtitles while the hook is visible. Keep the text within the portrait frame's safe margins.
- For a blurred layout, fit the horizontal source in the center of the 1080×1920 canvas and fill the top and bottom with a blurred copy of the source. Put the hook in the upper blurred area and subtitles in the lower blurred area. Check readability and spacing in the rendered preview.
- If the bundled render command lacks the requested layout or text positioning, use it for clip selection and render the same time ranges from the source with FFmpeg and positioned ASS overlays. Verify the final MP4s and update the manifest before delivery.

## Posting (optional)
If user also requests publishing through Publora, follow the existing `skills/video-to-social/SKILL.md` Publora MCP flow, including draft-first, upload, media validation, and explicit authorization before scheduling or publishing. Do not claim auto-posting was completed until confirmed in Publora. Never invent API/tool names or fabricate a success status.
