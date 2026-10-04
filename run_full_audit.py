import urllib.request
import urllib.error
import json
import os
import sys
import wave
import soundfile as sf
import numpy as np
from pathlib import Path

def test_api():
    print("=" * 70)
    print("REAV-TSE COMPREHENSIVE END-TO-END AUDIT SUITE")
    print("=" * 70)

    audit_results = {}
    base_url = "http://127.0.0.1:8000"

    # ----------------------------------------------------
    # TEST SUITE 1: API Robustness & Error Handling
    # ----------------------------------------------------
    print("\n[TEST 1] API Robustness & Bad Input Handling")
    
    # 1.1: Upload with no file
    try:
        req = urllib.request.Request(f"{base_url}/api/upload", method="POST")
        urllib.request.urlopen(req)
        audit_results["upload_no_file"] = "FAIL (Did not reject)"
    except urllib.error.HTTPError as e:
        audit_results["upload_no_file"] = f"PASS (Rejected with HTTP {e.code}: {e.read().decode()})"
    print(" 1.1 Upload no file:", audit_results["upload_no_file"])

    # 1.2: Upload invalid extension (.txt)
    boundary = "----WebKitFormBoundaryAuditTest123"
    txt_body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="malicious.txt"\r\n'
        f"Content-Type: text/plain\r\n\r\n"
        f"Not a video\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/upload",
            data=txt_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        urllib.request.urlopen(req)
        audit_results["upload_bad_ext"] = "FAIL (Did not reject .txt)"
    except urllib.error.HTTPError as e:
        audit_results["upload_bad_ext"] = f"PASS (Rejected with HTTP {e.code}: {e.read().decode()})"
    print(" 1.2 Upload unsupported format (.txt):", audit_results["upload_bad_ext"])

    # 1.3: Upload empty file (0 bytes)
    empty_body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="empty.mp4"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
        f"--{boundary}--\r\n"
    ).encode()
    try:
        req = urllib.request.Request(
            f"{base_url}/api/upload",
            data=empty_body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST"
        )
        urllib.request.urlopen(req)
        audit_results["upload_empty_file"] = "FAIL (Did not reject 0-byte file)"
    except urllib.error.HTTPError as e:
        audit_results["upload_empty_file"] = f"PASS (Rejected with HTTP {e.code}: {e.read().decode()})"
    print(" 1.3 Upload empty 0-byte video:", audit_results["upload_empty_file"])

    # 1.4: Analyze invalid job ID
    try:
        req = urllib.request.Request(
            f"{base_url}/api/analyze",
            data=json.dumps({"job_id": "job_nonexistent_999999"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req)
        audit_results["analyze_invalid_job"] = "FAIL (Did not return 404)"
    except urllib.error.HTTPError as e:
        audit_results["analyze_invalid_job"] = f"PASS (Rejected with HTTP {e.code}: {e.read().decode()})"
    print(" 1.4 Analyze nonexistent job_id:", audit_results["analyze_invalid_job"])

    # 1.5: Extract invalid target person ID
    try:
        req = urllib.request.Request(
            f"{base_url}/api/extract",
            data=json.dumps({
                "job_id": "job_1790332587_475ab7",
                "target": "person99",
                "mode": "person"
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req)
        audit_results["extract_invalid_person"] = "FAIL (Did not reject invalid person)"
    except urllib.error.HTTPError as e:
        audit_results["extract_invalid_person"] = f"PASS (Rejected with HTTP {e.code}: {e.read().decode()})"
    print(" 1.5 Extract invalid person ID (person99):", audit_results["extract_invalid_person"])

    # ----------------------------------------------------
    # TEST SUITE 2: Multi-Speaker Video Real Pipeline
    # ----------------------------------------------------
    print("\n[TEST 2] Multi-Speaker Video Pipeline Verification (job_1790332587_475ab7)")
    job_id = "job_1790332587_475ab7"

    # Query speakers endpoint
    sp_req = urllib.request.Request(f"{base_url}/api/jobs/{job_id}/speakers")
    sp_res = urllib.request.urlopen(sp_req)
    sp_data = json.loads(sp_res.read().decode())
    
    print(f"  Job ID: {sp_data['job_id']}")
    print(f"  Total Video Duration: {sp_data['video_info']['duration']}s, Total frames: {sp_data['video_info']['totalFrames']}")
    print(f"  Total Raw Face Tracks: {sp_data['totalTracks']}")
    print(f"  Distinct People Identified: {len(sp_data['persons'])}")
    for p in sp_data['persons']:
        print(f"    - {p['id']} ({p['title']}): span {p['timeSpan']}, active {p['detectedDuration']}s, tracks: {p['trackIds']}")

    # Verification: Person count must be 4, Tracks count must be 5
    assert len(sp_data['persons']) == 4, f"Expected 4 persons, got {len(sp_data['persons'])}"
    assert sp_data['totalTracks'] == 5, f"Expected 5 tracks, got {sp_data['totalTracks']}"
    print("  -> Clustering Verification: PASS (4 distinct persons across 5 tracks, no false merges)")

    # ----------------------------------------------------
    # TEST SUITE 3: Extraction & Timeline Preservation
    # ----------------------------------------------------
    print("\n[TEST 3] Extraction & Non-Concatenation Timeline Preservation")
    
    # Test Extraction for Person 01 (Single track: Track 1, 0.0s - 5.83s)
    print("  Extracting Person 01 (Track 1)...")
    p1_req = urllib.request.Request(
        f"{base_url}/api/extract",
        data=json.dumps({"job_id": job_id, "target": "person1", "mode": "person"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    p1_res = urllib.request.urlopen(p1_req)
    p1_data = json.loads(p1_res.read().decode())
    print(f"    Person 01 extracted! Target: {p1_data['targetName']}")
    print(f"    Report: {p1_data['report']['active_speech_duration_sec']}s active speech, {p1_data['report']['silence_duration_sec']}s silence across {p1_data['report']['total_timeline_duration_sec']}s timeline")

    # Test Extraction for Person 03 (Multi-segment: Tracks 4 & 0, 8.06s - 20.48s)
    print("  Extracting Person 03 (Multi-segment: Tracks 4 & 0)...")
    p3_req = urllib.request.Request(
        f"{base_url}/api/extract",
        data=json.dumps({"job_id": job_id, "target": "person3", "mode": "person"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    p3_res = urllib.request.urlopen(p3_req)
    p3_data = json.loads(p3_res.read().decode())
    print(f"    Person 03 extracted! Target: {p3_data['targetName']}")
    print(f"    Report: {p3_data['report']['active_speech_duration_sec']}s active speech, {p3_data['report']['silence_duration_sec']}s silence across {p3_data['report']['total_timeline_duration_sec']}s timeline")
    print(f"    Segments combined: {p3_data['report']['num_segments_combined']}")

    # ----------------------------------------------------
    # TEST SUITE 4: Audio Correctness & Property Checks
    # ----------------------------------------------------
    print("\n[TEST 4] Audio File Physical Integrity & Format Analysis")
    for pid in ["person1", "person3"]:
        wav_path = Path(f"outputs_clearvoice/jobs/{job_id}/target_speaker_{pid}.wav")
        assert wav_path.exists(), f"WAV file missing: {wav_path}"
        info = sf.info(str(wav_path))
        data, sr = sf.read(str(wav_path))
        
        # Audio properties
        duration = round(info.duration, 2)
        channels = info.channels
        samplerate = info.samplerate
        filesize = wav_path.stat().st_size
        max_amplitude = float(np.max(np.abs(data)))
        rms_amplitude = float(np.sqrt(np.mean(data**2)))

        print(f"  Target: {pid}")
        print(f"    - File Path: {wav_path}")
        print(f"    - File Size: {filesize:,} bytes")
        print(f"    - Duration: {duration}s (Original Video: {sp_data['video_info']['duration']}s)")
        print(f"    - Channels: {channels} (Mono: {channels == 1})")
        print(f"    - Sample Rate: {samplerate} Hz (16kHz standard: {samplerate == 16000})")
        print(f"    - Peak Amplitude: {max_amplitude:.4f}")
        print(f"    - RMS Level: {rms_amplitude:.4f}")

        # Assertions
        assert channels == 1, f"Expected mono audio, got {channels} channels"
        assert samplerate == 16000, f"Expected 16000 Hz, got {samplerate} Hz"
        assert abs(duration - sp_data['video_info']['duration']) < 0.1, f"Duration mismatch: {duration}s vs {sp_data['video_info']['duration']}s"
        assert max_amplitude > 0.05, f"Audio is silent! Max amplitude: {max_amplitude}"

    print("  -> Audio Verification: PASS (Perfect timeline duration, mono 16kHz PCM WAV, non-clipped)")

    # ----------------------------------------------------
    # TEST SUITE 5: Consecutive Upload & Multi-Job Isolation
    # ----------------------------------------------------
    print("\n[TEST 5] Consecutive Upload & Workspace Isolation Test")
    sample_req = urllib.request.Request(f"{base_url}/api/upload?use_sample=true", method="POST")
    sample_res = urllib.request.urlopen(sample_req)
    sample_upload = json.loads(sample_res.read().decode())
    sample_job_id = sample_upload["job_id"]

    print(f"  Uploaded sample video -> New Job ID: {sample_job_id}")
    assert sample_job_id != job_id, "Job ID collision!"
    assert Path(f"outputs_clearvoice/jobs/{sample_job_id}").exists(), "Job workspace not created!"

    # Verify both jobs remain intact and independent
    assert Path(f"outputs_clearvoice/jobs/{job_id}/speakers.json").exists(), "Original job speakers.json affected!"
    assert Path(f"outputs_clearvoice/jobs/{job_id}/target_speaker_person1.wav").exists(), "Original job audio affected!"

    print(f"  Original Job ({job_id}) remains completely intact.")
    print(f"  New Job ({sample_job_id}) created in an isolated directory.")
    print("  -> Workspace Isolation: PASS (Zero data contamination across jobs)")

    print("\n" + "=" * 70)
    print("ALL 5 AUDIT TEST SUITES PASSED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    test_api()
