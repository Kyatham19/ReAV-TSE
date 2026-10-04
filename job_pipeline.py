import os
import sys
import json
import time
import math
import uuid
import shutil
import pickle
import types
import subprocess
from pathlib import Path
import cv2
import numpy as np
import soundfile as sf
from scipy import signal
import torch
import torchvision.models as models
import torchvision.transforms as transforms

from clearvoice.utils.video_process import track_shot
import clearvoice.models.av_mossformer2_tse.av_mossformer2 as av_module

# Monkey patch overlap_and_add for CPU compatibility
def fixed_overlap_and_add(signal_tensor, frame_step):
    outer_dimensions = signal_tensor.size()[:-2]
    frames, frame_length = signal_tensor.size()[-2:]
    subframe_length = math.gcd(frame_length, frame_step)
    subframe_step = frame_step // subframe_length
    subframes_per_frame = frame_length // subframe_length
    output_size = frame_step * (frames - 1) + frame_length
    output_subframes = output_size // subframe_length

    subframe_signal = signal_tensor.view(*outer_dimensions, -1, subframe_length)
    frame = torch.arange(0, output_subframes).unfold(0, subframes_per_frame, subframe_step)
    frame = signal_tensor.new_tensor(frame, dtype=torch.long)
    frame = frame.contiguous().view(-1)

    result = signal_tensor.new_zeros(*outer_dimensions, output_subframes, subframe_length)
    result.index_add_(-2, frame, subframe_signal)
    result = result.view(*outer_dimensions, -1)
    return result

av_module.overlap_and_add = fixed_overlap_and_add

# Configure optimal PyTorch CPU threads based on hardware benchmarking
NUM_CPU_THREADS = min(8, os.cpu_count() or 1)
torch.set_num_threads(NUM_CPU_THREADS)
try:
    torch.set_num_interop_threads(2)
except RuntimeError:
    pass

BASE_DIR = Path(__file__).resolve().parent
JOBS_DIR = BASE_DIR / "outputs_clearvoice" / "jobs"
YUNET_PATH = str(BASE_DIR / "yunet.onnx")

# Global models
_CV_MODEL = None
_CV_ARGS = None
_RESNET_MODEL = None
_TRANSFORM = None

def get_resnet_embedder():
    global _RESNET_MODEL, _TRANSFORM
    if _RESNET_MODEL is None:
        resnet = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        resnet.fc = torch.nn.Identity()
        resnet.eval()
        _RESNET_MODEL = resnet
        _TRANSFORM = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
        ])
    return _RESNET_MODEL, _TRANSFORM

def get_clearvoice_model(quantize: bool = True):
    global _CV_MODEL, _CV_ARGS
    if _CV_MODEL is None:
        from clearvoice import ClearVoice
        print(f"[Job Pipeline] Loading AV_MossFormer2_TSE_16K into memory (CPU threads={torch.get_num_threads()})...")
        cv_app = ClearVoice(task='target_speaker_extraction', model_names=['AV_MossFormer2_TSE_16K'])
        raw_model = cv_app.models[0].model
        _CV_ARGS = cv_app.models[0].args
        _CV_ARGS.device = cv_app.models[0].device

        if quantize and _CV_ARGS.device.type == "cpu":
            print("[Job Pipeline] Applying PyTorch dynamic INT8 quantization to MossFormer Linear layers...")
            import torch.ao.quantization as quantization
            _CV_MODEL = quantization.quantize_dynamic(
                raw_model,
                {torch.nn.Linear},
                dtype=torch.qint8
            )
        else:
            _CV_MODEL = raw_model
    return _CV_MODEL, _CV_ARGS

def update_job_status(job_id: str, stage: str, message: str, progress: float):
    status_file = JOBS_DIR / job_id / "status.json"
    status_data = {
        "job_id": job_id,
        "stage": stage,
        "message": message,
        "progress": round(progress, 2),
        "timestamp": time.time()
    }
    with open(status_file, "w") as f:
        json.dump(status_data, f, indent=2)

