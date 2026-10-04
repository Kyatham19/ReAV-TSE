import os
import sys
import time
import types
import pickle
import numpy as np
import cv2
import torch
import soundfile as sf
from scipy import signal
from scipy.interpolate import interp1d

from clearvoice import ClearVoice
from clearvoice.utils.decode import decode_one_audio_AV_MossFormer2_TSE_16K
from clearvoice.utils.video_process import bb_intersection_over_union, track_shot
import clearvoice.models.av_mossformer2_tse.av_mossformer2 as av_module
import math

# Monkey patch overlap_and_add so it works on CPU (original code hardcodes .cuda())
def fixed_overlap_and_add(signal, frame_step):
    outer_dimensions = signal.size()[:-2]
    frames, frame_length = signal.size()[-2:]

    subframe_length = math.gcd(frame_length, frame_step)
    subframe_step = frame_step // subframe_length
    subframes_per_frame = frame_length // subframe_length
    output_size = frame_step * (frames - 1) + frame_length
    output_subframes = output_size // subframe_length

    subframe_signal = signal.view(*outer_dimensions, -1, subframe_length)

    frame = torch.arange(0, output_subframes).unfold(0, subframes_per_frame, subframe_step)
    frame = signal.new_tensor(frame, dtype=torch.long)
    frame = frame.contiguous().view(-1)

    result = signal.new_zeros(*outer_dimensions, output_subframes, subframe_length)
    result.index_add_(-2, frame, subframe_signal)
    result = result.view(*outer_dimensions, -1)
    return result

av_module.overlap_and_add = fixed_overlap_and_add


