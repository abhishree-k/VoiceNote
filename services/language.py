def determine_language(detected_lang: str) -> str:
    """
    Validates the language detected from Sarvam's STT response.
    Supports en-IN, hi-IN, kn-IN, mr-IN as required.
    Falls back to en-IN if the language is missing, undefined, or unsupported.
    """
    supported_langs = ["en-IN", "hi-IN", "kn-IN", "mr-IN"]
    
    if not detected_lang:
        return "en-IN"
        
    # Sometimes Sarvam might return just 'hi', 'en', etc. Ensure it has the '-IN' suffix
    lang_code = detected_lang.strip()
    if len(lang_code) == 2:
        lang_code = f"{lang_code}-IN"
        
    if lang_code in supported_langs:
        return lang_code
        
    return "en-IN"
