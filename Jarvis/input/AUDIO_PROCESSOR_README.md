# Audio Processor - Wave Visualization Module

## Overview

The `AudioProcessor` class provides FFT-based frequency analysis to extract audio data for wave visualization in Jarvis. It processes microphone input into 32 normalized frequency bands, enabling real-time audio spectrum visualization.

## Architecture

### Key Features

- **FFT Processing**: 512-sample Hann-windowed FFT for frequency extraction
- **32 Frequency Bands**: Logarithmic scale mapping from 20Hz to 20kHz
- **Normalized Output**: All frequency bands normalized to 0.0-1.0 range
- **Thread-Safe Design**: Queue-based data passing to UI thread
- **Performance**: <2ms processing time per frame
- **Smoothing**: 3-frame running average to reduce jitter

### Class: AudioProcessor

Located in: `Jarvis/input/audio_processor.py`

#### Initialization

```python
processor = AudioProcessor(
    sample_rate=16000,      # Sample rate in Hz
    fft_size=512,          # FFT window size
    num_bands=32           # Number of output bands
)
```

#### Core Methods

##### `process_chunk(audio_data: bytes | np.ndarray) -> np.ndarray`

Processes an audio chunk and extracts frequency bands.

**Parameters:**
- `audio_data`: Audio samples as bytes (raw int16) or numpy array

**Returns:**
- `np.ndarray`: 32-element array of normalized frequency bins (0.0-1.0)

**Processing Pipeline:**
1. Convert bytes to numpy array if needed
2. Normalize audio to [-1, 1] range
3. Apply Hann window
4. Compute FFT
5. Convert to magnitude spectrum (dB scale)
6. Extract 32 logarithmic frequency bands
7. Normalize to 0.0-1.0 range
8. Apply 3-frame smoothing
9. Store in thread-safe queue

**Example:**
```python
# From microphone stream (bytes)
audio_chunk = stream.read(1024)  # 1024 bytes of int16 audio
spectrum = processor.process_chunk(audio_chunk)

# From numpy array
audio_array = np.array([...], dtype=np.int16)
spectrum = processor.process_chunk(audio_array)
```

##### `get_spectrum() -> np.ndarray`

Get the latest spectrum data in a thread-safe manner.

**Returns:**
- `np.ndarray`: Latest 32-element spectrum array

**Example:**
```python
spectrum = processor.get_spectrum()
print(f"Spectrum shape: {spectrum.shape}")  # (32,)
print(f"Band 0 magnitude: {spectrum[0]:.3f}")  # 0.0-1.0
```

##### `get_spectrum_from_queue(timeout: float = 0.01) -> Optional[np.ndarray]`

Get spectrum from queue without blocking (non-blocking retrieval).

**Parameters:**
- `timeout`: Timeout in seconds (default: 0.01)

**Returns:**
- `np.ndarray` or `None`: Spectrum data if available, None if queue empty

**Example:**
```python
spectrum = processor.get_spectrum_from_queue(timeout=0.01)
if spectrum is not None:
    render_waveform(spectrum)
```

##### `get_processing_time() -> float`

Get the last processing time in milliseconds.

**Returns:**
- `float`: Processing time in ms

## Integration with Listener

The `Listener` class in `Jarvis/input/listener.py` automatically creates and uses an `AudioProcessor` instance.

### New Methods on Listener

#### `get_audio_spectrum() -> np.ndarray`

Get current spectrum from the listener.

**Example:**
```python
listener = Listener()
listener.start()
# ... listening in background ...
spectrum = listener.get_audio_spectrum()
```

#### `get_audio_spectrum_from_queue(timeout=0.01) -> Optional[np.ndarray]`

Get spectrum from queue (non-blocking).

**Example:**
```python
spectrum = listener.get_audio_spectrum_from_queue()
if spectrum is not None:
    # Update visualization
    update_waveform_widget(spectrum)
```

## Frequency Band Mapping

The processor maps audio frequencies to 32 logarithmic bands:

