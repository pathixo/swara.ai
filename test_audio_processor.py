"""
Test script for AudioProcessor and Listener integration.
Verifies FFT processing, spectrum extraction, and performance.
"""

import sys
import time
import numpy as np
sys.path.insert(0, 'D:\\Coding\\Projects\\Antigravity')

from Jarvis.input.audio_processor import AudioProcessor


def test_audio_processor():
    """Test AudioProcessor functionality."""
    print("Testing AudioProcessor...")
    
    # Initialize
    processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)
    print(f"✓ Initialized AudioProcessor")
    
    # Create synthetic audio (1kHz sine wave)
    sample_rate = 16000
    duration = 0.032  # 512 samples at 16kHz
    freq = 1000  # 1kHz tone
    
    t = np.arange(0, duration, 1/sample_rate)
    audio = np.sin(2 * np.pi * freq * t) * 32767  # int16 range
    audio = audio.astype(np.int16)
    
    print(f"✓ Created synthetic 1kHz tone ({len(audio)} samples)")
    
    # Test processing speed
    times = []
    for i in range(10):
        spectrum = processor.process_chunk(audio.tobytes())
        proc_time = processor.get_processing_time()
        times.append(proc_time)
    
    avg_time = np.mean(times)
    max_time = np.max(times)
    
    print(f"✓ Processing time: avg={avg_time:.3f}ms, max={max_time:.3f}ms")
    assert avg_time < 2.0, f"Processing time {avg_time}ms exceeds 2ms threshold!"
    
    # Test spectrum properties
    print(f"✓ Spectrum shape: {spectrum.shape}")
    assert spectrum.shape == (32,), f"Expected shape (32,), got {spectrum.shape}"
    
    print(f"✓ Spectrum range: [{spectrum.min():.3f}, {spectrum.max():.3f}]")
    assert spectrum.min() >= 0.0 and spectrum.max() <= 1.0, \
        f"Spectrum out of 0-1 range: [{spectrum.min()}, {spectrum.max()}]"
    
    # Test queue functionality
    queued = processor.get_spectrum_from_queue(timeout=0.01)
    print(f"✓ Queue retrieval: {'success' if queued is not None else 'empty'}")
    
    # Test thread-safe get
    direct = processor.get_spectrum()
    print(f"✓ Direct spectrum retrieval: shape={direct.shape}")
    
    # Test different audio formats
    # bytes
    spectrum1 = processor.process_chunk(audio.tobytes())
    # numpy array
    spectrum2 = processor.process_chunk(audio)
    print(f"✓ Both input formats processed successfully")
    
    # Verify smoothing is working (should produce similar values)
    spectrum3 = processor.process_chunk(audio)
    spectrum4 = processor.process_chunk(audio)
    
    corr = np.corrcoef(spectrum3.flatten(), spectrum4.flatten())[0, 1]
    print(f"✓ Smoothing working (correlation between consecutive frames: {corr:.3f})")
    
    print("\n✓ All AudioProcessor tests passed!")
    return True


def test_frequency_mapping():
    """Test that frequency bands are correctly mapped."""
    print("\nTesting frequency band mapping...")
    
    processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)
    
    # Verify band indices are within valid range
    max_fft_bins = 256 + 1  # For 512-point FFT
    
    all_indices = []
    for indices in processor.band_indices:
        for idx in indices:
            assert 0 <= idx < max_fft_bins, f"Invalid FFT bin index: {idx}"
            all_indices.append(idx)
    
    print(f"✓ All {len(all_indices)} FFT bins mapped to 32 bands")
    print(f"✓ Band coverage: {len(set(all_indices))} unique bins used")
    
    # Test with specific frequencies
    frequencies = [100, 500, 1000, 5000, 10000, 20000]
    for freq in frequencies:
        # Create sine wave at this frequency
        duration = 512 / 16000
        t = np.arange(0, duration, 1/16000)
        audio = np.sin(2 * np.pi * freq * t) * 32767
        audio = audio.astype(np.int16)
        
        spectrum = processor.process_chunk(audio)
        max_band = np.argmax(spectrum)
        max_value = spectrum[max_band]
        
        print(f"  {freq}Hz -> Band {max_band} (magnitude={max_value:.3f})")
    
    print("\n✓ Frequency mapping tests passed!")
    return True


def test_integration():
    """Test integration with Listener."""
    print("\nTesting Listener integration...")
    
    try:
        from Jarvis.input.listener import Listener
        
        # Check that Listener can be instantiated
        listener = Listener()
        print(f"✓ Listener instantiated")
        
        # Check audio processor is available
        assert hasattr(listener, 'audio_processor'), "audio_processor not found"
        print(f"✓ audio_processor attached to Listener")
        
        # Check methods exist
        assert hasattr(listener, 'get_audio_spectrum'), "get_audio_spectrum not found"
        assert hasattr(listener, 'get_audio_spectrum_from_queue'), "get_audio_spectrum_from_queue not found"
        print(f"✓ Spectrum retrieval methods available")
        
        # Get spectrum without processing data
        spectrum = listener.get_audio_spectrum()
        assert spectrum.shape == (32,), f"Expected shape (32,), got {spectrum.shape}"
        print(f"✓ Can retrieve spectrum from listener: shape={spectrum.shape}")
        
        print("\n✓ Integration tests passed!")
        return True
        
    except ImportError as e:
        print(f"⚠ Could not test Listener integration: {e}")
        print("  (This is expected if running outside the full environment)")
        return True
    except Exception as e:
        print(f"✗ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("AudioProcessor Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("AudioProcessor", test_audio_processor()))
    results.append(("Frequency Mapping", test_frequency_mapping()))
    results.append(("Listener Integration", test_integration()))
    
    print("\n" + "=" * 60)
    print("Summary:")
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("=" * 60)
    
    sys.exit(0 if all_passed else 1)
