import os
import struct
import tempfile
import subprocess
import time

try:
    import pvporcupine
    import pyaudio
    import speech_recognition as sr
    from faster_whisper import WhisperModel
except ImportError:
    pass # Handled in requirements

class VoiceSystem:
    def __init__(self, config):
        self.config = config
        self.system_cfg = config.get("system", {})
        self.voice_cfg = config.get("voice", {})
        self.input_device_index = self.voice_cfg.get("input_device_index")
        
        # Initialize STT
        print(f"[JARVIS] Initializing faster-whisper on {self.voice_cfg.get('stt_device', 'cpu')}...")
        self.stt_model = WhisperModel(
            self.voice_cfg.get("stt_model", "base"),
            device=self.voice_cfg.get("stt_device", "cpu"),
            compute_type=self.voice_cfg.get("stt_compute_type", "int8")
        )
        print("[JARVIS] Voice system ready.")
        self.recognizer = sr.Recognizer()
        print("[JARVIS] Voice system initialized.")

    def apply_runtime_settings(self, system_cfg=None, voice_cfg=None):
        """Applies updated runtime settings without reloading models."""
        if system_cfg:
            self.system_cfg.update(system_cfg)
        if voice_cfg:
            self.voice_cfg.update(voice_cfg)
            self.input_device_index = self.voice_cfg.get("input_device_index")

    def list_input_devices(self):
        """Returns available input audio devices with indices."""
        pa = pyaudio.PyAudio()
        devices = []
        try:
            for index in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(index)
                if int(info.get("maxInputChannels", 0)) > 0:
                    devices.append(
                        {
                            "index": index,
                            "name": info.get("name", f"Input Device {index}"),
                            "defaultSampleRate": int(info.get("defaultSampleRate", 0)),
                        }
                    )
        finally:
            pa.terminate()
        return devices

    def listen_for_wake_word(self, on_level=None):
        """Blocks until wake trigger is detected. Optionally calls on_level with audio energy."""
        keyword = self.system_cfg.get("wake_word", "jarvis")
        access_key = self.system_cfg.get("picovoice_key")
        keyword_wake_enabled = bool(self.voice_cfg.get("enable_keyword_wake", True))
        use_clap = bool(self.voice_cfg.get("enable_clap_wake", True))
        clap_threshold = int(self.voice_cfg.get("clap_threshold", 12000))
        clap_count_required = int(self.voice_cfg.get("clap_count_required", 2))
        clap_window_s = float(self.voice_cfg.get("clap_window_s", 1.2))
        clap_cooldown_s = float(self.voice_cfg.get("clap_cooldown_s", 0.25))

        can_use_keyword = bool(
            keyword_wake_enabled and access_key and access_key != "YOUR_PICOVOICE_ACCESS_KEY"
        )
        porcupine = None
        if can_use_keyword:
            porcupine = pvporcupine.create(
                access_key=access_key,
                keywords=[keyword]
            )
        elif not use_clap:
            print("[WARN] No wake trigger enabled. Waiting for keyboard enter instead.")
            input("Press Enter to trigger JARVIS...")
            return True

        sample_rate = porcupine.sample_rate if porcupine else 16000
        frame_length = porcupine.frame_length if porcupine else 512
        pa = pyaudio.PyAudio()
        audio_stream = pa.open(
            rate=sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            input_device_index=self.input_device_index,
            frames_per_buffer=frame_length
        )

        mode = []
        if can_use_keyword:
            mode.append(f"wake word '{keyword}'")
        if use_clap:
            mode.append(f"{clap_count_required}-clap pattern")
        print(f"[JARVIS] Listening for {' or '.join(mode)}...")

        clap_hits = []
        last_clap_ts = 0.0
        try:
            while True:
                pcm = audio_stream.read(frame_length, exception_on_overflow=False)
                pcm_unpacked = struct.unpack_from("h" * frame_length, pcm)

                if porcupine:
                    keyword_index = porcupine.process(pcm_unpacked)
                    if keyword_index >= 0:
                        print("[JARVIS] Wake word detected!")
                        return True

                if use_clap or on_level:
                    peak = max(abs(sample) for sample in pcm_unpacked)
                    # Broadcast level to UI
                    if on_level:
                        on_level(peak)
                    
                    now = time.time()
                    if use_clap and peak >= clap_threshold and (now - last_clap_ts) >= clap_cooldown_s:
                        clap_hits.append(now)
                        last_clap_ts = now
                        clap_hits = [t for t in clap_hits if now - t <= clap_window_s]
                        if len(clap_hits) >= clap_count_required:
                            print("[JARVIS] Clap wake detected!")
                            return True
        finally:
            audio_stream.close()
            pa.terminate()
            if porcupine:
                porcupine.delete()

    def record_audio(self):
        """Records from microphone until silence and saves to a temp WAV."""
        print("[JARVIS] Listening to command...")
        with sr.Microphone(device_index=self.input_device_index) as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Listen until silence
            try:
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=15)
                
                # Save to temp file
                temp_wav = tempfile.mktemp(suffix=".wav")
                with open(temp_wav, "wb") as f:
                    f.write(audio.get_wav_data())
                return temp_wav
            except sr.WaitTimeoutError:
                return None

    def transcribe(self, audio_path):
        """Transcribes audio using faster-whisper."""
        if not audio_path or not os.path.exists(audio_path):
            return ""
            
        print("[JARVIS] Transcribing...")
        segments, info = self.stt_model.transcribe(audio_path, beam_size=5)
        text = " ".join([segment.text for segment in segments])
        os.remove(audio_path) # Cleanup
        print(f"[USER] {text.strip()}")
        return text.strip()

    def speak(self, text):
        """Text-to-speech using Piper."""
        if not text:
            return
            
        print(f"[JARVIS] {text}")
        model_path = self.voice_cfg.get("tts_model_path", "en_US-lessac-high.onnx")
        
        if not os.path.exists(model_path):
            print("[WARN] Piper model not found. Using print instead.")
            return

        # Run Piper TTS executable
        # Assumes piper is in PATH or current dir
        command = [
            "piper", 
            "--model", model_path,
            "--output_raw"
        ]
        
        try:
            piper_proc = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            # Pipe the raw audio output directly to aplay/sox/ffplay 
            # On Windows, we can use simpleaudio or a similar player, but Piper has --output-file
            # For simplicity let's just make it output a temp file and play it
            
            temp_wav = tempfile.mktemp(suffix=".wav")
            command = [
                "piper",
                "--model", model_path,
                "--output_file", temp_wav
            ]
            subprocess.run(command, input=text.encode('utf-8'), stderr=subprocess.DEVNULL)
            
            import wave
            import pyaudio
            
            wf = wave.open(temp_wav, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            while data:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            p.terminate()
            os.remove(temp_wav)
            
        except Exception as e:
            print(f"[TTS ERROR] {e}")
