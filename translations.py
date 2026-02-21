import locale
import os
import json
import warnings
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
LOCALES_DIR = SCRIPT_DIR / "locales"

def load_translations():
    try:
        lang_code = locale.getlocale()[0]
        if lang_code is None:
            lang = os.environ.get('LANG', '')
            if lang:
                lang_code = lang
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", DeprecationWarning)
                    lang_code = locale.getdefaultlocale()[0]
        system_lang = lang_code[:2] if lang_code else "en"
    except:
        system_lang = "en"

    translations = {}
    lang_file = LOCALES_DIR / f"{system_lang}.json"
    if lang_file.exists():
        with open(lang_file, 'r', encoding='utf-8') as f:
            translations = json.load(f)
    else:
        fallback = LOCALES_DIR / "en.json"
        if fallback.exists():
            with open(fallback, 'r', encoding='utf-8') as f:
                translations = json.load(f)
    return translations

translations = load_translations()

def tr(key, *args):
    text = translations.get(key, key)
    if args:
        return text.format(*args)
    return text