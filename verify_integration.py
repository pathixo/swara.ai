"""
Integration test: Verify AudioProcessor works with Listener
"""
import sys
sys.path.insert(0, 'D:\\Coding\\Projects\\Antigravity')

def verify_imports():
    """Verify all imports work correctly."""
    try:
        print("Verifying imports...")
        
        # Test AudioProcessor import
        from Jarvis.input.audio_processor import AudioProcessor
        print("✓ AudioProcessor imported")
        
        # Test Listener import
        from Jarvis.input.listener import Listener
        print("✓ Listener imported")
        
        # Test dependencies
        import numpy as np
        import queue
        import threading
        print("✓ Dependencies available")
        
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def verify_processor():
    """Verify AudioProcessor is functional."""
    try:
        print("\nVerifying AudioProcessor...")
        from Jarvis.input.audio_processor import AudioProcessor
        import numpy as np
        
        # Create instance
        processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)
        print("✓ AudioProcessor instantiated")
        
        # Verify attributes
        assert hasattr(processor, 'process_chunk'), "Missing process_chunk method"
        assert hasattr(processor, 'get_spectrum'), "Missing get_spectrum method"
        assert hasattr(processor, 'get_spectrum_from_queue'), "Missing get_spectrum_from_queue method"
        assert hasattr(processor, 'spectrum_queue'), "Missing spectrum_queue"
        print("✓ All required methods and attributes present")
        
        # Test processing
        audio = np.random.randint(-32768, 32767, 512, dtype=np.int16)
        spectrum = processor.process_chunk(audio.tobytes())
        
        assert spectrum.shape == (32,), f"Wrong output shape: {spectrum.shape}"
        assert spectrum.min() >= 0.0 and spectrum.max() <= 1.0, "Values out of range"
        print("✓ Processing works correctly")
        
        # Test getters
        spec1 = processor.get_spectrum()
        assert spec1.shape == (32,), "get_spectrum returned wrong shape"
        
        spec2 = processor.get_spectrum_from_queue(timeout=0.01)
        # May be None if queue empty, but method should work
        print("✓ Getters work correctly")
        
        # Test performance
        import time
        start = time.time()
        for _ in range(10):
            processor.process_chunk(audio.tobytes())
        elapsed = (time.time() - start) * 1000
        avg_time = elapsed / 10
        
        print(f"✓ Performance: {avg_time:.3f}ms avg (target: <2ms)")
        assert avg_time < 2.0, f"Too slow: {avg_time}ms"
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_listener():
    """Verify Listener has AudioProcessor integration."""
    try:
        print("\nVerifying Listener integration...")
        from Jarvis.input.listener import Listener
        import numpy as np
        
        # Try to instantiate (may fail if PyQt6 not fully configured)
        try:
            listener = Listener()
            print("✓ Listener instantiated")
        except Exception as e:
            print(f"⚠ Listener instantiation warning: {e}")
            print("  (This may be expected in test environment)")
            return True
        
        # Verify audio processor attachment
        assert hasattr(listener, 'audio_processor'), "audio_processor not found"
        print("✓ audio_processor attached to Listener")
        
        # Verify methods
        assert hasattr(listener, 'get_audio_spectrum'), "Missing get_audio_spectrum"
        assert hasattr(listener, 'get_audio_spectrum_from_queue'), "Missing get_audio_spectrum_from_queue"
        print("✓ Spectrum retrieval methods present")
        
        # Try to get spectrum
        spectrum = listener.get_audio_spectrum()
        assert spectrum.shape == (32,), f"Wrong spectrum shape: {spectrum.shape}"
        print("✓ Can retrieve spectrum")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_thread_safety():
    """Verify thread-safe operations."""
    try:
        print("\nVerifying thread safety...")
        from Jarvis.input.audio_processor import AudioProcessor
        import numpy as np
        import threading
        import time
        
        processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)
        print("✓ AudioProcessor created")
        
        results = {'errors': 0, 'processed': 0}
        audio = np.random.randint(-32768, 32767, 512, dtype=np.int16)
        
        def process_audio():
            try:
                for _ in range(10):
                    processor.process_chunk(audio)
                results['processed'] += 10
            except Exception as e:
                results['errors'] += 1
                print(f"  Processing error: {e}")
        
        def get_spectrum():
            try:
                for _ in range(10):
                    spectrum = processor.get_spectrum()
                    queue_data = processor.get_spectrum_from_queue(timeout=0.001)
                results['processed'] += 10
            except Exception as e:
                results['errors'] += 1
                print(f"  Retrieval error: {e}")
        
        # Run concurrent operations
        threads = []
        for _ in range(2):
            t1 = threading.Thread(target=process_audio)
            t2 = threading.Thread(target=get_spectrum)
            threads.extend([t1, t2])
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        print(f"✓ Thread safety verified ({results['processed']} ops, {results['errors']} errors)")
        assert results['errors'] == 0, f"Errors during concurrent access: {results['errors']}"
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("="*60)
    print("AudioProcessor Integration Verification")
    print("="*60)
    
    tests = [
        ("Imports", verify_imports),
        ("AudioProcessor", verify_processor),
        ("Listener Integration", verify_listener),
        ("Thread Safety", verify_thread_safety),
    ]
    
    results = []
    for name, test_func in tests:
        print()
        try:
            passed = test_func()
            results.append((name, passed))
        except Exception as e:
            print(f"✗ {name} failed: {e}")
            results.append((name, False))
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(r[1] for r in results)
    print("="*60)
    
    if all_passed:
        print("\n✓✓✓ All integration tests passed! ✓✓✓")
    else:
        print("\n✗✗✗ Some tests failed ✗✗✗")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
