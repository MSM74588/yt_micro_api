import subprocess
from fastapi import FastAPI, Query
from pydantic import BaseModel
from typing import Optional, List
import json
import datetime

app = FastAPI(
    title="YT-DLP micro API",
    docs_url="/",
    description="API to get Channel Details, Video Details and Playlist Details"
)



class VideoResponseModel(BaseModel):
    type: Optional[str]
    url: Optional[str]
    id: Optional[str]
    title: Optional[str]
    description: Optional[str]
    duration_ms: Optional[int]
    uploader: Optional[str]
    uploader_url: Optional[str]
    thumbnail: Optional[str]
    view_count: Optional[int]
    upload_date: Optional[str]
    

class PlaylistItem(BaseModel):
    url: Optional[str]
    title: Optional[str]
    description: Optional[str]
    duration_ms: Optional[int]
    

class PlaylistResponseModel(BaseModel):
    type: Optional[str]
    url: Optional[str]
    id: Optional[str]
    title: Optional[str]
    publisher: Optional[str]
    image: Optional[str]
    description: Optional[str]
    total_episodes: Optional[int]
    api_href: Optional[str]
    limit: Optional[int]
    next: Optional[int]
    offset: Optional[int]
    previous: Optional[int]
    total: Optional[int]
    items: Optional[List[PlaylistItem]]
    
class ChannelVideoItem(BaseModel):
    url: Optional[str]
    title: Optional[str]
    description: Optional[str] = None
    duration_ms: Optional[int] = None


class ChannelResponseModel(BaseModel):
    type: Optional[str]
    url: Optional[str]
    id: Optional[str]
    name: Optional[str]
    description: Optional[str]
    thumbnail: Optional[str]
    total_videos: Optional[int]
    items: Optional[List[ChannelVideoItem]]


@app.get("/ytdlp")
def getYTDLPinfo():
    """
    Returns useful yt-dlp information such as version, Python version, and update status.
    """
    try:
        # Get yt-dlp version
        version_cmd = ["yt-dlp", "--version"]
        version_result = subprocess.run(version_cmd, capture_output=True, text=True, check=True)
        version = version_result.stdout.strip()

        # Get full help output for available extractors/formats if needed
        extractor_cmd = ["yt-dlp", "--list-extractors"]
        extractor_result = subprocess.run(extractor_cmd, capture_output=True, text=True, check=True)
        extractors = extractor_result.stdout.strip().split("\n")
        
        return {
            "yt_dlp_version": version,
            "total_extractors": len(extractors),
        }

    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

@app.get("/ping")
def pong():
    return {
        "message" : "pong"
    }


