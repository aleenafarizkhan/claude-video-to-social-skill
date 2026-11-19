#!/usr/bin/env python3
"""Upload a local file to a Publora presigned URL; never print secrets."""
import argparse
import sys
from pathlib import Path
from urllib.parse import urlsplit
import httpx

def upload(file: Path, url: str):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("An HTTPS presigned upload URL is required")
    if not file.is_file():
        raise FileNotFoundError(file)
    with file.open("rb") as f, httpx.Client(timeout=300, follow_redirects=False) as client:
        response = client.put(url, content=f, headers={"Content-Type":"video/mp4"})
        if response.status_code not in (200, 201, 204):
            raise RuntimeError(f"Upload rejected with HTTP {response.status_code}; check signed URL expiry and content type")
    print("Upload completed. Call Publora MCP complete_media with the mediaId.")

if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("url", help="Presigned URL from Publora get_upload_url (do not share)")
    a=parser.parse_args()
    try: upload(Path(a.file),a.url)
    except Exception as e:
        print(f"Upload failed: {type(e).__name__}: {e}",file=sys.stderr)
        sys.exit(1)
