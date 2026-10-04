import os
import sys
import json
import time
import shutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from job_pipeline import create_job, analyze_video_job, extract_job_speaker, JOBS_DIR

app = FastAPI(title="ReAV-TSE Multi-Job API", description="Dynamic Audio-Visual Target Speaker Extraction Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
SAMPLE_VIDEO_PATH = BASE_DIR / "test_videos" / "test.mp4"

ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}

class AnalyzeRequest(BaseModel):
    job_id: str

class ExtractJobRequest(BaseModel):
    job_id: str
    target: str
    mode: str = "person"

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "ReAV-TSE Multi-Job", "timestamp": time.time()}

@app.post("/api/upload")
async def upload_video(file: UploadFile = None, use_sample: bool = False):
    """Generates unique job_id and initializes a clean, isolated job workspace."""
    if use_sample:
        if not SAMPLE_VIDEO_PATH.exists():
            raise HTTPException(status_code=404, detail="Sample video not found on server")
        job_id = create_job(SAMPLE_VIDEO_PATH, is_sample=True)
        return {
            "status": "uploaded",
            "job_id": job_id,
            "filename": "test.mp4",
            "video_url": f"/api/jobs/{job_id}/video"
        }

    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No video file uploaded. Please select a video file.")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_VIDEO_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed video formats: {', '.join(sorted(ALLOWED_VIDEO_EXTS))}."
        )

    # Temporary save
    temp_dir = BASE_DIR / "test_videos" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"upload_{int(time.time())}_{file.filename}"
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if temp_file.stat().st_size == 0:
        temp_file.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="The uploaded file is empty (0 bytes).")

    job_id = create_job(temp_file, is_sample=False)
    return {
        "status": "uploaded",
        "job_id": job_id,
        "filename": file.filename,
        "video_url": f"/api/jobs/{job_id}/video"
    }

@app.post("/api/analyze")
def analyze_video(req: AnalyzeRequest):
    """Runs fresh face detection, tracking, thumbnail generation, and speaker clustering for the specific job."""
    if not req.job_id or not (JOBS_DIR / req.job_id).exists():
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found.")
    try:
        data = analyze_video_job(req.job_id)
        return data
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Analyze Error] {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.get("/api/jobs/latest")
def get_latest_job():
    if not JOBS_DIR.exists():
        return {"job_id": None}
    jobs = [p for p in JOBS_DIR.iterdir() if p.is_dir() and (p / "speakers.json").exists()]
    if not jobs:
        return {"job_id": None}
    latest_job = max(jobs, key=lambda p: (p / "speakers.json").stat().st_mtime)
    with open(latest_job / "speakers.json", "r") as f:
        speakers = json.load(f)
    return {
        "job_id": latest_job.name,
        "video_url": f"/api/jobs/{latest_job.name}/video",
        "speakers": speakers
    }

@app.get("/api/jobs/{job_id}/speakers")
def get_job_speakers(job_id: str):
    job_dir = JOBS_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    speakers_file = job_dir / "speakers.json"
    if not speakers_file.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' has not been analyzed yet")
    with open(speakers_file, "r") as f:
        data = json.load(f)
    return data

@app.get("/api/jobs/{job_id}/status")
def get_job_status(job_id: str):
    job_dir = JOBS_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    status_file = job_dir / "status.json"
    if not status_file.exists():
        return {
            "job_id": job_id,
            "stage": "pending",
            "message": "Initializing workspace...",
            "progress": 0.05
        }
    with open(status_file, "r") as f:
        return json.load(f)

@app.get("/api/jobs/{job_id}/video")
def get_job_video(job_id: str):
    video_path = JOBS_DIR / job_id / "video.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found")
    return FileResponse(video_path, media_type="video/mp4")

@app.get("/api/jobs/{job_id}/audio/original")
def get_job_original_audio(job_id: str):
    audio_path = JOBS_DIR / job_id / "audio.wav"
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Original audio not found")
    return FileResponse(audio_path, media_type="audio/wav")

@app.get("/api/jobs/{job_id}/thumbnails/{filename}")
def get_job_thumbnail(job_id: str, filename: str):
    thumb_path = JOBS_DIR / job_id / "thumbnails" / filename
    if not thumb_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    response = FileResponse(thumb_path, media_type="image/jpeg")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.post("/api/extract")
def extract_speaker(req: ExtractJobRequest):
    """Extracts target speaker audio specifically for this job."""
    job_dir = JOBS_DIR / req.job_id
    if not req.job_id or not job_dir.exists():
        raise HTTPException(status_code=404, detail=f"Job '{req.job_id}' not found.")
    speakers_file = job_dir / "speakers.json"
    if not speakers_file.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Video analysis has not been performed for job '{req.job_id}'. Please run analysis first."
        )
    try:
        report = extract_job_speaker(req.job_id, req.target, req.mode)
        target_clean = req.target.strip().lower()
        return {
            "status": "success",
            "job_id": req.job_id,
            "targetId": req.target,
            "targetName": report.get("target_name", req.target),
            "audioUrl": f"/api/jobs/{req.job_id}/audio/target?person={target_clean}&t={int(time.time()*1000)}",
            "downloadUrl": f"/api/jobs/{req.job_id}/audio/download?person={target_clean}",
            "report": report
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[Extract Error] {e}", file=sys.stderr)
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")

@app.get("/api/jobs/{job_id}/audio/target")
def get_job_target_audio(job_id: str, person: str = "person1"):
    clean_p = person.strip().lower()
    target_path = JOBS_DIR / job_id / f"target_speaker_{clean_p}.wav"
    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"Target speaker audio not found for {person}")
    response = FileResponse(target_path, media_type="audio/wav")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

@app.get("/api/jobs/{job_id}/audio/download")
def download_job_target_audio(job_id: str, person: str = "person1"):
    clean_p = person.strip().lower()
    target_path = JOBS_DIR / job_id / f"target_speaker_{clean_p}.wav"
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Target speaker audio not found")
    return FileResponse(
        target_path,
        media_type="audio/wav",
        filename=f"ReAV_TSE_{job_id}_{clean_p}.wav"
    )

@app.get("/api/audio/target")
def get_legacy_target_audio(person: str = "person1"):
    latest = get_latest_job()
    if not latest.get("job_id"):
        raise HTTPException(status_code=404, detail="No active jobs found")
    return get_job_target_audio(latest["job_id"], person)

@app.get("/api/audio/download")
def get_legacy_download_audio(person: str = "person1"):
    latest = get_latest_job()
    if not latest.get("job_id"):
        raise HTTPException(status_code=404, detail="No active jobs found")
    return download_job_target_audio(latest["job_id"], person)

@app.get("/api/audio/original")
def get_legacy_original_audio():
    latest = get_latest_job()
    if not latest.get("job_id"):
        raise HTTPException(status_code=404, detail="No active jobs found")
    return get_job_original_audio(latest["job_id"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)
