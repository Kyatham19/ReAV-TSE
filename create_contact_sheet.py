import os
import pickle
import types
import cv2
import numpy as np
from clearvoice.utils.video_process import track_shot

def main():
    video_path = "outputs_clearvoice/AV_MossFormer2_TSE_16K/test_videos/test/py_video/video.avi"
    cache_path = "outputs_clearvoice/results/all_faces.pkl"
    out_dir = "outputs_clearvoice/results"
    thumb_dir = os.path.join(out_dir, "track_thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    with open(cache_path, "rb") as f:
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

    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Total video frames: {total_frames}")

    # Read all frames into memory
    frames = []
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()

    cards = []
    card_w, card_h = 240, 280

    for tidx, track in enumerate(tracks):
        mid_idx = len(track['frame']) // 2
        fidx = track['frame'][mid_idx]
        bbox = track['bbox'][mid_idx]  # [x1, y1, x2, y2]
        x1, y1, x2, y2 = [int(v) for v in bbox]

        # Pad bbox slightly
        bw = x2 - x1
        bh = y2 - y1
        pad_x = int(bw * 0.2)
        pad_y = int(bh * 0.2)
        h, w = frames[fidx].shape[:2]
        px1 = max(0, x1 - pad_x)
        py1 = max(0, y1 - pad_y)
        px2 = min(w, x2 + pad_x)
        py2 = min(h, y2 + pad_y)

        face_crop = frames[fidx][py1:py2, px1:px2]
        if face_crop.size == 0:
            face_crop = np.zeros((180, 180, 3), dtype=np.uint8)
        else:
            face_crop = cv2.resize(face_crop, (200, 200))

        # Save individual thumbnail
        thumb_path = os.path.join(thumb_dir, f"track_{tidx:02d}.jpg")
        cv2.imwrite(thumb_path, face_crop)

        # Create card for contact sheet
        card = np.full((card_h, card_w, 3), 30, dtype=np.uint8)
        # Paste face thumbnail at top
        card[10:210, 20:220] = face_crop

        # Text info
        start_t = track['frame'][0] / 25.0
        end_t = (track['frame'][-1] + 1) / 25.0
        dur_t = len(track['frame']) / 25.0

        cv2.putText(card, f"Track {tidx}", (20, 230), cv2.FONT_HERSHEY_DUPLEX, 0.65, (0, 255, 255), 1)
        cv2.putText(card, f"{start_t:.2f}s - {end_t:.2f}s ({dur_t:.2f}s)", (20, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
        cv2.putText(card, f"Frames {track['frame'][0]}-{track['frame'][-1]}", (20, 268), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1)
        cards.append(card)

    # Grid of cards: 7 columns x 3 rows = 21 cards
    cols = 7
    rows = (len(cards) + cols - 1) // cols
    sheet = np.full((rows * card_h, cols * card_w, 3), 20, dtype=np.uint8)

    for i, card in enumerate(cards):
        r = i // cols
        c = i % cols
        sheet[r * card_h:(r + 1) * card_h, c * card_w:(c + 1) * card_w] = card

    contact_sheet_path = os.path.join(out_dir, "contact_sheet.jpg")
    cv2.imwrite(contact_sheet_path, sheet)
    print(f"Saved contact sheet to: {contact_sheet_path}")
    print(f"Saved individual thumbnails to: {thumb_dir}")

if __name__ == '__main__':
    main()
