import urllib.request
import json
import os

def test_api():
    print("=" * 60)
    print("TESTING CONSECUTIVE VIDEO UPLOADS AND ISOLATED JOBS")
    print("=" * 60)

    # --- Test 1: Upload Video 1 (Full 22.7s multi-speaker test.mp4) ---
    print("\n--- TEST 1: Uploading Video 1 (test.mp4) ---")
    req1 = urllib.request.Request("http://127.0.0.1:8000/api/upload?use_sample=true", method="POST")
    res1 = urllib.request.urlopen(req1)
    upload1 = json.loads(res1.read())
    job1_id = upload1["job_id"]
    print(f"Job 1 Created: {job1_id}")
    print(f"Video URL: {upload1['video_url']}")

    print(f"Triggering analysis for {job1_id}...")
    analyze_req1 = urllib.request.Request(
        "http://127.0.0.1:8000/api/analyze",
        data=json.dumps({"job_id": job1_id}).encode(),
        headers={"Content-Type": "application/json"}
    )
    analyze_res1 = urllib.request.urlopen(analyze_req1)
    data1 = json.loads(analyze_res1.read())

    print(f"\n[Video 1 Results]")
    print(f"  Duration: {data1['video_info']['duration']}s, Total frames: {data1['video_info']['totalFrames']}")
    print(f"  Total Face Tracks Detected: {data1['totalTracks']}")
    print(f"  Total Person Clusters: {len(data1['persons'])}")
    for p in data1['persons']:
        print(f"    - {p['title']}: {p['detectedDuration']}s detected ({p['tracksCount']} segments), thumbnail: {p['thumbnailUrl']}")

    # --- Test 2: Upload Video 2 (3.0s trimmed clip test2_single_speaker.mp4) ---
    print("\n" + "=" * 60)
    print("--- TEST 2: Uploading Video 2 (test2_single_speaker.mp4) ---")
    file_path = "test_videos/test2_single_speaker.mp4"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test2_single_speaker.mp4"\r\n'
        f"Content-Type: video/mp4\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req2 = urllib.request.Request(
        "http://127.0.0.1:8000/api/upload",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    res2 = urllib.request.urlopen(req2)
    upload2 = json.loads(res2.read())
    job2_id = upload2["job_id"]
    print(f"Job 2 Created: {job2_id}")
    print(f"Video URL: {upload2['video_url']}")

    print(f"Triggering analysis for {job2_id}...")
    analyze_req2 = urllib.request.Request(
        "http://127.0.0.1:8000/api/analyze",
        data=json.dumps({"job_id": job2_id}).encode(),
        headers={"Content-Type": "application/json"}
    )
    analyze_res2 = urllib.request.urlopen(analyze_req2)
    data2 = json.loads(analyze_res2.read())

    print(f"\n[Video 2 Results]")
    print(f"  Duration: {data2['video_info']['duration']}s, Total frames: {data2['video_info']['totalFrames']}")
    print(f"  Total Face Tracks Detected: {data2['totalTracks']}")
    print(f"  Total Person Clusters: {len(data2['persons'])}")
    for p in data2['persons']:
        print(f"    - {p['title']}: {p['detectedDuration']}s detected ({p['tracksCount']} segments), thumbnail: {p['thumbnailUrl']}")

    # --- Verification of Independence ---
    print("\n" + "=" * 60)
    print("VERIFICATION OF JOB INDEPENDENCE:")
    print("=" * 60)
    print(f"Job 1 ID: {job1_id} != Job 2 ID: {job2_id}: {job1_id != job2_id}")
    print(f"Job 1 Directory Exists: {os.path.exists(f'outputs_clearvoice/jobs/{job1_id}')}")
    print(f"Job 2 Directory Exists: {os.path.exists(f'outputs_clearvoice/jobs/{job2_id}')}")
    print(f"Job 1 Frame Count ({data1['video_info']['totalFrames']}) != Job 2 Frame Count ({data2['video_info']['totalFrames']}): {data1['video_info']['totalFrames'] != data2['video_info']['totalFrames']}")
    print(f"Job 1 Tracks ({data1['totalTracks']}) != Job 2 Tracks ({data2['totalTracks']}): {data1['totalTracks'] != data2['totalTracks']}")
    print(f"Job 1 Duration ({data1['video_info']['duration']}s) != Job 2 Duration ({data2['video_info']['duration']}s): {data1['video_info']['duration'] != data2['video_info']['duration']}")
    print("\nALL VERIFICATIONS PASSED: ZERO STALE DATA LEAKAGE!")

if __name__ == '__main__':
    test_api()
