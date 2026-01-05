from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
import bcrypt

# Troque por uma chave segura em produção
SECRET_KEY = "troque_isso_por_uma_chave_aleatoria_e_longa_em_producao"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

def verify_password(plain_password, hashed_password):
    """Verifica se a senha bate com o hash (usando bcrypt direto)."""
    # bcrypt requer bytes, então codificamos as strings
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password):
    """Gera um hash seguro da senha."""
    # Gera o salt e o hash, depois decodifica para string para salvar no banco SQLite
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Gera o token JWT para a sessão."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt