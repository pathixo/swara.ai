"""
Simple inline test for AudioProcessor - verifies core functionality.
"""
import sys
sys.path.insert(0, 'D:\\Coding\\Projects\\Antigravity')

import numpy as np
from Jarvis.input.audio_processor import AudioProcessor

def test():
    print("Testing AudioProcessor...")
    
    # Initialize
    processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)
    print(f"✓ Initialized: {processor.num_bands} bands, FFT size {processor.fft_size}")
    
    # Create synthetic audio (1kHz sine wave, 512 samples)
    sample_rate = 16000
    duration = 512 / sample_rate  # 0.032 seconds
    freq = 1000  # 1kHz
    
    t = np.arange(0, duration, 1/sample_rate)
    audio = np.sin(2 * np.pi * freq * t) * 32767  # int16 range
    audio = audio.astype(np.int16)
    
    print(f"✓ Created 1kHz sine wave: {len(audio)} samples")
    
    # Test processing
    import time
    start = time.time()
    spectrum = processor.process_chunk(audio.tobytes())
    elapsed = (time.time() - start) * 1000
    
    print(f"✓ Processing time: {elapsed:.3f}ms")
    assert elapsed < 2.0, f"Too slow: {elapsed}ms"
    
    # Test output properties
    assert spectrum.shape == (32,), f"Wrong shape: {spectrum.shape}"
    assert spectrum.min() >= 0.0 and spectrum.max() <= 1.0, \
        f"Out of range: [{spectrum.min()}, {spectrum.max()}]"
    
    print(f"✓ Output shape: {spectrum.shape}")
    print(f"✓ Value range: [{spectrum.min():.3f}, {spectrum.max():.3f}]")
    
    # Test queue
    queued = processor.get_spectrum_from_queue(timeout=0.01)
    print(f"✓ Queue: {'has data' if queued is not None else 'empty'}")
    
    # Test direct access
    direct = processor.get_spectrum()
    print(f"✓ Direct spectrum: {direct.shape}")
    
    # Test both input formats
    spec_bytes = processor.process_chunk(audio.tobytes())
    spec_array = processor.process_chunk(audio)
    print(f"✓ Both input formats work")
    
    # Test performance over 10 iterations
    times = []
    for i in range(10):
        start = time.time()
        processor.process_chunk(audio)
        times.append((time.time() - start) * 1000)
    
    avg_time = np.mean(times)
    max_time = np.max(times)
    print(f"✓ Performance (10 iterations): avg={avg_time:.3f}ms, max={max_time:.3f}ms")
    
    print("\n✓✓✓ All tests passed! ✓✓✓")
    return True

if __name__ == "__main__":
    try:
        success = test()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
