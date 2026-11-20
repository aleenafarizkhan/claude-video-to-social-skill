---
name: stream-split-screen
description: Stack a stream recording and a second video in one vertical 9:16 export. Use when the stream should be above or below the other video and the other video's full frame must stay visible.
---

# Stream Split Screen

Use authorized sources. Identify which is the stream and which is the main video. If the user supplies one recording with an embedded facecam, extract that facecam for the stream panel and use the recording for the main panel. Honor the requested placement. If unspecified, put the stream on top. Use the same panel order throughout the export.

Keep the full main-video frame visible at its original proportions. Fit each input into its panel using scale and padding. Use two equal panels by default. Check any requested unequal split against face, HUD, and subtitle readability.

## Facecam quality and hook

- For an authorized YouTube source, use free `yt-dlp` to download the selected excerpt at the highest accessible resolution that improves the facecam, preferably 1440p or higher. Use `--download-sections "*START-END"` with timestamps in seconds. If the top rendition fails, try the next available resolution through normal public access. Use `ffprobe` to verify the actual source dimensions.
- In FFmpeg, measure and crop the facecam from that high-resolution excerpt before scaling. Preserve its aspect ratio, use Lanczos scaling, and apply mild brightness or sharpening only if the preview benefits.
- If the original facecam is also visible in the main panel, mask the duplicate in that panel with FFmpeg `delogo` or a localized blur. The original footage hidden behind the facecam cannot be recovered from a composite source.
- For this facecam-plus-gameplay layout, put the fitted panels directly against each other and fill remaining space above and below with a blurred extension of the adjacent video. Keep the main frame and HUD visible.
- Add a short, clip-specific hook in the upper safe area clear of the facecam and HUD. Burn it in using FFmpeg with an ASS overlay at 1080×1920. Set its dialogue start to zero and its end to the full export duration so it stays visible through the last frame. Check both the opening and final frame.

Use stream audio by default, or main-video audio when requested. Mix both only when requested. Align the starts unless offsets are supplied. For a paired excerpt, stop at the end of the shorter selected range. If the user wants the entire main video and the stream ends first, keep the main video playing and leave the stream panel black for the remaining time. Loop or freeze the stream only if requested.

## Render

For two local files and stream on top, run this single-line FFmpeg command. The stream is input 0 and the main video is input 1. Replace `30` in `-t 30` with the intended duration in seconds, based on the selected video ranges.

```text
ffmpeg -i "stream.mp4" -i "main-video.mp4" -filter_complex "[0:v]setpts=PTS-STARTPTS,fps=30,scale=1080:960:force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1,pad=1080:960:(ow-iw)/2:(oh-ih)/2,format=yuv420p[stream];[1:v]setpts=PTS-STARTPTS,fps=30,scale=1080:960:force_original_aspect_ratio=decrease:force_divisible_by=2:reset_sar=1,pad=1080:960:(ow-iw)/2:(oh-ih)/2,format=yuv420p[main];[stream][main]vstack=inputs=2:shortest=1[v]" -map "[v]" -map "0:a:0?" -af apad -t 30 -c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart "split-screen.mp4"
```

- For stream on bottom, change the stack inputs to `[main][stream]`. For main-video audio, map `1:a:0?`.
- For the full main video with a shorter stream, add `tpad=stop_mode=add:stop=-1:color=black` immediately before the `[stream]` output label. The main panel then controls the stack duration.
- Add captions only when requested. Place them within the panel whose audio they transcribe, with clearance for faces, original subtitles, and HUD.

Use `ffprobe` to verify 1080×1920, the chosen audio track, and the expected duration. Preview the beginning, middle, and end to check panel order, full-frame visibility, and synchronization. Return the MP4 for review.
