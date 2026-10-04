import os
import sys
import time
import json
import shutil
from pathlib import Path
import soundfile as sf
import numpy as np
import torch

from job_pipeline import (
    create_job,
    analyze_video_job,
    extract_job_speaker,
    JOBS_DIR
)

def run_verification():
    print("=" * 75)
    print("VERIFICATION: FULL MULTI-PERSON VIDEO OPTIMIZED PIPELINE RUN")
    print("=" * 75)

    source_video = Path("outputs_clearvoice/jobs/job_1790332587_475ab7/video.mp4")
    baseline_wav_path = Path("outputs_clearvoice/jobs/job_bench_1790411979/target_speaker_person3.wav")
    baseline_json_path = Path("benchmark_results.json")

    assert source_video.exists(), f"Source video {source_video} not found!"
    assert baseline_wav_path.exists(), f"Baseline WAV {baseline_wav_path} not found!"
    assert baseline_json_path.exists(), f"Baseline JSON {baseline_json_path} not found!"

    with open(baseline_json_path, "r") as f:
        baseline_meta = json.load(f)

    # 1. Create a fresh clean job
    bench_start = time.perf_counter()
    new_job_id = create_job(source_video, is_sample=False)
    print(f"Created fresh job: {new_job_id}")

    # 2. Run analysis
    t_analyze_start = time.perf_counter()
    analysis_data = analyze_video_job(new_job_id)
    t_analyze_end = time.perf_counter()
    analyze_duration = t_analyze_end - t_analyze_start
    print(f"Analysis completed in {analyze_duration:.3f}s: {len(analysis_data['persons'])} persons, {analysis_data['totalTracks']} tracks")

    # 3. Run extraction on Person 03 (Tracks [4, 0])
    t_extract_start = time.perf_counter()
    extract_report = extract_job_speaker(new_job_id, target="person3", mode="person")
    t_extract_end = time.perf_counter()
    extract_duration = t_extract_end - t_extract_start
    bench_end = time.perf_counter()
    total_pipeline_duration = bench_end - bench_start

    print(f"Extraction completed in {extract_duration:.3f}s: target {extract_report['target_name']}")
    print(f"Total pipeline time: {total_pipeline_duration:.3f}s")

    # 4. Compare audio properties
    opt_wav_path = Path(f"outputs_clearvoice/jobs/{new_job_id}/target_speaker_person3.wav")
    assert opt_wav_path.exists(), f"Optimized WAV missing at {opt_wav_path}!"

    base_audio, base_sr = sf.read(str(baseline_wav_path), dtype="float32")
    opt_audio, opt_sr = sf.read(str(opt_wav_path), dtype="float32")

    base_info = sf.info(str(baseline_wav_path))
    opt_info = sf.info(str(opt_wav_path))

    # Numerical Metrics
    base_peak = float(np.max(np.abs(base_audio)))
    opt_peak = float(np.max(np.abs(opt_audio)))
    base_rms = float(np.sqrt(np.mean(base_audio**2)))
    opt_rms = float(np.sqrt(np.mean(opt_audio**2)))

    # Align lengths if minor sample padding
    min_len = min(len(base_audio), len(opt_audio))
    base_clip = base_audio[:min_len]
    opt_clip = opt_audio[:min_len]

    # Waveform Cosine Similarity
    dot_prod = np.dot(base_clip, opt_clip)
    norm_base = np.linalg.norm(base_clip)
    norm_opt = np.linalg.norm(opt_clip)
    cosine_sim = float(dot_prod / (norm_base * norm_opt + 1e-9))

    # Difference metrics
    diff = base_clip - opt_clip
    max_abs_diff = float(np.max(np.abs(diff)))
    mae = float(np.mean(np.abs(diff)))
    rmse = float(np.sqrt(np.mean(diff**2)))
    sqnr_db = float(10 * np.log10(np.sum(base_clip**2) / (np.sum(diff**2) + 1e-9)))

    # Durations
    base_tse_time = baseline_meta["total_av_mossformer2_time_sec"]
    base_total_time = baseline_meta["total_pipeline_time_sec"]
    opt_tse_time = round(extract_duration, 3)
    opt_total_time = round(total_pipeline_duration, 3)

    tse_speedup = (base_tse_time - opt_tse_time) / base_tse_time * 100
    tse_factor = base_tse_time / opt_tse_time
    total_speedup = (base_total_time - opt_total_time) / base_total_time * 100
    total_factor = base_total_time / opt_total_time

    comparison_results = {
        "baseline_job_id": baseline_meta["bench_job_id"],
        "optimized_job_id": new_job_id,
        "video_duration_sec": 26.01,
        "av_mossformer2_inference_time_sec": {
            "before_fp32": base_tse_time,
            "after_int8_threads8": opt_tse_time,
            "speedup_percentage": round(tse_speedup, 2),
            "speedup_factor": f"{tse_factor:.2f}x faster"
        },
        "total_pipeline_time_sec": {
            "before_fp32": base_total_time,
            "after_int8_threads8": opt_total_time,
            "speedup_percentage": round(total_speedup, 2),
            "speedup_factor": f"{total_factor:.2f}x faster"
        },
        "audio_properties": {
            "output_wav_duration_sec": {
                "before": round(base_info.duration, 2),
                "after": round(opt_info.duration, 2)
            },
            "sample_rate_hz": {
                "before": base_sr,
                "after": opt_sr
            },
            "channels": {
                "before": base_info.channels,
                "after": opt_info.channels
            },
            "file_size_bytes": {
                "before": baseline_wav_path.stat().st_size,
                "after": opt_wav_path.stat().st_size
            },
            "peak_amplitude": {
                "before": round(base_peak, 4),
                "after": round(opt_peak, 4)
            },
            "rms_energy": {
                "before": round(base_rms, 4),
                "after": round(opt_rms, 4)
            },
            "active_speech_sec": {
                "before": baseline_meta.get("active_speech_sec", 13.91),
                "after": extract_report["active_speech_duration_sec"]
            },
            "silence_sec": {
                "before": baseline_meta.get("silence_sec", 12.10),
                "after": extract_report["silence_duration_sec"]
            }
        },
        "waveform_numerical_fidelity": {
            "cosine_similarity": round(cosine_sim, 5),
            "max_absolute_difference": round(max_abs_diff, 5),
            "mean_absolute_error": round(mae, 6),
            "root_mean_squared_error": round(rmse, 6),
            "signal_to_quantization_noise_ratio_db": round(sqnr_db, 2)
        },
        "perceptual_metrics_availability": {
            "SI_SDR": "Not available (no isolated ground-truth reference audio exists for in-the-wild multi-speaker video mix)",
            "STOI": "Not available (requires clean reference speech signal recorded simultaneously without background/other speakers)",
            "PESQ": "Not available (requires clean narrow/wideband reference speech without multi-talker interference)"
        }
    }

    with open("optimization_comparison_report.json", "w") as f:
        json.dump(comparison_results, f, indent=2)

    print("\n" + "=" * 75)
    print("COMPARISON REPORT")
    print("=" * 75)
    print(f"AV-MossFormer2 Time:   {base_tse_time}s -> {opt_tse_time}s ({tse_speedup:.1f}% faster, {tse_factor:.2f}x)")
    print(f"Total Pipeline Time:   {base_total_time}s -> {opt_total_time}s ({total_speedup:.1f}% faster, {total_factor:.2f}x)")
    print(f"WAV Duration:          {opt_info.duration:.2f}s (Matches video: {opt_info.duration == 26.01})")
    print(f"Sample Rate:           {opt_sr} Hz (Mono: {opt_info.channels == 1})")
    print(f"Peak Amplitude:        {base_peak:.4f} -> {opt_peak:.4f}")
    print(f"RMS Energy:            {base_rms:.4f} -> {opt_rms:.4f}")
    print(f"Active Speech Span:    {extract_report['active_speech_duration_sec']}s (Silence: {extract_report['silence_duration_sec']}s)")
    print(f"Cosine Similarity:     {cosine_sim:.5f}")
    print(f"SQNR (Signal-to-Noise):{sqnr_db:.2f} dB")
    print("=" * 75)

if __name__ == "__main__":
    run_verification()
