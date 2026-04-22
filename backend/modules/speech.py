import subprocess
import speech_recognition as sr
from config.settings import TTS_RATE


def speak(text: str) -> None:
    """Speak text using Android TTS via Termux."""
    try:
        subprocess.run(
            ["termux-tts-speak", "-r", str(TTS_RATE), text],
            timeout=60,
        )
    except FileNotFoundError:
        # Fallback: pyttsx3 if termux-tts-speak not available
        try:
            import pyttsx3
            engine = pyttsx3.init()
            engine.setProperty("rate", TTS_RATE)
            engine.say(text)
            engine.runAndWait()
        except Exception:
            print(f"[TTS] {text}")
    except Exception:
        print(f"[TTS] {text}")


def listen(timeout: int = 8, phrase_limit: int = 10) -> str | None:
    """Listen for speech and return recognized text, or None on failure."""
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True

    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        print("[Listening...]")
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_limit)
        except sr.WaitTimeoutError:
            return None

    try:
        text = recognizer.recognize_google(audio).lower()
        print(f"[Heard] {text}")
        return text
    except sr.UnknownValueError:
        return None
    except sr.RequestError:
        # Fallback to Vosk if Google STT fails
        try:
            text = recognizer.recognize_vosk(audio).lower()
            print(f"[Heard-Vosk] {text}")
            return text
        except Exception:
            return None
