import time
import torch
import numpy as np
from job_pipeline import get_clearvoice_model
from clearvoice.utils.decode import decode_one_audio_AV_MossFormer2_TSE_16K

def test_optimized():
    print("=" * 60)
    print("TESTING OPTIMIZED AV-MOSSFORMER2 INFERENCE")
    print("=" * 60)

    # 11.13 seconds test input (matching Track 0)
    sr = 16000
    fps = 25
    audio_len = int(11.13 * sr) # 178080 samples
    visual_len = int(11.13 * fps) # 278 frames

    audio_in = np.random.randn(1, audio_len).astype(np.float32)
    visual_in = np.random.randn(1, visual_len, 112, 112).astype(np.float32)

    model, args = get_clearvoice_model()

    # Apply optimizations:
    # 1. Optimal CPU threads (8 cores)
    torch.set_num_threads(8)
    
    # 2. Increase decode_window from 3s to 6s
    # (Reduces number of sliding forward passes from 7 to ~3)
    orig_window = args.decode_window
    orig_length = args.one_time_decode_length

    args.decode_window = 6
    args.one_time_decode_length = 6

    print(f"Running 11.13s audio inference with decode_window = {args.decode_window}s, threads = 8...")
    t0 = time.perf_counter()
    with torch.inference_mode():
        est_audio = decode_one_audio_AV_MossFormer2_TSE_16K(model, (audio_in, visual_in), args)
    t1 = time.perf_counter()

    dur = t1 - t0
    print(f"\n11.13s Audio Inference Time: {dur:.3f}s (Baseline was 316.165s)")
    print(f"Speedup: {316.165 / dur:.2f}x faster!")
    print(f"Output shape: {est_audio.shape}")

if __name__ == "__main__":
    test_optimized()
