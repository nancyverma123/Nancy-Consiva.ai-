from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ar": "Arabic",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "pt": "Portuguese",
    "zh-cn": "Chinese",
    "ja": "Japanese",
    "bn": "Bengali",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "gu": "Gujarati",
    "ur": "Urdu",
}


# langdetect is unreliable on very short inputs ("hi", "pricing?"), so only trust it
# for longer text, or when the text is in a non-Latin script.
_MIN_LATIN_CHARS_FOR_DETECTION = 20


def detect_language(text: str, fallback: str = "en") -> str:
    stripped = text.strip()
    has_non_latin = any(ord(ch) > 0x024F and ch.isalpha() for ch in stripped)
    if not has_non_latin and len(stripped) < _MIN_LATIN_CHARS_FOR_DETECTION:
        return fallback
    try:
        code = detect(stripped)
    except LangDetectException:
        return fallback
    return code if code in LANGUAGE_NAMES else fallback


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)