- **Frequency Range**: 20 Hz - 20 kHz (human hearing range)
- **Scale**: Logarithmic (perceptually uniform)
- **Each Band**: Covers proportional range of frequency space

**Example Band Distribution:**
- Band 0-7: Low frequencies (20Hz - ~200Hz)
- Band 8-15: Mid frequencies (~200Hz - ~2kHz)
- Band 16-23: High-mid frequencies (~2kHz - ~8kHz)
- Band 24-31: High frequencies (~8kHz - 20kHz)

## Performance Specifications

| Metric | Target | Typical |
|--------|--------|---------|
| Processing Time | <2ms | 0.3-0.8ms |
| Memory Usage | Constant | ~50KB |
| CPU Usage | <1% (per frame) | <0.5% |
| FFT Window | 512 samples | @ 16kHz = 32ms |
| Output Bands | 32 | Fixed |
| Latency | <100ms | ~50ms (including smoothing) |

## Usage Example

### Basic Usage

```python
from Jarvis.input.audio_processor import AudioProcessor
import numpy as np

# Create processor
processor = AudioProcessor(sample_rate=16000, fft_size=512, num_bands=32)

# Process audio chunk (1024 samples @ 16kHz)
audio_bytes = microphone_stream.read(1024)
spectrum = processor.process_chunk(audio_bytes)

# spectrum is now a 32-element numpy array with values 0.0-1.0
print(f"Max frequency band: {spectrum.max():.3f}")
```

### With Listener (Recommended)

```python
from Jarvis.input.listener import Listener

# Create and start listener
listener = Listener()
listener.start()

# Get spectrum for visualization
spectrum = listener.get_audio_spectrum()

# Or from queue (non-blocking)
spectrum = listener.get_audio_spectrum_from_queue(timeout=0.01)
if spectrum is not None:
    # Update waveform visualization
    update_ui(spectrum)
```

### Rendering Waveform Widget

```python
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPainter, QColor
import numpy as np

class AudioWaveWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.spectrum = np.zeros(32)
    
    def update_spectrum(self, spectrum):
        self.spectrum = spectrum
        self.update()  # Trigger repaint
    
    def paintEvent(self, event):
        painter = QPainter(self)
        width = self.width()
        height = self.height()
        
        # Draw 32 frequency bands
        band_width = width / 32
        
        for i, magnitude in enumerate(self.spectrum):
            # Scale magnitude to widget height
            bar_height = magnitude * height
            
            # Draw bar
            x = i * band_width
            y = height - bar_height
            painter.fillRect(x, y, band_width - 1, bar_height, QColor(0, 255, 100))
```

## Thread Safety

The `AudioProcessor` is designed for use in multi-threaded environments:

1. **Spectrum Queue**: Lock-free queue for UI thread consumption
2. **Direct Access**: Thread-safe `get_spectrum()` method using lock
3. **Audio Processing**: Can be called from audio thread without blocking UI

## Troubleshooting

### High Processing Time (>2ms)

1. Check system CPU load
2. Reduce FFT size or number of bands (not recommended)
3. Verify audio input buffer isn't too large

### Spectrum Not Updating

1. Check if `Listener.start()` has been called
2. Verify audio data is being received
3. Check queue isn't full: `processor.spectrum_queue.qsize()`

### Memory Issues

1. AudioProcessor uses constant memory (~50KB)
2. Check for memory leaks in UI rendering code
3. Monitor numpy array allocations

## Testing

Run the test suite:

```bash
python test_audio_processor.py
```

Tests verify:
- FFT processing correctness
- Performance (<2ms per frame)
- Spectrum normalization (0.0-1.0 range)
- Frequency band mapping
- Thread-safe queue functionality
- Listener integration

## Dependencies

- `numpy`: Numerical operations and FFT
- `threading`: Thread-safe queue operations
- `queue`: Thread-safe data passing

## Future Enhancements

- [ ] Mel-scale spectrogram option
- [ ] Real-time spectrum analyzer UI widget
- [ ] Spectrum recording/playback
- [ ] Custom frequency band ranges
- [ ] Peak detection per band
- [ ] Spectral centroid calculation