@app.get("/flatlist", response_model=PlaylistResponseModel)
def getflatlistData(url: str = Query(..., description="YouTube playlist URL")):
    """
    Fetch playlist metadata fully but items in flatlist mode for speed.
    """
    print(f"[DEBUG] Fetching playlist metadata for: {url}")

    # 1️⃣ Fetch playlist metadata (no videos)
    meta_cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--playlist-items", "0",
        url
    ]
    try:
        meta_result = subprocess.run(meta_cmd, capture_output=True, text=True, check=True)
        meta_data = json.loads(meta_result.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

    # 2️⃣ Fetch flatlist items
    flat_cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        url
    ]
    try:
        flat_result = subprocess.run(flat_cmd, capture_output=True, text=True, check=True)
        flat_data = json.loads(flat_result.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

    # 3️⃣ Build PlaylistItem list (flat)
    items_list = [
        PlaylistItem(
            url=f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else None,
            title=entry.get("title"),
            description=None,
            duration_ms=None
        )
        for entry in flat_data.get("entries", [])
    ]

    # 4️⃣ Return combined metadata + items
    return PlaylistResponseModel(
        type="YouTube Playlist",
        url=url,
        id=meta_data.get("id"),
        title=meta_data.get("title"),
        publisher=meta_data.get("uploader"),
        image=meta_data.get("thumbnails", [{}])[-1].get("url"),
        description=meta_data.get("description"),
        total_episodes=len(items_list),
        api_href=f"/flatlist?url={url}",
        limit=len(items_list),
        next=None,
        offset=None,
        previous=None,
        total=len(items_list),
        items=items_list
    )


@app.get("/playlist", response_model=PlaylistResponseModel)
def getplaylistData(url: str = Query(..., description="YouTube playlist URL")):
    """
    Fetch playlist metadata + items using yt-dlp.
    Works for YouTube playlists and YouTube podcasts (same format).
    """
    print(f"[DEBUG] Running full playlist fetch for URL: {url}")

    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        url
    ]
    print(f"[DEBUG] Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("[DEBUG] Initial yt-dlp output received")
    except subprocess.CalledProcessError as e:
        print("[ERROR] yt-dlp failed")
        print(e.stderr.strip())
        return {"error": e.stderr.strip()}

    data = json.loads(result.stdout)
    print(f"[DEBUG] Playlist title: {data.get('title')}")
    print(f"[DEBUG] Number of flat entries: {len(data.get('entries', []))}")

    items_list = []
    for idx, entry in enumerate(data.get("entries", []), start=1):
        print(f"[DEBUG] Fetching full details for video {idx}/{len(data.get('entries', []))}: {entry.get('id')}")
        video_cmd = [
            "yt-dlp",
            "--dump-single-json",
            f"https://www.youtube.com/watch?v={entry['id']}"
        ]
        try:
            video_result = subprocess.run(video_cmd, capture_output=True, text=True, check=True)
            video_data = json.loads(video_result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] Failed to fetch video details for {entry.get('id')}")
            print(e.stderr.strip())
            continue

        items_list.append(
            PlaylistItem(
                url=f"https://www.youtube.com/watch?v={video_data.get('id')}",
                title=video_data.get("title", ""),
                description=video_data.get("description", ""),
                duration_ms=int(video_data.get("duration", 0) * 1000)
            )
        )

    return PlaylistResponseModel(
        type="YouTube Playlist",
        url=url,
        id=data.get("id", ""),
        title=data.get("title", ""),
        publisher=data.get("uploader", ""),
        image=data.get("thumbnails", [{}])[-1].get("url", ""),
        description=data.get("description", ""),
        total_episodes=len(items_list),
        api_href=f"/playlist?url={url}",
        limit=len(items_list),
        next=0,
        offset=0,
        previous=0,
        total=len(items_list),
        items=items_list
    )

@app.get("/video", response_model=VideoResponseModel)
def getVideoData(url: str = Query(..., description="YouTube video URL")):
    """
    Fetch details for a single YouTube video (no stream URL).
    """
    print(f"[DEBUG] Fetching video metadata for: {url}")

    cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--no-playlist",  # ensure only single video is fetched
        url
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

    # Convert YYYYMMDD to ISO date
    iso_date = None
    if data.get("upload_date"):
        try:
            iso_date = datetime.strptime(data["upload_date"], "%Y%m%d").date().isoformat()
        except ValueError:
            iso_date = None

    return VideoResponseModel(
        type="YouTube Video",
        url=url,
        id=data.get("id"),
        title=data.get("title"),
        description=data.get("description"),
        duration_ms=int(data.get("duration", 0) * 1000) if data.get("duration") else None,
        uploader=data.get("uploader"),
        uploader_url=data.get("uploader_url"),
        thumbnail=(data.get("thumbnails", [{}])[-1].get("url") if data.get("thumbnails") else None),
        view_count=data.get("view_count"),
        upload_date=iso_date
    )

@app.get("/channel", response_model=PlaylistResponseModel)
def get_channel_data(url: str = Query(..., description="YouTube channel URL")):
    """
    Fetch YouTube channel metadata and `long-form` videos only.
    Uses the channel's 'Uploads' playlist (no Shorts).
    """
    print(f"[DEBUG] Fetching channel metadata for: {url}")

    # 1️⃣ Get channel metadata (without fetching all videos)
    meta_cmd = [
        "yt-dlp",
        "--dump-single-json",
        "--playlist-items", "0",
        url
    ]
    try:
        meta_result = subprocess.run(meta_cmd, capture_output=True, text=True, check=True)
        meta_data = json.loads(meta_result.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

    # Extract channel ID
    channel_id = meta_data.get("channel_id") or meta_data.get("id")
    if not channel_id:
        return {"error": "Unable to fetch channel ID"}

    # 2️⃣ Build "Uploads" playlist ID for long-form videos
    uploads_playlist_id = f"UU{channel_id[2:]}"
    uploads_playlist_url = f"https://www.youtube.com/playlist?list={uploads_playlist_id}"

    print(f"[DEBUG] Fetching uploads playlist: {uploads_playlist_url}")

    # 3️⃣ Fetch flat list of videos (fast, no Shorts)
    flat_cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--dump-single-json",
        uploads_playlist_url
    ]
    try:
        flat_result = subprocess.run(flat_cmd, capture_output=True, text=True, check=True)
        flat_data = json.loads(flat_result.stdout)
    except subprocess.CalledProcessError as e:
        return {"error": e.stderr.strip()}

    # 4️⃣ Build video items
    items_list = [
        PlaylistItem(
            url=f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else None,
            title=entry.get("title"),
            description=None,
            duration_ms=None
        )
        for entry in flat_data.get("entries", [])
    ]

    # 5️⃣ Return channel metadata + videos
    return PlaylistResponseModel(
        type="YouTube Channel",
        url=url,
        id=channel_id,
        title=meta_data.get("channel"),
        publisher=meta_data.get("uploader"),
        image=meta_data.get("thumbnails", [{}])[-1].get("url"),
        description=meta_data.get("description"),
        total_episodes=len(items_list),
        api_href=f"/channel?url={url}",
        limit=len(items_list),
        next=None,
        offset=None,
        previous=None,
        total=len(items_list),
        items=items_list
    )
