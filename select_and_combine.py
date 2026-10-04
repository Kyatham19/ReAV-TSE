import os
import sys
import json
import types
import pickle
import argparse
import numpy as np
import soundfile as sf
from clearvoice.utils.video_process import track_shot

# Pre-analyzed mapping of face tracks to people based on visual contact sheet & scene continuity
PERSON_MAPPING = {
    "person1": {
        "name": "Person 1 (Older man / Grey hair)",
        "tracks": [0, 13, 8, 18],
        "description": "Frames 39-110 (1.56s-4.44s), 111-130 (4.44s-5.24s), 143-171 (5.72s-6.88s), 192-205 (7.68s-8.24s)"
    },
    "person2": {
        "name": "Person 2 (Young woman / Dark hair)",
        "tracks": [7, 5, 10, 1, 9, 12, 4],
        "description": "Frames 10-38 (0.40s-1.56s), 261-295 (10.44s-11.84s), 296-318 (11.84s-12.76s), 319-354 (12.76s-14.20s), 355-381 (14.20s-15.28s), 387-408 (15.48s-16.36s), 409-444 (16.36s-17.80s)"
    },
    "person3": {
        "name": "Person 3 (Young man / Short hair)",
        "tracks": [6, 16, 14, 11, 3],
        "description": "Frames 10-38 (0.40s-1.56s), 227-241 (9.08s-9.68s), 243-260 (9.72s-10.44s), 386-408 (15.44s-16.36s), 409-444 (16.36s-17.80s)"
    },
    "person4": {
        "name": "Person 4 (Bearded man)",
        "tracks": [2],
        "description": "Frames 319-354 (12.76s-14.20s)"
    }
}

# Reverse lookup: track_id -> person_key
TRACK_TO_PERSON = {}
for p_key, p_val in PERSON_MAPPING.items():
    for tid in p_val["tracks"]:
        TRACK_TO_PERSON[tid] = p_key

def load_tracks():
    cache_path = 'outputs_clearvoice/results/all_faces.pkl'
    if not os.path.exists(cache_path):
        raise FileNotFoundError(f"Missing {cache_path}")
    with open(cache_path, 'rb') as f:
        all_faces = pickle.load(f)

    v_args = types.SimpleNamespace(
        numFailedDet=10,
        minTrack=10,
        minFaceSize=10,
        cropScale=0.40,
        nDataLoaderThread=4
    )
    tracks = track_shot(v_args, all_faces)
    tracks = sorted(tracks, key=lambda t: len(t['frame']), reverse=True)
    return tracks

