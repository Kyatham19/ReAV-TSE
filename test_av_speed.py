import time
import torch
import numpy as np
import soundfile as sf
from job_pipeline import get_clearvoice_model, fixed_overlap_and_add
from clearvoice.utils.decode import decode_one_audio_AV_MossFormer2_TSE_16K

def test_speed():
    print("=" * 60)
    print("DIAGNOSTIC: AV-MossFormer2 CPU Threading & Optimization")
    print("=" * 60)

    # Prepare dummy 2-second audio (32000 samples) and visual (50 frames of 112x112)
    sr = 16000
    audio_len = 32000 # 2.0s
    visual_len = 50   # 2.0s @ 25fps

    audio_in = np.random.randn(1, audio_len).astype(np.float32)
    visual_in = np.random.randn(1, visual_len, 112, 112).astype(np.float32)

    model, args = get_clearvoice_model()

    # Test different thread counts
    for num_threads in [4, 6, 8]:
        torch.set_num_threads(num_threads)
        print(f"\n--- Testing with torch.set_num_threads({num_threads}) ---")
        
        t0 = time.perf_counter()
        with torch.inference_mode():
            out = decode_one_audio_AV_MossFormer2_TSE_16K(model, (audio_in, visual_in), args)
        t1 = time.perf_counter()
        dur = t1 - t0
        rtf = dur / 2.0
        print(f"2.0s Audio Inference Time: {dur:.3f}s (RTF: {rtf:.1f}x real-time)")

if __name__ == "__main__":
    test_speed()
