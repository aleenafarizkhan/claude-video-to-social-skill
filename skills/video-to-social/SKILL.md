---
name: video-to-social
description: Generate ranked short-form video clips, burn captions, and draft/schedule/publish them via Publora MCP from a user-provided YouTube link or local video. Use when the user requests video clipping, subtitles, Shorts, Reels, TikTok, or cross-posting.
---

# Video to Social — Claude Code skill

Author: aleenafarizkhan

## Preconditions
- Require the user to own or have explicit permission to reuse and redistribute the input content; respect platform terms. Never bypass login, DRM, age or geographic restrictions.
- Verify `ffmpeg`, `ffprobe`, `yt-dlp`, Python dependencies and Publora MCP connection.
- Ask for target platform/account and schedule if not already specified. Never assume which account to use.
- Default to review/draft only; **do not publish or schedule without clear authorization**. A request to auto-post constitutes authorization only if targets, cadence and access have been specified.

## Workflow

Use one skill and one 9:16 layout for each source video. Apply the selected skill and layout to every Short from that source, from the first frame to the last. Switch skill or layout only when the user explicitly asks, and apply the change only to the clips or time ranges they specify.

1. Accept a YouTube HTTPS URL or a local video file. Follow the full-transcript review below to select moments, then render the selected ranges.
2. Open `manifest.json`; inspect file existence, rendered durations, speech and crop, and adjust errors before showing selected clips to the user. Candidate ranking is heuristic; do not describe it as objective virality prediction.
3. Create platform-tailored text and hashtags after reviewing the transcript. Keep source credit. Use `manifest.json` captions as starting drafts, not final optimization.
4. Check Publora MCP `account_context` and `list_connections` for quotas and authorized connection IDs. Never invent a connection ID. Use **the hosted Publora MCP tools**, not an imaginary REST endpoint.
5. For **each** clip, call Publora `create_post` with `content`, `platforms` (actual connection IDs), and `idempotencyKey` — omit `scheduledTime` and `publishNow` initially to create a draft. Save `postGroupId` in the job state.
6. Call `get_upload_url` with `postGroupId`, clip filename, `contentType: video/mp4`, `type: video`. Upload actual bytes to the returned signed URL using `python scripts/upload_signed.py CLIP_PATH URL` without logging or storing the URL. Then call `complete_media` with the returned `mediaId`. If upload fails, do not call `complete_media`, schedule or publish. Inspect `get_post` and clean the pending media slot (`delete_media`) if the user authorizes it; otherwise provide the editor URL for manual remediation.
7. Call `get_post` and verify the media is attached and processing/validation complete. Use `update_post` to schedule (`scheduledTime` with ISO 8601 UTC and `status: scheduled`) or `publishNow: true` **only when explicitly authorized**. For TikTok/YouTube/Instagram, include appropriate `platformSettings`, e.g. YouTube title/privacy and Instagram `videoType: REELS`. Use settings documented in https://docs.publora.com/mcp/tools-reference .
8. Call `get_post` again and report the actual draft/scheduled/publishing status and IDs; "publishNow" is asynchronous, not proof of publication. Record status in a local `publora-results.json`. Check duplicate risks before retries; reuse original idempotency keys.

### Full-transcript review

Choose each range's duration independently within 20–55 seconds. Start before the first spoken word of the selected thought and end after its last word and payoff. Prefer a sentence boundary or natural pause at both cuts. If the thought cannot fit, choose another moment. Preview the opening and ending audio before final delivery.

1. Run the selected script with `--transcript-only`. It writes the full timestamped `transcript.json` and a `highlight-signals.json` file with audio loudness spikes and scene-change timestamps. Both use seconds from the start of the source.
2. Review the entire transcript with AI, from the first entry to the last, alongside the matching time ranges in `highlight-signals.json`. If the materials exceed the AI's context window, review every consecutive part with original timestamps and compare candidates across all parts before selecting. Use clustered spikes and cuts as clues for gameplay or action, and preview those moments in the source to confirm what happened before selecting them. Loudness alone cannot identify laughter or screams. Select five distinct, non-overlapping ranges for a one-hour video, each 20–55 seconds long, with enough context for the hook and payoff.
3. Save the selected ranges as a JSON array of objects with numeric `start` and `end` in seconds, such as `{"start": 128, "end": 165}`. Render from the reported local source with `--ranges` and `--transcript` so the exact selections and transcript are reused. If the transcript contains too little speech for five credible moments, use the video preview or user-supplied timestamps to complete the review.

```bash
python scripts/pipeline.py "VIDEO_URL" --output output/job-name --transcript-only
python scripts/pipeline.py "LOCAL_SOURCE_PATH" --output output/job-name --transcript output/job-name/transcript.json --ranges output/job-name/ranges.json
```

### Caption language and text placement

- Produce one caption in the selected language. Supported choices are English, Roman Hindi, Roman Urdu, and Urdu script on explicit request. Otherwise use the supported spoken language with English as the fallback. Use Roman Hindi for spoken Hindi and Roman Urdu for spoken Urdu. Add relevant emojis to the post caption and keep on-video subtitles faithful to the speech.
- Use `--caption-style highlight` (the default) for yellow word-by-word emphasis, `--caption-style boxed` for green emphasis on a dark box, or `--caption-style classic` for static text. Keep each word's timestamp when editing the transcript and pass the edited transcript with `--transcript`.
- For Urdu script, keep words in natural reading order in UTF-8. Let libass shape the right-to-left text and verify letter joining, word order, and highlighted word timing in the rendered preview.
- Before burning subtitles, review the transcript and romanize the text while keeping the original timestamps. Review and update the manifest caption before handing off drafts or publishing.
- For a full-fill layout, preview representative frames across the entire clip. Choose a fixed position for a short, clip-specific hook in available space that stays clear of faces, gameplay HUD, key action, and subtitles while the hook is visible. Keep the text within the portrait frame's safe margins.
- For a blurred layout, fit the horizontal source in the center of the 1080×1920 canvas and fill the top and bottom with a blurred copy of the source. Put the hook in the upper blurred area and subtitles in the lower blurred area. Check readability and spacing in the rendered preview.
- If the bundled render command lacks the requested layout or text positioning, use it for clip selection and render the same time ranges from the source with FFmpeg and positioned ASS overlays. Verify the final MP4s and update the manifest before delivery.

## Tools and recovery
- MCP setup: `claude mcp add --transport http --scope user publora https://mcp.publora.com/mcp` then `/mcp` -> Authenticate. Do not commit tokens.
- Publora tool names: `account_context`, `list_connections`, `create_post`, `get_upload_url`, `complete_media`, `get_post`, `update_post`.
- If no audio/transcript, allow manual review; never fabricate spoken subtitles. Pipeline can render a plain crop without subtitles only if transcript is empty.
- If download is blocked, ask for a video file; never claim that clips were generated.
- Never use copyrighted music not licensed by the user or platform; avoid third-party videos without reuse rights.
- Large rendered videos use disk space; delete only files for the current job with user approval.
