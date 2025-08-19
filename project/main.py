import os
import uuid
import json
import zipfile
from fastapi import FastAPI, Form, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import yt_dlp

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DOWNLOAD_DIR = "downloads"
CACHE_FILE = "cache.json"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
if not os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "w") as f:
        json.dump({}, f)

def load_cache():
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/download")
async def download_video(
    urls: str = Form(...),
    quality: str = Form(...),
    only_audio: str = Form(default="off")
):
    url_list = urls.strip().splitlines()
    file_paths = []
    cache = load_cache()

    for url in url_list:
        url = url.strip()
        if url in cache and os.path.exists(cache[url]):
            file_paths.append(cache[url])
            continue

        uid = str(uuid.uuid4())
        output_template = os.path.join(DOWNLOAD_DIR, f"{uid}.%(ext)s")

        if only_audio == "on":
            ydl_opts = {
                "outtmpl": output_template,
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "quiet": True,
                "merge_output_format": "mp3",
            }
        else:
            ydl_opts = {
                "outtmpl": output_template,
                "format": f"bestvideo[height<={quality}]+bestaudio/best",
                "quiet": True,
            }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)

            if only_audio == "on":
                filename = os.path.splitext(filename)[0] + ".mp3"

        if not os.path.exists(filename):

            print(f"Error: File not found after download: {filename}")
            raise RuntimeError(f"File not found: {filename}")

        cache[url] = filename
        file_paths.append(filename)

    save_cache(cache)

    if len(file_paths) == 1:
        return FileResponse(
            file_paths[0],
            filename=os.path.basename(file_paths[0]),
            media_type="application/octet-stream"
        )

    zip_path = os.path.join(DOWNLOAD_DIR, f"package_{uuid.uuid4().hex}.zip")
    with zipfile.ZipFile(zip_path, "w") as z:
        for path in file_paths:
            z.write(path, arcname=os.path.basename(path))

    return FileResponse(zip_path, filename="downloaded_videos.zip", media_type="application/zip")
