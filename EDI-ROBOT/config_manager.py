import json
import os
import logging

PROFILES_FILE = 'profiles.json'

def load_profiles():
    if not os.path.exists(PROFILES_FILE):
        return {}

    try:
        with open(PROFILES_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        logging.error(f"Erro ao ler o ficheiro de perfis '{PROFILES_FILE}'. Um novo ficheiro será criado.")
        return {}

def save_profiles(profiles):
    try:
        with open(PROFILES_FILE, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, indent=4)
    except Exception as e:
        logging.error(f"Não foi possível salvar os perfis em '{PROFILES_FILE}': {e}")