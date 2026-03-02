"""
Audio processor for wave visualization.
Performs FFT-based frequency analysis to extract 32 frequency bands
from microphone input for the AudioWave widget.
"""

import numpy as np
import threading
import time
import queue
from typing import Optional, List


class AudioProcessor:
    """
    FFT-based frequency analyzer that processes audio chunks into normalized
    frequency bands for wave visualization.
    
    Features:
    - 512-sample FFT window processing
    - 32 logarithmic frequency bands (20Hz-20kHz)
    - Thread-safe queue for UI updates
    - Running average smoothing (3-frame)
    - <2ms processing time per chunk
    """
    
    def __init__(self, sample_rate: int = 16000, fft_size: int = 512, num_bands: int = 32):
        """
        Initialize the audio processor.
        
        Args:
            sample_rate: Sample rate in Hz (default: 16000)
            fft_size: FFT window size (default: 512)
            num_bands: Number of output frequency bands (default: 32)
        """
        self.sample_rate = sample_rate
        self.fft_size = fft_size
        self.num_bands = num_bands
        
        # Hann window for FFT
        self.window = np.hanning(fft_size)
        
        # Queue for thread-safe spectrum passing to UI
        self.spectrum_queue = queue.Queue(maxsize=2)
        
        # Current spectrum (latest 32 bands)
        self._current_spectrum = np.zeros(num_bands, dtype=np.float32)
        self._spectrum_lock = threading.Lock()
        
        # Smoothing buffer (3-frame running average)
        self._smoothing_buffer = [np.zeros(num_bands, dtype=np.float32) for _ in range(3)]
        self._smoothing_idx = 0
        
        # Frequency band mapping
        self._setup_frequency_bands()
        
        # Performance tracking
        self._last_process_time = 0
    
    def _setup_frequency_bands(self):
        """
        Setup logarithmic frequency band mapping.
        Maps 20Hz-20kHz to 32 bands using logarithmic scale.
        """
        # Frequency range: 20Hz to 20kHz
        freq_min = 20
        freq_max = 20000
        
        # Calculate FFT bin frequencies
        self.freqs = np.fft.rfftfreq(self.fft_size, d=1/self.sample_rate)
        
        # Create logarithmic band edges
        log_min = np.log10(freq_min)
        log_max = np.log10(freq_max)
        log_bands = np.logspace(log_min, log_max, self.num_bands + 1)
        
        # Map frequency bands to FFT bin indices
        self.band_indices = []
        for i in range(self.num_bands):
            # Find bins within this band's frequency range
            band_min = log_bands[i]
            band_max = log_bands[i + 1]
            
            # Get indices where frequency falls in this band
            mask = (self.freqs >= band_min) & (self.freqs < band_max)
            indices = np.where(mask)[0]
            
            if len(indices) == 0:
                # If no bins in range, use nearest bin
                idx = np.argmin(np.abs(self.freqs - band_min))
                indices = np.array([idx])
            
            self.band_indices.append(indices)
    
    def process_chunk(self, audio_data) -> np.ndarray:
        """
        Process an audio chunk and extract 32 frequency bands.
        
        Args:
            audio_data: bytes or np.ndarray of audio samples
            
        Returns:
            Normalized frequency bins (0.0-1.0 range), shape (32,)
        """
        t_start = time.time()
        
        # Convert bytes to numpy array if needed
        if isinstance(audio_data, bytes):
            audio_data = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
        elif isinstance(audio_data, np.ndarray):
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
        else:
            raise TypeError(f"Unsupported audio_data type: {type(audio_data)}")
        
        # Ensure we have enough samples for FFT
        if len(audio_data) < self.fft_size:
            # Pad with zeros if needed
            audio_data = np.pad(audio_data, (0, self.fft_size - len(audio_data)), mode='constant')
        else:
            # Use only first fft_size samples
            audio_data = audio_data[:self.fft_size]
        
        # Normalize audio to [-1, 1]
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val
        
        # Apply Hann window
        windowed = audio_data * self.window
        
        # Compute FFT
        fft_result = np.fft.rfft(windowed)
        
        # Convert to magnitude spectrum (dB scale)
        magnitude = np.abs(fft_result)
        magnitude_db = 20 * np.log10(magnitude + 1e-10)  # Add small value to avoid log(0)
        
        # Extract frequency bands
        bands = np.zeros(self.num_bands, dtype=np.float32)
        for i, indices in enumerate(self.band_indices):
            if len(indices) > 0:
                # Average magnitude in this band
                bands[i] = np.mean(magnitude_db[indices])
        
        # Normalize to 0.0-1.0 range
        # dB range typically -80 to 0 dB, normalize accordingly
        bands = np.clip((bands + 80) / 80, 0.0, 1.0)
        
        # Apply smoothing (3-frame running average)
        self._smoothing_buffer[self._smoothing_idx] = bands
        self._smoothing_idx = (self._smoothing_idx + 1) % 3
        smoothed = np.mean(self._smoothing_buffer, axis=0)
        
        # Store in thread-safe manner
        with self._spectrum_lock:
            self._current_spectrum = smoothed.copy()
        
        # Put in queue for UI (non-blocking, drop old data if queue full)
        try:
            self.spectrum_queue.put_nowait(smoothed.copy())
        except queue.Full:
            # Queue is full, drop oldest data
            try:
                self.spectrum_queue.get_nowait()
                self.spectrum_queue.put_nowait(smoothed.copy())
            except queue.Empty:
                pass
        
        # Performance tracking
        self._last_process_time = (time.time() - t_start) * 1000  # Convert to ms
        
        return smoothed
    
    def get_spectrum(self) -> np.ndarray:
        """
        Get the latest spectrum data (thread-safe).
        
        Returns:
            Latest 32 normalized frequency bins (0.0-1.0)
        """
        with self._spectrum_lock:
            return self._current_spectrum.copy()
    
    def get_spectrum_from_queue(self, timeout: float = 0.01) -> Optional[np.ndarray]:
        """
        Get spectrum from queue (non-blocking).
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Spectrum array or None if queue is empty
        """
        try:
            return self.spectrum_queue.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_processing_time(self) -> float:
        """Get last processing time in milliseconds."""
        return self._last_process_time