def run_inference():
    print("=" * 60)
    print("Starting AV_MossFormer2_TSE_16K Target Speaker Extraction")
    print("=" * 60)

    audio_path = os.path.abspath("outputs_clearvoice/AV_MossFormer2_TSE_16K/test_videos/test/py_video/audio.wav")
    video_path = os.path.abspath("outputs_clearvoice/AV_MossFormer2_TSE_16K/test_videos/test/py_video/video.avi")
    out_dir = os.path.abspath("outputs_clearvoice/results")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Loading Audio: {audio_path}")
    print(f"Loading Video: {video_path}")

    # 1. Load Audio
    full_audio, sr = sf.read(audio_path, dtype='float32')
    print(f"Audio Sample Rate: {sr}, Length: {len(full_audio)} samples ({len(full_audio)/sr:.2f}s)")
    assert sr == 16000, "Sample rate must be 16000 Hz"

    # 2. Read Video Frames in memory
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Video Resolution: {w}x{h}, FPS: {fps}")

    frames = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    total_frames = len(frames)
    print(f"Total Video Frames: {total_frames}")

    # 3. Face Detection using YuNet (with local cache)
    cache_path = os.path.join(out_dir, "all_faces.pkl")
    if os.path.exists(cache_path):
        print(f"\n[Step 1/3] Loading cached face detections from {cache_path}...")
        with open(cache_path, "rb") as f:
            all_faces = pickle.load(f)
    else:
        yunet_model = "yunet.onnx"
        detector = cv2.FaceDetectorYN.create(yunet_model, "", (w, h), score_threshold=0.5)

        print("\n[Step 1/3] Detecting faces across all frames...")
        all_faces = []
        for fidx, frame in enumerate(frames):
            _, faces = detector.detect(frame)
            dets = []
            if faces is not None:
                for f in faces:
                    x, y, fw, fh = f[:4]
                    dets.append({'frame': fidx, 'bbox': [x, y, x + fw, y + fh], 'conf': float(f[-1])})
            all_faces.append(dets)
        with open(cache_path, "wb") as f:
            pickle.dump(all_faces, f)

    # 4. Face Tracking with minTrack = 10
    print("\n[Step 2/3] Tracking faces across video (minTrack = 10)...")
    v_args = types.SimpleNamespace(
        numFailedDet=10,
        minTrack=10,
        minFaceSize=10,
        cropScale=0.40,
        nDataLoaderThread=4
    )
    tracks = track_shot(v_args, all_faces)
    print(f"Successfully detected {len(tracks)} face track(s)!")

    if len(tracks) == 0:
        print("ERROR: No face tracks detected even with minTrack=10.")
        return

    # Sort tracks by length (longest tracks first)
    tracks = sorted(tracks, key=lambda t: len(t['frame']), reverse=True)

    for i, t in enumerate(tracks):
        start_f = t['frame'][0]
        end_f = t['frame'][-1]
        n_f = len(t['frame'])
        print(f"  Track {i}: Start frame {start_f} -> End frame {end_f} ({n_f} frames, {n_f/25:.2f}s)")

    # 5. Load Model
    print("\n[Step 3/3] Loading AV_MossFormer2_TSE_16K Model...")
    cv_app = ClearVoice(task='target_speaker_extraction', model_names=['AV_MossFormer2_TSE_16K'])
    model = cv_app.models[0].model
    device = cv_app.models[0].device
    args = cv_app.models[0].args
    args.device = device
    print(f"Model ready on device: {device}")

    # 6. Extract Target Speaker for each Track
    extracted_wav_paths = []
    for tidx, track in enumerate(tracks):
        print(f"\nProcessing Track {tidx} ({len(track['frame'])} frames)...")

        # Smooth bounding box
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

        # Crop face and extract mouth ROI (112x112)
        video_features = []
        cs = v_args.cropScale
        for fidx, frame_num in enumerate(track['frame']):
            bs = dets['s'][fidx]
            bsi = int(bs * (1 + 2 * cs))
            orig_img = frames[frame_num]
            padded_img = np.pad(orig_img, ((bsi, bsi), (bsi, bsi), (0, 0)), 'constant', constant_values=(110, 110))
            my = dets['y'][fidx] + bsi
            mx = dets['x'][fidx] + bsi
            face = padded_img[int(my - bs):int(my + bs * (1 + 2 * cs)), int(mx - bs * (1 + cs)):int(mx + bs * (1 + cs))]
            face_224 = cv2.resize(face, (224, 224))

            # Mouth ROI: central 112x112 region
            gray = cv2.cvtColor(face_224, cv2.COLOR_BGR2GRAY)
            mouth_112 = gray[56:168, 56:168]
            video_features.append(mouth_112)

        # Normalize visual features
        visual = np.array(video_features, dtype=np.float32) / 255.0
        visual = (visual - 0.4161) / 0.1688

        # Segment audio matching track
        audio_start = int(track['frame'][0] * 16000 / 25)
        audio_end = int((track['frame'][-1] + 1) * 16000 / 25)
        audio_seg = full_audio[audio_start:audio_end].copy()

        # Match lengths
        req_visual_len = int(audio_seg.shape[0] / 16000 * 25)
        if visual.shape[0] < req_visual_len:
            visual = np.pad(visual, ((0, req_visual_len - visual.shape[0]), (0, 0), (0, 0)), mode='edge')
        else:
            visual = visual[:req_visual_len]

        audio_max = np.max(np.abs(audio_seg))
        if audio_max > 0:
            audio_seg /= audio_max

        # Model inputs format: audio [1, T], visual [1, T_v, 112, 112]
        audio_in = np.expand_dims(audio_seg, axis=0)
        visual_in = np.expand_dims(visual, axis=0)

        # Run Model Inference
        with torch.no_grad():
            est_audio = decode_one_audio_AV_MossFormer2_TSE_16K(model, (audio_in, visual_in), args)

        # Peak Normalize
        max_est = np.max(np.abs(est_audio))
        if max_est > 0:
            est_audio = est_audio / max_est

        # Save Target Speaker Segment WAV
        out_wav = os.path.join(out_dir, f"target_speaker_track{tidx}.wav")
        sf.write(out_wav, est_audio, 16000)
        extracted_wav_paths.append(out_wav)
        print(f"-> Saved: {out_wav} (Length: {len(est_audio)/16000:.2f}s)")

    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE! OUTPUT AUDIO FILES:")
    for p in extracted_wav_paths:
        print(f"  - {p}")
    print("=" * 60)

if __name__ == '__main__':
    run_inference()
