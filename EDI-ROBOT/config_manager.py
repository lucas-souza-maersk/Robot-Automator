import json
import os
import logging

# Nomes dos arquivos
SETTINGS_FILE = 'system_config.json'
PROFILES_FILE = 'profiles.json'

# --- PARTE 1: CONFIGURAÇÕES DE SISTEMA (AUTH N4 / BANCO) ---
def load_system_settings():
    # Configuração padrão se o arquivo não existir
    default = {
        "auth_method": "N4", 
        "n4_url": "http://10.55.26.16/apex/services/argoservice",
        "n4_scope": {"op": "APMT", "cpx": "BRPEC", "fac": "PEC", "yard": "PEC"},
        "db_config": {"host": "LOCALHOST", "name": "ROBOT_DB", "user": "sa", "pass": "senha"}
    }
    
    if not os.path.exists(SETTINGS_FILE):
        save_system_settings(default)
        return default

    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar system config: {e}")
        return default

def save_system_settings(data):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar system config: {e}")
        return False

# --- PARTE 2: CONFIGURAÇÕES DE PERFIS (O QUE ESTAVA FALTANDO) ---
def load_profiles():
    if not os.path.exists(PROFILES_FILE):
        return {}
    try:
        with open(PROFILES_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar perfis: {e}")
        return {}

def save_profiles(profiles):
    try:
        with open(PROFILES_FILE, 'w') as f:
            json.dump(profiles, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Erro ao salvar perfis: {e}")
        return False