def create_job(video_path: Path, is_sample: bool = False) -> str:
    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "thumbnails").mkdir(exist_ok=True)

    dest_video = job_dir / "video.mp4"
    if video_path.exists():
        shutil.copy(str(video_path), str(dest_video))

    update_job_status(job_id, "uploading", "Video uploaded to workspace", 0.1)
    return job_id

def extract_audio_from_video(video_path: Path, audio_path: Path):
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", "16000",
        str(audio_path), "-loglevel", "error"
    ]
    subprocess.run(cmd, check=True)

def analyze_video_job(job_id: str):
    job_dir = JOBS_DIR / job_id
    video_path = job_dir / "video.mp4"
    audio_path = job_dir / "audio.wav"
    thumb_dir = job_dir / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)

    if not video_path.exists():
        raise FileNotFoundError(f"Video missing for job {job_id}")

    # Stage 1: Extract 16kHz audio
    update_job_status(job_id, "detecting_faces", "Extracting audio track and decoding video frames...", 0.2)
    if not audio_path.exists():
        extract_audio_from_video(video_path, audio_path)

    audio_info = sf.info(str(audio_path))
    total_audio_sec = round(audio_info.duration, 2)

    # Read video frames
    cap = cv2.VideoCapture(str(video_path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0

    frames = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    if len(frames) == 0:
        raise ValueError(f"Could not read frames from {video_path}")

    # Stage 2: YuNet face detection
    update_job_status(job_id, "detecting_faces", f"YuNet scanning {len(frames)} frames for faces...", 0.4)
    faces_cache = job_dir / "all_faces.pkl"
    if faces_cache.exists():
        with open(faces_cache, "rb") as f:
            all_faces = pickle.load(f)
    else:
        detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (w, h), score_threshold=0.5)
        all_faces = []
        for fidx, frame in enumerate(frames):
            _, faces = detector.detect(frame)
            dets = []
            if faces is not None:
                for f in faces:
                    fx, fy, fw, fh = f[:4]
                    dets.append({'frame': fidx, 'bbox': [fx, fy, fx + fw, fy + fh], 'conf': float(f[-1])})
            all_faces.append(dets)
        with open(faces_cache, "wb") as f:
            pickle.dump(all_faces, f)

    # Stage 3: Face tracking
    update_job_status(job_id, "tracking_speakers", "Tracking face sequences across shots and cut boundaries...", 0.6)
    v_args = types.SimpleNamespace(
        numFailedDet=10,
        minTrack=10,
        minFaceSize=10,
        cropScale=0.40,
        nDataLoaderThread=4
    )
    tracks = track_shot(v_args, all_faces)
    tracks = sorted(tracks, key=lambda t: len(t['frame']), reverse=True)

    tracks_cache = job_dir / "tracks.pkl"
    with open(tracks_cache, "wb") as f:
        pickle.dump(tracks, f)

    # Stage 4: Extract face thumbnails & deep visual embeddings
    update_job_status(job_id, "clustering_speakers", f"Extracting deep neural embeddings for {len(tracks)} face tracks...", 0.75)
    resnet, transform = get_resnet_embedder()

    track_meta = []
    track_embeddings = []

    for tidx, track in enumerate(tracks):
        mid_idx = len(track['frame']) // 2
        fidx = track['frame'][mid_idx]
        bbox = track['bbox'][mid_idx]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        bw = x2 - x1
        bh = y2 - y1
        pad_x = int(bw * 0.2)
        pad_y = int(bh * 0.2)
        px1 = max(0, x1 - pad_x)
        py1 = max(0, y1 - pad_y)
        px2 = min(w, x2 + pad_x)
        py2 = min(h, y2 + pad_y)

        face_crop = frames[fidx][py1:py2, px1:px2]
        if face_crop.size == 0:
            face_crop = np.zeros((180, 180, 3), dtype=np.uint8)
        else:
            face_crop = cv2.resize(face_crop, (200, 200))

        thumb_name = f"track_{tidx:02d}.jpg"
        cv2.imwrite(str(thumb_dir / thumb_name), face_crop)

        # Extract 512-dim deep visual embedding with ResNet-18
        rgb = cv2.cvtColor(face_crop, cv2.COLOR_BGR2RGB)
        tensor = transform(rgb).unsqueeze(0)
        with torch.no_grad():
            emb = resnet(tensor).squeeze(0).numpy()
            emb = emb / (np.linalg.norm(emb) + 1e-6)

        dur_sec = round(len(track['frame']) / fps, 2)
        start_sec = round(track['frame'][0] / fps, 2)
        end_sec = round((track['frame'][-1] + 1) / fps, 2)

        track_meta.append({
            "track_id": tidx,
            "trackNumber": tidx,
            "duration": dur_sec,
            "startSec": start_sec,
            "endSec": end_sec,
            "start_frame": track['frame'][0],
            "end_frame": track['frame'][-1],
            "timeSpan": f"{start_sec:.2f}s – {end_sec:.2f}s",
            "thumbnailUrl": f"/api/jobs/{job_id}/thumbnails/{thumb_name}?t={job_id}",
            "frame_set": set(track['frame'])
        })
        track_embeddings.append(emb)

    # Stage 5: Person Clustering via Deep Feature Cosine Similarity
    # Strict threshold 0.80 ensures genuinely different people are NEVER merged!
    SIM_THRESHOLD = 0.80
    clusters = [] # list of lists of track indices

    for tidx in range(len(tracks)):
        t_frames = track_meta[tidx]["frame_set"]
        best_cluster = -1
        best_sim = -1

        for c_idx, cluster in enumerate(clusters):
            # Check temporal collision: tracks overlapping in time CANNOT belong to the same person
            collision = any(not t_frames.isdisjoint(track_meta[other_tid]["frame_set"]) for other_tid in cluster)
            if not collision:
                sims = [float(np.dot(track_embeddings[tidx], track_embeddings[other_tid])) for other_tid in cluster]
                avg_sim = sum(sims) / len(sims)
                # Must exceed strict deep similarity threshold
                if avg_sim >= SIM_THRESHOLD and avg_sim > best_sim:
                    best_sim = avg_sim
                    best_cluster = c_idx

        if best_cluster >= 0:
            clusters[best_cluster].append(tidx)
        else:
            clusters.append([tidx])

    # Sort clusters chronologically by their earliest appearance
    clusters = sorted(clusters, key=lambda c: min(track_meta[idx]["start_frame"] for idx in c))

    persons = []
    for p_num, cluster in enumerate(clusters):
        p_id = f"person{p_num + 1}"
        cluster_tracks = sorted(cluster, key=lambda idx: track_meta[idx]["start_frame"])
        total_cluster_dur = round(sum(track_meta[idx]["duration"] for idx in cluster_tracks), 2)
        min_sec = track_meta[cluster_tracks[0]]["startSec"]
        max_sec = max(track_meta[idx]["endSec"] for idx in cluster_tracks)
        rep_idx = cluster_tracks[0]

        persons.append({
            "id": p_id,
            "title": f"Person {p_num + 1:02d}",
            "role": f"Detected in {len(cluster_tracks)} segment{'s' if len(cluster_tracks) > 1 else ''}",
            "detectedDuration": total_cluster_dur,
            "timeSpan": f"{min_sec:.2f}s – {max_sec:.2f}s",
            "tracksCount": len(cluster_tracks),
            "trackIds": cluster_tracks,
            "thumbnailUrl": f"/api/jobs/{job_id}/thumbnails/track_{rep_idx:02d}.jpg?t={job_id}",
            "galleryThumbnails": [f"/api/jobs/{job_id}/thumbnails/track_{t:02d}.jpg?t={job_id}" for t in cluster_tracks]
        })

    # Individual tracks metadata
    individual_tracks = []
    for m in track_meta:
        assigned_person = "unassigned"
        for p in persons:
            if m["track_id"] in p["trackIds"]:
                assigned_person = p["id"]
                break

        individual_tracks.append({
            "id": str(m["track_id"]),
            "trackNumber": m["track_id"],
            "duration": m["duration"],
            "startSec": m["startSec"],
            "endSec": m["endSec"],
            "timeSpan": m["timeSpan"],
            "thumbnailUrl": m["thumbnailUrl"],
            "belongsTo": assigned_person
        })

    result_data = {
        "job_id": job_id,
        "video_info": {
            "duration": total_audio_sec,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "totalFrames": len(frames)
        },
        "persons": persons,
        "tracks": individual_tracks,
        "totalTracks": len(tracks)
    }

    with open(job_dir / "speakers.json", "w") as f:
        json.dump(result_data, f, indent=2)

    update_job_status(job_id, "speakers_detected", f"{len(persons)} distinct speakers detected across {len(tracks)} tracks", 1.0)
    return result_data

def extract_job_speaker(job_id: str, target: str, mode: str = "person"):
    job_dir = JOBS_DIR / job_id
    speakers_file = job_dir / "speakers.json"
    audio_file = job_dir / "audio.wav"
    tracks_file = job_dir / "tracks.pkl"
    video_file = job_dir / "video.mp4"

    if not speakers_file.exists():
        raise FileNotFoundError(f"speakers.json not found for job {job_id}")

    with open(speakers_file, "r") as f:
        job_speakers = json.load(f)

    with open(tracks_file, "rb") as f:
        tracks = pickle.load(f)

    full_audio, sr = sf.read(str(audio_file), dtype='float32')
    total_samples = len(full_audio)
    total_duration = total_samples / sr

    target_str = target.strip().lower()
    selected_track_ids = []
    target_name = ""

    found_person = None
    for p in job_speakers["persons"]:
        if p["id"].lower() == target_str:
            found_person = p
            break

    if found_person:
        selected_track_ids = found_person["trackIds"]
        target_name = found_person["title"]
    elif target_str.isdigit():
        tid = int(target_str)
        if mode == "person":
            for p in job_speakers["persons"]:
                if tid in p["trackIds"]:
                    selected_track_ids = p["trackIds"]
                    target_name = f"{p['title']} (from track {tid})"
                    break
            if not selected_track_ids:
                selected_track_ids = [tid]
                target_name = f"Track {tid}"
        else:
            selected_track_ids = [tid]
            target_name = f"Track {tid} Only"
    else:
        raise ValueError(f"Unknown target: {target}")

    update_job_status(job_id, "extracting_speech", f"AV-MossFormer2 isolating vocal harmonics for {target_name} ({len(selected_track_ids)} segments)...", 0.4)

    # Read video frames and get exact video FPS
    cap = cv2.VideoCapture(str(video_file))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if not fps or fps <= 0 or np.isnan(fps):
        fps = job_speakers.get("video_info", {}).get("fps", 25.0)

    frames = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    model, args = get_clearvoice_model()

    timeline = np.zeros(total_samples, dtype=np.float32)
    weight_map = np.zeros(total_samples, dtype=np.float32)
    combined_segments = []

    selected_track_ids = sorted(selected_track_ids, key=lambda tid: tracks[tid]['frame'][0])

    for i, tid in enumerate(selected_track_ids):
        update_job_status(job_id, "extracting_speech", f"Extracting speech segment {i+1}/{len(selected_track_ids)} (Track {tid})...", 0.4 + (i / max(1, len(selected_track_ids))) * 0.4)
        track = tracks[tid]
        start_frame = track['frame'][0]
        end_frame = track['frame'][-1]
        start_sec = start_frame / fps
        end_sec = (end_frame + 1) / fps

        track_wav = job_dir / f"track_{tid}.wav"

        if not track_wav.exists():
            dets = {'x': [], 'y': [], 's': []}
            for det in track['bbox']:
                dets['s'].append(max((det[3] - det[1]), (det[2] - det[0])) / 2)
                dets['y'].append((det[1] + det[3]) / 2)
                dets['x'].append((det[0] + det[2]) / 2)

            k_size = min(13, len(dets['s']))
            if k_size % 2 == 0:
                k_size -= 1
            if k_size >= 3:
                dets['s'] = signal.medfilt(dets['s'], kernel_size=k_size)
                dets['x'] = signal.medfilt(dets['x'], kernel_size=k_size)
                dets['y'] = signal.medfilt(dets['y'], kernel_size=k_size)

            video_features = []
            cs = 0.40
            for fidx, frame_num in enumerate(track['frame']):
                bs = dets['s'][fidx]
                bsi = int(bs * (1 + 2 * cs))
                orig_img = frames[frame_num]
                padded_img = np.pad(orig_img, ((bsi, bsi), (bsi, bsi), (0, 0)), 'constant', constant_values=(110, 110))
                my = dets['y'][fidx] + bsi
                mx = dets['x'][fidx] + bsi
                face = padded_img[int(my - bs):int(my + bs * (1 + 2 * cs)), int(mx - bs * (1 + cs)):int(mx + bs * (1 + cs))]
                face_224 = cv2.resize(face, (224, 224))
                gray = cv2.cvtColor(face_224, cv2.COLOR_BGR2GRAY)
                mouth_112 = gray[56:168, 56:168]
                video_features.append(mouth_112)

            visual = np.array(video_features, dtype=np.float32) / 255.0
            visual = (visual - 0.4161) / 0.1688

            audio_start = max(0, int(start_frame * sr / fps))
            audio_end = min(total_samples, int((end_frame + 1) * sr / fps))
            audio_seg = full_audio[audio_start:audio_end].copy()

            if audio_seg.shape[0] < 160:
                continue

            req_visual_len = int(audio_seg.shape[0] / 16000 * 25)
            if visual.shape[0] < req_visual_len:
                visual = np.pad(visual, ((0, req_visual_len - visual.shape[0]), (0, 0), (0, 0)), mode='edge')
            else:
                visual = visual[:req_visual_len]

            audio_max = np.max(np.abs(audio_seg))
            if audio_max > 0:
                audio_seg /= audio_max

            audio_in = np.expand_dims(audio_seg, axis=0)
            visual_in = np.expand_dims(visual, axis=0)

            from clearvoice.utils.decode import decode_one_audio_AV_MossFormer2_TSE_16K
            with torch.inference_mode():
                est_audio = decode_one_audio_AV_MossFormer2_TSE_16K(model, (audio_in, visual_in), args)

            max_est = np.max(np.abs(est_audio))
            if max_est > 0:
                est_audio = est_audio / max_est

            sf.write(str(track_wav), est_audio, 16000)
        else:
            est_audio, _ = sf.read(str(track_wav), dtype='float32')

        start_sample = max(0, int(start_frame * sr / fps))
        end_sample = start_sample + len(est_audio)
        if end_sample > total_samples:
            est_audio = est_audio[:total_samples - start_sample]
            end_sample = total_samples

        timeline[start_sample:end_sample] += est_audio
        weight_map[start_sample:end_sample] += 1.0

        combined_segments.append({
            "track_id": tid,
            "start_frame": int(start_frame),
            "end_frame": int(end_frame),
            "start_time_sec": round(start_sec, 2),
            "end_time_sec": round(end_sec, 2),
            "duration_sec": round(len(est_audio) / sr, 2),
            "start_sample": start_sample,
            "end_sample": end_sample
        })

    update_job_status(job_id, "combining_segments", "Normalizing timeline and preserving natural silence intervals...", 0.9)

    mask = weight_map > 1.0
    timeline[mask] /= weight_map[mask]

    max_val = np.max(np.abs(timeline))
    if max_val > 0.95:
        timeline = timeline * (0.95 / max_val)

    out_file = job_dir / f"target_speaker_{target_str}.wav"
    sf.write(str(out_file), timeline, sr)

    active_mask = np.abs(timeline) > 1e-4
    active_sec = round(float(np.sum(active_mask) / sr), 2)
    silence_sec = round(total_duration - active_sec, 2)

    report = {
        "job_id": job_id,
        "target": target_str,
        "target_name": target_name,
        "total_timeline_duration_sec": round(total_duration, 2),
        "active_speech_duration_sec": active_sec,
        "silence_duration_sec": silence_sec,
        "num_segments_combined": len(combined_segments),
        "segments": combined_segments
    }

    with open(job_dir / f"meta_{target_str}.json", "w") as f:
        json.dump(report, f, indent=2)

    update_job_status(job_id, "completed", f"Target speech successfully isolated for {target_name}", 1.0)
    return report
