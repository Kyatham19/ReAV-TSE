import os
import sys
import time
import json
import shutil
import pickle
import types
from pathlib import Path
import cv2
import numpy as np
import soundfile as sf
from scipy import signal
import torch

# Import pipeline dependencies
from job_pipeline import (
    fixed_overlap_and_add,
    get_resnet_embedder,
    get_clearvoice_model,
    extract_audio_from_video,
    YUNET_PATH,
    BASE_DIR,
    JOBS_DIR
)
from clearvoice.utils.video_process import track_shot
from clearvoice.utils.decode import decode_one_audio_AV_MossFormer2_TSE_16K

def run_benchmark():
    print("=" * 75)
    print("REAV-TSE PIPELINE PERFORMANCE BENCHMARK (CLEAN RUN)")
    print("=" * 75)

    source_video = Path("outputs_clearvoice/jobs/job_1790332587_475ab7/video.mp4")
    if not source_video.exists():
        print(f"Error: Source video {source_video} not found!")
        return

    # Create brand new clean job workspace for benchmark
    bench_job_id = f"job_bench_{int(time.time())}"
    job_dir = JOBS_DIR / bench_job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    job_dir.mkdir(parents=True, exist_ok=True)
    thumb_dir = job_dir / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)

    video_dest = job_dir / "video.mp4"
    audio_dest = job_dir / "audio.wav"

    stage_timings = {}
    timestamps = {}

    def record_stage(name, t_start, t_end):
        duration = t_end - t_start
        stage_timings[name] = duration
        timestamps[name] = {
            "start": time.strftime("%H:%M:%S", time.localtime(t_start)) + f".{int((t_start % 1) * 1000):03d}",
            "end": time.strftime("%H:%M:%S", time.localtime(t_end)) + f".{int((t_end % 1) * 1000):03d}",
            "duration_sec": round(duration, 3)
        }
        print(f"  [{name}] {duration:.3f}s ({timestamps[name]['start']} -> {timestamps[name]['end']})")

    overall_start = time.perf_counter()

    # ----------------------------------------------------
    # Stage 1: Video upload/save
    # ----------------------------------------------------
    print("\n1. Measuring Video Upload & Save...")
    t0 = time.perf_counter()
    shutil.copyfile(str(source_video), str(video_dest))
    t1 = time.perf_counter()
    record_stage("1. Video upload/save", t0, t1)

    # ----------------------------------------------------
    # Stage 2: Audio extraction
    # ----------------------------------------------------
    print("\n2. Measuring Audio Extraction (ffmpeg 16kHz mono)...")
    t0 = time.perf_counter()
    extract_audio_from_video(video_dest, audio_dest)
    audio_info = sf.info(str(audio_dest))
    total_audio_sec = round(audio_info.duration, 2)
    t1 = time.perf_counter()
    record_stage("2. Audio extraction", t0, t1)

    # Read video frames
    cap = cv2.VideoCapture(str(video_dest))
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
    total_frames = len(frames)

    # ----------------------------------------------------
    # Stage 3: Face detection (YuNet)
    # ----------------------------------------------------
    print(f"\n3. Measuring Face Detection (YuNet across {total_frames} frames)...")
    t0 = time.perf_counter()
    detector = cv2.FaceDetectorYN.create(YUNET_PATH, "", (w, h), score_threshold=0.5)
    all_faces = []
    total_face_detections = 0
    for fidx, frame in enumerate(frames):
        _, faces = detector.detect(frame)
        dets = []
        if faces is not None:
            for f in faces:
                fx, fy, fw, fh = f[:4]
                dets.append({'frame': fidx, 'bbox': [fx, fy, fx + fw, fy + fh], 'conf': float(f[-1])})
                total_face_detections += 1
        all_faces.append(dets)
    t1 = time.perf_counter()
    record_stage("3. Face detection", t0, t1)

    # ----------------------------------------------------
    # Stage 4: Face tracking (track_shot)
    # ----------------------------------------------------
    print("\n4. Measuring Face Tracking (track_shot IoU & sequence linking)...")
    t0 = time.perf_counter()
    v_args = types.SimpleNamespace(
        numFailedDet=10,
        minTrack=10,
        minFaceSize=10,
        cropScale=0.40,
        nDataLoaderThread=4
    )
    tracks = track_shot(v_args, all_faces)
    tracks = sorted(tracks, key=lambda t: len(t['frame']), reverse=True)
    t1 = time.perf_counter()
    record_stage("4. Face tracking", t0, t1)

    # ----------------------------------------------------
    # Stage 5: Speaker clustering (ResNet-18 Deep Embeddings)
    # ----------------------------------------------------
    print(f"\n5. Measuring Speaker Clustering ({len(tracks)} tracks via ResNet-18)...")
    t0 = time.perf_counter()
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
            "thumbnailUrl": f"/api/jobs/{bench_job_id}/thumbnails/{thumb_name}",
            "frame_set": set(track['frame'])
        })
        track_embeddings.append(emb)

    SIM_THRESHOLD = 0.80
    clusters = []
    for tidx in range(len(tracks)):
        t_frames = track_meta[tidx]["frame_set"]
        best_cluster = -1
        best_sim = -1
        for c_idx, cluster in enumerate(clusters):
            collision = any(not t_frames.isdisjoint(track_meta[other_tid]["frame_set"]) for other_tid in cluster)
            if not collision:
                sims = [float(np.dot(track_embeddings[tidx], track_embeddings[other_tid])) for other_tid in cluster]
                avg_sim = sum(sims) / len(sims)
                if avg_sim >= SIM_THRESHOLD and avg_sim > best_sim:
                    best_sim = avg_sim
                    best_cluster = c_idx
        if best_cluster >= 0:
            clusters[best_cluster].append(tidx)
        else:
            clusters.append([tidx])

    clusters = sorted(clusters, key=lambda c: min(track_meta[idx]["start_frame"] for idx in c))
    t1 = time.perf_counter()
    record_stage("5. Speaker clustering", t0, t1)

    # ----------------------------------------------------
    # Stage 6: Speaker analysis & metadata generation
    # ----------------------------------------------------
    print("\n6. Measuring Speaker Analysis / Metadata Generation...")
    t0 = time.perf_counter()
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
            "thumbnailUrl": f"/api/jobs/{bench_job_id}/thumbnails/track_{rep_idx:02d}.jpg",
            "galleryThumbnails": [f"/api/jobs/{bench_job_id}/thumbnails/track_{t:02d}.jpg" for t in cluster_tracks]
        })

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
        "job_id": bench_job_id,
        "video_info": {
            "duration": total_audio_sec,
            "resolution": f"{w}x{h}",
            "fps": fps,
            "totalFrames": total_frames
        },
        "persons": persons,
        "tracks": individual_tracks,
        "totalTracks": len(tracks)
    }

    with open(job_dir / "speakers.json", "w") as f:
        json.dump(result_data, f, indent=2)
    t1 = time.perf_counter()
    record_stage("6. Speaker analysis/metadata", t0, t1)

    # ----------------------------------------------------
    # Stage 7: Target speaker selection
    # ----------------------------------------------------
    print("\n7. Measuring Target Speaker Selection (Selecting Person 03)...")
    t0 = time.perf_counter()
    target_person = None
    for p in persons:
        if p["id"] == "person3":
            target_person = p
            break
    if not target_person:
        target_person = persons[0]

    selected_track_ids = target_person["trackIds"]
    target_name = target_person["title"]
    selected_track_ids = sorted(selected_track_ids, key=lambda tid: tracks[tid]['frame'][0])
    t1 = time.perf_counter()
    record_stage("7. Target speaker selection", t0, t1)

    # ----------------------------------------------------
    # Stage 8: AV-MossFormer2 inference
    # ----------------------------------------------------
    print(f"\n8. Measuring AV-MossFormer2 Inference on {len(selected_track_ids)} segments for {target_name}...")
    t0 = time.perf_counter()
    model, args = get_clearvoice_model()

    full_audio, sr = sf.read(str(audio_dest), dtype='float32')
    total_samples = len(full_audio)

    extracted_segments_data = []

    for i, tid in enumerate(selected_track_ids):
        t_seg_start = time.perf_counter()
        track = tracks[tid]
        start_frame = track['frame'][0]
        end_frame = track['frame'][-1]
        start_sec = start_frame / fps
        end_sec = (end_frame + 1) / fps

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

        with torch.no_grad():
            est_audio = decode_one_audio_AV_MossFormer2_TSE_16K(model, (audio_in, visual_in), args)

        max_est = np.max(np.abs(est_audio))
        if max_est > 0:
            est_audio = est_audio / max_est

        track_wav = job_dir / f"track_{tid}.wav"
        sf.write(str(track_wav), est_audio, 16000)

        t_seg_end = time.perf_counter()
        print(f"    - Segment {i+1} (Track {tid}, {len(track['frame'])} frames, {len(est_audio)/sr:.2f}s audio): {t_seg_end - t_seg_start:.3f}s")
        extracted_segments_data.append((tid, start_frame, end_frame, start_sec, end_sec, est_audio))

    t1 = time.perf_counter()
    record_stage("8. AV-MossFormer2 inference", t0, t1)

    # ----------------------------------------------------
    # Stage 9: Segment combination & timeline reconstruction
    # ----------------------------------------------------
    print("\n9. Measuring Segment Combination & Timeline Reconstruction...")
    t0 = time.perf_counter()
    timeline = np.zeros(total_samples, dtype=np.float32)
    weight_map = np.zeros(total_samples, dtype=np.float32)
    combined_segments = []

    for tid, start_frame, end_frame, start_sec, end_sec, est_audio in extracted_segments_data:
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

    mask = weight_map > 1.0
    timeline[mask] /= weight_map[mask]

    max_val = np.max(np.abs(timeline))
    if max_val > 0.95:
        timeline = timeline * (0.95 / max_val)
    t1 = time.perf_counter()
    record_stage("9. Segment combination/reconstruction", t0, t1)

    # ----------------------------------------------------
    # Stage 10: WAV output & reporting
    # ----------------------------------------------------
    print("\n10. Measuring WAV Output & File Saving...")
    t0 = time.perf_counter()
    out_file = job_dir / f"target_speaker_person3.wav"
    sf.write(str(out_file), timeline, sr)

    active_mask = np.abs(timeline) > 1e-4
    active_sec = round(float(np.sum(active_mask) / sr), 2)
    silence_sec = round(total_audio_sec - active_sec, 2)

    report = {
        "job_id": bench_job_id,
        "target": "person3",
        "target_name": target_name,
        "total_timeline_duration_sec": total_audio_sec,
        "active_speech_duration_sec": active_sec,
        "silence_duration_sec": silence_sec,
        "num_segments_combined": len(combined_segments),
        "segments": combined_segments
    }
    with open(job_dir / "meta_person3.json", "w") as f:
        json.dump(report, f, indent=2)
    t1 = time.perf_counter()
    record_stage("10. WAV output", t0, t1)

    overall_end = time.perf_counter()
    total_pipeline_time = overall_end - overall_start

    # Final Summary Dictionary
    summary = {
        "bench_job_id": bench_job_id,
        "video_duration_sec": total_audio_sec,
        "total_frames": total_frames,
        "raw_face_detections": total_face_detections,
        "face_tracks": len(tracks),
        "distinct_people": len(persons),
        "selected_person": f"{target_name} ({target_person['id']})",
        "selected_tracks": selected_track_ids,
        "num_target_segments": len(selected_track_ids),
        "total_av_mossformer2_time_sec": round(stage_timings["8. AV-MossFormer2 inference"], 3),
        "total_pipeline_time_sec": round(total_pipeline_time, 3),
        "stage_timings_sec": {k: round(v, 3) for k, v in stage_timings.items()},
        "timestamps": timestamps
    }

    with open("benchmark_results.json", "w") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 75)
    print("BENCHMARK EXECUTION COMPLETED")
    print("=" * 75)
    print(f"Video Duration:                  {total_audio_sec}s ({total_frames} frames @ {fps:.2f} fps)")
    print(f"Number of Face Detections:       {total_face_detections}")
    print(f"Number of Face Tracks:           {len(tracks)}")
    print(f"Number of People:                {len(persons)}")
    print(f"Selected Person:                 {target_name} ({target_person['id']})")
    print(f"Number of Target Segments:       {len(selected_track_ids)} (Tracks {selected_track_ids})")
    print(f"Total AV-MossFormer2 Time:       {stage_timings['8. AV-MossFormer2 inference']:.3f}s")
    print(f"Total Pipeline Time:             {total_pipeline_time:.3f}s")
    print("=" * 75)

    # Sort stages by duration to identify the biggest bottleneck
    sorted_stages = sorted(stage_timings.items(), key=lambda x: x[1], reverse=True)
    biggest_bottleneck = sorted_stages[0]
    print(f"\nBIGGEST BOTTLENECK: {biggest_bottleneck[0]} ({biggest_bottleneck[1]:.3f}s, {biggest_bottleneck[1]/total_pipeline_time*100:.1f}% of total time)")
    print("\nTIMING BREAKDOWN (Fastest to Slowest):")
    for name, dur in sorted(stage_timings.items(), key=lambda x: x[1]):
        pct = (dur / total_pipeline_time) * 100
        print(f"  {name:38s}: {dur:8.3f}s ({pct:5.1f}%)")

if __name__ == "__main__":
    run_benchmark()
