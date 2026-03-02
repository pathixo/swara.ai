
import pyaudio
import wave

class AudioCapture:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []

    def start_recording(self):
        self.frames = []
        self.stream = self.p.open(format=pyaudio.paInt16,
                                channels=1,
                                rate=16000,
                                input=True,
                                frames_per_buffer=1024)
        print("Recording started...")

    def stop_recording(self, filename="output.wav"):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        print("Recording stopped.")

        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(16000)
        wf.writeframes(b''.join(self.frames))
        wf.close()

    def read_chunk(self):
         if self.stream and self.stream.is_active():
             return self.stream.read(1024, exception_on_overflow=False)
         return None

    def close(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
