# Video to Social — Claude Code Plugin

**Author:** aleenafarizkhan

A standalone Claude Code plugin for turning authorized videos into captioned short-form clips and managing publishing workflows through Publora MCP. This is an independent project and is not affiliated with Publora.

## Choose your skill

Both skills are installed side-by-side and work independently:

| Skill | When to use | Command |
| --- | --- | --- |
| `video-to-social` | General Shorts + captions + optional Publora drafts/posts | `python scripts/pipeline.py ...` |
| `video-to-shorts-cutter` | Gameplay-focused full-screen crop with adjustable character offset, no blur, optional hook and captions | `python scripts/shorts_cutter.py ...` |

Choose explicitly in Claude Code: **“Use video-to-shorts-cutter”** or **“Use video-to-social”**. Use Publora publishing instructions from `video-to-social` for either skill when requested and authorized.

Example cutter commands:
```bash
python scripts/shorts_cutter.py "my-gameplay.mp4" --start 20 --end 50 --mode character --crop-x 300 --hook "EPIC MOMENT"
python scripts/shorts_cutter.py "https://youtu.be/VIDEO_ID" --count 3 --mode character
```

The cutter's crop offset is static, not AI character tracking; verify framing on every source.

## Features
- Paste an authorized public YouTube URL or a local video path
- Whisper speech transcription with word timestamps
- Heuristic highlight detection and candidate ranking
- 1080×1920 9:16 FFmpeg center-crop exports with burned subtitles
- Manifest with clip timestamps, rough hooks and captions
- Claude Code skill orchestrates draft / upload / scheduling via the **official hosted Publora MCP**
- Default **review first**; no unapproved automatic publishing

## Prerequisites
Python 3.10+, FFmpeg/ffprobe and a Publora account with social connections. `yt-dlp` can only fetch content allowed by platform access and terms. First Whisper model run downloads weights; internet is necessary. Performance depends on hardware, language, video resolution and link availability.

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows PowerShell:
# .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
ffmpeg -version
claude mcp add --transport http --scope user publora https://mcp.publora.com/mcp
# In Claude Code use /mcp -> publora -> Authenticate
```

Install as a Claude Code plugin from a locally available marketplace directory:
```text
/plugin marketplace add /absolute/path/to/video-to-social-skill
/plugin install video-to-social@video-to-social-marketplace
```
Or put the `skills/video-to-social/SKILL.md` skill into your Claude Code project skills directory and ask Claude to use it.

## Run just the local pipeline
```bash
python scripts/pipeline.py 'https://youtu.be/VIDEO_ID' --output output/demo --count 3 --clip-length 35
python scripts/pipeline.py '/path/to/owned-video.mp4' --output output/demo
```

Produced: `output/demo/manifest.json`, `transcript.json`, `clip_01.mp4` … and ASS subtitle files. The pipeline itself **does not publish**; Claude Code uses the skill to run Publora MCP after rendering. Ask Claude: **“Use video-to-social to create three captioned Shorts from this authorized link, review and save Publora drafts for my YouTube and Instagram connections.”**

## Posting steps (Publora)
Claude must run `account_context` → `list_connections` → `create_post` (draft, one per clip with idempotency key) → `get_upload_url` → presigned PUT via `scripts/upload_signed.py` → `complete_media` → `get_post` → (if authorized) `update_post` → `get_post`. Posting is asynchronous; the final status must be verified. The `.mcp.json` contains the OAuth URL without secrets.

## Limits & security
- Downloading, subtitle generation and upload require a working network and correct third-party services. A successful render does not guarantee social publishing.
- Automatic highlight score uses transcript features; no video-vision AI or guaranteed virality.
- Center crop may cut out off-center subjects. Review clips before posting.
- Only use content for which you have rights to edit and repost.
- Never commit API keys, private presigned URLs, user source files or video outputs.

Documentation: https://docs.publora.com/mcp/client-setup and https://docs.publora.com/mcp/tools-reference