def combine_tracks(selected_tracks, tracks_info, master_audio_path, output_path):
    # Load master audio info to get exact length and sample rate
    master_info = sf.info(master_audio_path)
    sr = master_info.samplerate
    total_samples = master_info.frames
    total_duration = master_info.duration

    print(f"\nMaster Timeline: {total_samples} samples ({total_duration:.2f}s) at {sr} Hz")
    timeline = np.zeros(total_samples, dtype=np.float32)
    weight_map = np.zeros(total_samples, dtype=np.float32)

    combined_segments = []

    # Sort tracks chronologically by start frame
    selected_tracks = sorted(selected_tracks, key=lambda tid: tracks_info[tid]['frame'][0])

    for tid in selected_tracks:
        track = tracks_info[tid]
        start_frame = track['frame'][0]
        end_frame = track['frame'][-1]
        start_sec = start_frame / 25.0
        end_sec = (end_frame + 1) / 25.0

        track_wav = f"outputs_clearvoice/results/target_speaker_track{tid}.wav"
        if not os.path.exists(track_wav):
            print(f"Warning: {track_wav} not found! Skipping.")
            continue

        audio_seg, seg_sr = sf.read(track_wav, dtype='float32')
        assert seg_sr == sr, f"Sample rate mismatch: {seg_sr} vs {sr}"

        start_sample = int(start_frame * sr / 25)
        end_sample = start_sample + len(audio_seg)

        if end_sample > total_samples:
            audio_seg = audio_seg[:total_samples - start_sample]
            end_sample = total_samples

        # Add segment into timeline with overlap-add weighting
        timeline[start_sample:end_sample] += audio_seg
        weight_map[start_sample:end_sample] += 1.0

        seg_info = {
            "track_id": tid,
            "start_frame": int(start_frame),
            "end_frame": int(end_frame),
            "start_time_sec": round(start_sec, 2),
            "end_time_sec": round(end_sec, 2),
            "duration_sec": round(len(audio_seg) / sr, 2),
            "start_sample": start_sample,
            "end_sample": end_sample,
            "source_file": track_wav
        }
        combined_segments.append(seg_info)
        print(f"  + Added Track {tid:2d}: frames {start_frame:3d}-{end_frame:3d} ({start_sec:5.2f}s - {end_sec:5.2f}s, dur: {len(audio_seg)/sr:4.2f}s)")

    # Normalize overlapping regions
    mask = weight_map > 1.0
    timeline[mask] /= weight_map[mask]

    # Peak normalize final combined audio
    max_val = np.max(np.abs(timeline))
    if max_val > 0.95:
        timeline = timeline * (0.95 / max_val)

    # Save output WAV
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    sf.write(output_path, timeline, sr)
    print(f"\nSuccessfully written combined target speech to: {output_path}")

    # Calculate active speech duration
    active_mask = np.abs(timeline) > 1e-4
    active_sec = np.sum(active_mask) / sr
    silence_sec = total_duration - active_sec

    report = {
        "output_file": os.path.abspath(output_path),
        "total_timeline_duration_sec": round(total_duration, 2),
        "active_speech_duration_sec": round(active_sec, 2),
        "silence_duration_sec": round(silence_sec, 2),
        "num_segments_combined": len(combined_segments),
        "segments": combined_segments
    }

    meta_path = os.path.splitext(output_path)[0] + "_meta.json"
    with open(meta_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Metadata saved to: {meta_path}")

    return report

def main():
    parser = argparse.ArgumentParser(description="Target Person Selection and Timeline Combiner for AV-MossFormer2")
    parser.add_argument("--target", type=str, required=True,
                        help="Target person (person1, person2, person3, person4) or track ID (e.g. 0) or comma-separated track IDs (e.g. 0,8,13,18)")
    parser.add_argument("--mode", type=str, choices=["person", "single"], default="person",
                        help="'person' combines all segments for the chosen person; 'single' extracts only the exact track specified")
    parser.add_argument("--output", type=str, default="outputs_clearvoice/results/target_speaker.wav",
                        help="Destination WAV file")

    args = parser.parse_args()

    tracks_info = load_tracks()
    target_str = args.target.strip().lower()

    if target_str in PERSON_MAPPING:
        p_info = PERSON_MAPPING[target_str]
        selected_tracks = p_info["tracks"]
        target_name = p_info["name"]
    elif "," in target_str:
        selected_tracks = [int(x.strip()) for x in target_str.split(",")]
        target_name = f"Custom Tracks {selected_tracks}"
    elif target_str.isdigit():
        tid = int(target_str)
        if args.mode == "person" and tid in TRACK_TO_PERSON:
            p_key = TRACK_TO_PERSON[tid]
            p_info = PERSON_MAPPING[p_key]
            selected_tracks = p_info["tracks"]
            target_name = f"{p_info['name']} (auto-grouped from Track {tid})"
        else:
            selected_tracks = [tid]
            target_name = f"Track {tid} Only"
    else:
        print(f"Error: Unknown target '{target_str}'. Available persons: {list(PERSON_MAPPING.keys())} or track IDs 0-20.")
        sys.exit(1)

    print("=" * 60)
    print(f"TARGET SELECTED: {target_name}")
    print(f"Tracks to combine: {selected_tracks}")
    print("=" * 60)

    master_audio = "outputs_clearvoice/AV_MossFormer2_TSE_16K/test_videos/test/py_video/audio.wav"
    report = combine_tracks(selected_tracks, tracks_info, master_audio, args.output)

if __name__ == '__main__':
    main()
