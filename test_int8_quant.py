import time
import torch
import torch.ao.quantization as quantization
import numpy as np
from job_pipeline import get_clearvoice_model

def test_quant():
    print("=" * 60)
    print("TESTING DYNAMIC INT8 QUANTIZATION ON AV-MOSSFORMER2")
    print("=" * 60)

    model, args = get_clearvoice_model()
    torch.set_num_threads(8)

    # Test baseline 2.0s
    audio = torch.randn(1, 32000)
    video = torch.randn(1, 50, 112, 112)

    print("\n1. Measuring Baseline FP32 (2.0s audio):")
    t0 = time.perf_counter()
    with torch.inference_mode():
        base_out = model(audio, video)
    dur_base = time.perf_counter() - t0
    print(f"FP32 Time: {dur_base:.3f}s")

    print("\n2. Applying torch.ao.quantization.quantize_dynamic to Linear layers...")
    try:
        quantized_model = quantization.quantize_dynamic(
            model,
            {torch.nn.Linear},
            dtype=torch.qint8
        )
        print("Dynamic quantization applied successfully!")

        print("\n3. Measuring INT8 Quantized (2.0s audio):")
        t0 = time.perf_counter()
        with torch.inference_mode():
            quant_out = quantized_model(audio, video)
        dur_quant = time.perf_counter() - t0
        print(f"INT8 Time: {dur_quant:.3f}s")
        print(f"Speedup: {dur_base / dur_quant:.2f}x faster!")

        # Check similarity between FP32 and INT8 output
        cos_sim = torch.nn.functional.cosine_similarity(base_out.flatten(), quant_out.flatten(), dim=0)
        print(f"Cosine Similarity between FP32 and INT8: {cos_sim.item():.4f}")

    except Exception as e:
        print(f"Quantization failed: {e}")

if __name__ == "__main__":
    test_quant()
