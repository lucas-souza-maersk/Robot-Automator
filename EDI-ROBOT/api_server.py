import os
import json
import sqlite3
import string
import platform
import fnmatch
import traceback
import socket
import paramiko
import warnings
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt

# Silencia avisos de criptografia (TripleDES) para limpar o log
warnings.filterwarnings("ignore", category=DeprecationWarning) 

import config_manager
import data_manager
import user_db
import auth_utils

# Inicializa o banco de usuários
user_db.init_user_db()

app = FastAPI(title="EDI Robot Dashboard API", version="3.1.0 (Fix UserCreate)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- MODELS (Definições de Dados) ---

# 1. Modelo para Login (Token)
class Token(BaseModel):
    access_token: str
    token_type: str

# 2. Modelo para Dados do Usuário (Leitura)
class UserData(BaseModel):
    username: str
    role: str
    full_name: Optional[str] = None

# 3. Modelo para CRIAR Usuário (AQUI ESTAVA O ERRO, PRECISA ESTAR AQUI)
class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    full_name: str = ""

# 4. Outros Modelos
class ForceResendRequest(BaseModel):
    profile_name: str
    item_ids: List[int]

class BrowseRequest(BaseModel):
    path: str

class SftpBrowseRequest(BaseModel):
    host: str
    port: int = 22
    username: str
    password: str
    path: str = "/"

class PreviewRequest(BaseModel):
    path: str
    pattern: str

class ProfileConfigModel(BaseModel):
    profiles: Dict[str, Any]

# --- AUTH HELPERS ---

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, auth_utils.SECRET_KEY, algorithms=[auth_utils.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = user_db.get_user(username)
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action"
        )
    return current_user

# --- ROTAS DA API ---

# 1. Autenticação e Usuários

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_db.get_user(form_data.username)
    if not user or not auth_utils.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_410_GONE, # Código genérico para falha de auth
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_utils.create_access_token(
        data={"sub": user["username"], "role": user["role"]}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserData)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {
        "username": current_user["username"], 
        "role": current_user["role"], 
        "full_name": current_user["full_name"]
    }

@app.get("/users", response_model=List[UserData])
def list_users(current_user: dict = Depends(get_current_admin_user)):
    """Lista todos os usuários (Somente Admin)."""
    return user_db.get_all_users()

@app.post("/users")
def register_user(user: UserCreate, current_user: dict = Depends(get_current_admin_user)):
    """Cria um novo usuário (Somente Admin)."""
    success = user_db.create_user(user.username, user.password, user.role, user.full_name)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User created successfully"}

@app.delete("/users/{username}")
def remove_user(username: str, current_user: dict = Depends(get_current_admin_user)):
    """Remove um usuário (Somente Admin)."""
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete root admin")
    
    success = user_db.delete_user(username)
    if not success:
         raise HTTPException(status_code=404, detail="User not found")
         
    return {"message": "User deleted"}

# 2. Perfis e Configuração

@app.get("/profiles")
def get_profiles(current_user: dict = Depends(get_current_user)):
    return config_manager.load_profiles()

@app.post("/profiles")
def save_profiles(config: ProfileConfigModel, current_user: dict = Depends(get_current_admin_user)):
    try:
        config_manager.save_profiles(config.profiles)
        return {"status": "success", "message": "Profiles saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. Monitoramento e Filas

@app.get("/queue/{profile_name}")
def get_profile_queue(profile_name: str, limit: int = 100, search: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    profiles = config_manager.load_profiles()
    if profile_name not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_path = profiles[profile_name].get("settings", {}).get("db_path")
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database not found for this profile")

    try:
        # Busca TODOS os itens para filtrar no Python (para suportar busca avançada)
        items = data_manager.get_all_queue_items(db_path, container_filter=None)
        
        formatted_items = []
        for item in items:
            # item: (id, status, retries, file_path, file_hash, added_at, processed_at, original_path, units)
            f_name = os.path.basename(item[3] or item[7] or "N/A")
            units = item[8] or ""
            
            # Lógica de Filtro Avançado (Busca por nome ou unidade, separados por vírgula)
            if search:
                search_terms = [t.strip().lower() for t in search.split(',')]
                match = False
                for term in search_terms:
                    if not term: continue
                    if (term in f_name.lower()) or (term in units.lower()):
                        match = True
                        break
                if not match:
                    continue # Pula se não bateu com nenhum termo
            
            formatted_items.append({
                "id": item[0],
                "status": item[1],
                "retries": item[2],
                "filename": f_name,
                "hash": item[4],
                "added_at": item[5],
                "processed_at": item[6],
                "units": item[8]
            })
            
            # Paginação manual após filtro
            if len(formatted_items) >= limit: 
                break
            
        return formatted_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/stats/{profile_name}")
def get_profile_stats(profile_name: str, current_user: dict = Depends(get_current_user)):
    profiles = config_manager.load_profiles()
    if profile_name not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_path = profiles[profile_name].get("settings", {}).get("db_path")
    if not db_path or not os.path.exists(db_path):
        return {"pending": 0, "sent": 0, "failed": 0, "duplicate": 0}

    stats = data_manager.get_queue_stats(db_path)
    return stats

@app.post("/resend")
def force_resend(request: ForceResendRequest, current_user: dict = Depends(get_current_admin_user)):
    profiles = config_manager.load_profiles()
    if request.profile_name not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_path = profiles[request.profile_name].get("settings", {}).get("db_path")
    if not db_path:
        raise HTTPException(status_code=400, detail="Profile has no database path")

    try:
        data_manager.force_resend_items(db_path, request.item_ids)
        return {"message": f"Successfully queued {len(request.item_ids)} items for resend."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update database: {str(e)}")

# 4. Sistema de Arquivos e SFTP

@app.get("/system/drives")
def get_server_drives(current_user: dict = Depends(get_current_admin_user)):
    drives = []
    if platform.system() == "Windows":
        available_drives = ['%s:/' % d for d in string.ascii_uppercase if os.path.exists('%s:/' % d)]
        drives = available_drives
    else:
        drives = ["/"]
    return drives

@app.post("/system/browse")
def browse_server_path(request: BrowseRequest, current_user: dict = Depends(get_current_admin_user)):
    raw_path = request.path.strip()
    target_path = os.path.normpath(raw_path)

    if platform.system() == "Windows" and len(target_path) == 2 and target_path[1] == ":":
        target_path += "/"

    print(f"[BROWSER DEBUG] Local Access: '{target_path}'")

    if not os.path.exists(target_path):
        raise HTTPException(status_code=404, detail=f"Path not found: {target_path}")
    
    if not os.path.isdir(target_path):
        raise HTTPException(status_code=400, detail="Not a directory")
    
    try:
        items = []
        with os.scandir(target_path) as entries:
            for entry in entries:
                if entry.is_dir():
                    items.append({"name": entry.name, "type": "folder", "path": entry.path})
        return sorted(items, key=lambda x: x["name"])
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied. Access blocked by OS.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/system/preview")
def preview_files(request: PreviewRequest, current_user: dict = Depends(get_current_admin_user)):
    target_path = os.path.normpath(request.path.strip())
    patterns = [p.strip() for p in request.pattern.split(',')]
    
    if not os.path.isdir(target_path):
        raise HTTPException(status_code=404, detail=f"Path not found: {target_path}")

    try:
        matched_files = []
        count = 0
        limit = 50 
        
        with os.scandir(target_path) as entries:
            for entry in entries:
                if entry.is_file():
                    if any(fnmatch.fnmatch(entry.name, p) for p in patterns):
                        matched_files.append(entry.name)
                        count += 1
                        if count >= limit:
                            break
        
        return {
            "files": matched_files, 
            "total_preview": count, 
            "message": "Showing first 50 matches" if count >= limit else "All matches shown"
        }
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied accessing this folder.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sftp/browse")
def browse_sftp(request: SftpBrowseRequest, current_user: dict = Depends(get_current_admin_user)):
    """Conecta ao SFTP usando Paramiko (Robust SSHClient)."""
    print(f"[SFTP DEBUG] Connecting to {request.username}@{request.host}:{request.port} path={request.path}")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    sftp = None
    try:
        ssh.connect(
            hostname=request.host, 
            port=request.port, 
            username=request.username, 
            password=request.password,
            timeout=10, 
            banner_timeout=10
        )
        
        sftp = ssh.open_sftp()
        target_path = request.path if request.path else "."
        
        try:
            sftp.chdir(target_path)
        except IOError:
            print(f"[SFTP DEBUG] Path {target_path} invalid, falling back to root.")
            target_path = "."
            sftp.chdir(".")

        items = []
        for attr in sftp.listdir_attr(target_path):
            is_dir = str(attr).startswith('d') 
            if is_dir:
                filename = attr.filename
                if filename in ['.', '..']: continue
                
                if target_path == "." or target_path == "/":
                    full_path = "/" + filename
                else:
                    full_path = target_path.rstrip('/') + '/' + filename
                    
                items.append({"name": filename, "type": "folder", "path": full_path})
        
        return sorted(items, key=lambda x: x["name"])

    except socket.timeout:
        raise HTTPException(status_code=504, detail="Connection Timed Out. Check Firewall/VPN.")
    except paramiko.AuthenticationException:
        raise HTTPException(status_code=401, detail="Authentication Failed. Check User/Pass.")
    except paramiko.SSHException as e:
        raise HTTPException(status_code=502, detail=f"SSH Handshake Error: {str(e)}")
    except Exception as e:
        print("--- SFTP ERROR TRACEBACK ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"SFTP Error: {str(e)}")
    
    finally:
        if sftp: sftp.close()
        ssh.close()

if __name__ == "__main__":
    import uvicorn
    print("Starting API Server v3.1.0...")
    uvicorn.run(app, host="0.0.0.0", port=8000)