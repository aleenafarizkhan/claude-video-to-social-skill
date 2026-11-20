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

1. Accept YouTube HTTPS URL or a local video file. Invoke from plugin root:
   `python scripts/pipeline.py 'VIDEO_URL' --output output/job-name --count 5 --clip-length 35`
   By default, a one-hour video yields 5 clips. Each clip is 20–55 seconds long, with a default target of 35 seconds. If there are too few speech-ranked moments, the pipeline fills the remaining slots with unranked segments.
   The pipeline uses faster-whisper word timestamps and a heuristic speech/excitement score (not a guaranteed viral classifier), FFmpeg portrait crop and burned-in ASS subtitles.
2. Open `manifest.json`; inspect file existence, rendered durations, speech and crop, and adjust errors before showing selected clips to the user. Candidate ranking is heuristic; do not describe it as objective virality prediction.
3. Create platform-tailored text and hashtags after reviewing the transcript. Keep source credit. Use `manifest.json` captions as starting drafts, not final optimization.
4. Check Publora MCP `account_context` and `list_connections` for quotas and authorized connection IDs. Never invent a connection ID. Use **the hosted Publora MCP tools**, not an imaginary REST endpoint.
5. For **each** clip, call Publora `create_post` with `content`, `platforms` (actual connection IDs), and `idempotencyKey` — omit `scheduledTime` and `publishNow` initially to create a draft. Save `postGroupId` in the job state.
6. Call `get_upload_url` with `postGroupId`, clip filename, `contentType: video/mp4`, `type: video`. Upload actual bytes to the returned signed URL using `python scripts/upload_signed.py CLIP_PATH URL` without logging or storing the URL. Then call `complete_media` with the returned `mediaId`. If upload fails, do not call `complete_media`, schedule or publish. Inspect `get_post` and clean the pending media slot (`delete_media`) if the user authorizes it; otherwise provide the editor URL for manual remediation.
7. Call `get_post` and verify the media is attached and processing/validation complete. Use `update_post` to schedule (`scheduledTime` with ISO 8601 UTC and `status: scheduled`) or `publishNow: true` **only when explicitly authorized**. For TikTok/YouTube/Instagram, include appropriate `platformSettings`, e.g. YouTube title/privacy and Instagram `videoType: REELS`. Use settings documented in https://docs.publora.com/mcp/tools-reference .
8. Call `get_post` again and report the actual draft/scheduled/publishing status and IDs; "publishNow" is asynchronous, not proof of publication. Record status in a local `publora-results.json`. Check duplicate risks before retries; reuse original idempotency keys.

## Tools and recovery
- MCP setup: `claude mcp add --transport http --scope user publora https://mcp.publora.com/mcp` then `/mcp` -> Authenticate. Do not commit tokens.
- Publora tool names: `account_context`, `list_connections`, `create_post`, `get_upload_url`, `complete_media`, `get_post`, `update_post`.
- If no audio/transcript, allow manual review; never fabricate spoken subtitles. Pipeline can render a plain crop without subtitles only if transcript is empty.
- If download is blocked, ask for a video file; never claim that clips were generated.
- Never use copyrighted music not licensed by the user or platform; avoid third-party videos without reuse rights.
- Large rendered videos use disk space; delete only files for the current job with user approval.
