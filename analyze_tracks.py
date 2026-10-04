import os
import pickle
import types
import numpy as np
from clearvoice.utils.video_process import track_shot

cache_path = 'outputs_clearvoice/results/all_faces.pkl'
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

print(f"Total detected tracks: {len(tracks)}")
for i, t in enumerate(tracks):
    xs = [(b[0] + b[2]) / 2 for b in t['bbox']]
    ys = [(b[1] + b[3]) / 2 for b in t['bbox']]
    ws = [b[2] - b[0] for b in t['bbox']]
    hs = [b[3] - b[1] for b in t['bbox']]
    avg_x = np.mean(xs)
    avg_y = np.mean(ys)
    avg_w = np.mean(ws)
    avg_h = np.mean(hs)
    start_sec = t['frame'][0] / 25.0
    end_sec = (t['frame'][-1] + 1) / 25.0
    dur = len(t['frame']) / 25.0
    print(f"Track {i:2d}: frames {t['frame'][0]:3d}-{t['frame'][-1]:3d} ({start_sec:5.2f}s - {end_sec:5.2f}s, dur {dur:4.2f}s) | Center ({avg_x:6.1f}, {avg_y:6.1f}) | BBox {avg_w:5.1f}x{avg_h:5.1f}")
