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
import edi_parser
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from jose import JWTError, jwt

# Silencia avisos de criptografia
warnings.filterwarnings("ignore", category=DeprecationWarning) 

import config_manager
import data_manager
import user_db
import auth_utils

user_db.init_user_db()

app = FastAPI(title="EDI Robot Dashboard API", version="3.4.0 (Fix RFF Error)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- MODELS ---
class Token(BaseModel):
    access_token: str
    token_type: str

class UserData(BaseModel):
    username: str
    role: str
    full_name: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    full_name: str = ""

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

# --- ROTAS ---

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_db.get_user(form_data.username)
    if not user or not auth_utils.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Incorrect username or password", headers={"WWW-Authenticate": "Bearer"})
    access_token = auth_utils.create_access_token(data={"sub": user["username"], "role": user["role"]})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=UserData)
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return {"username": current_user["username"], "role": current_user["role"], "full_name": current_user["full_name"]}

@app.get("/users", response_model=List[UserData])
def list_users(current_user: dict = Depends(get_current_admin_user)):
    return user_db.get_all_users()

@app.post("/users")
def register_user(user: UserCreate, current_user: dict = Depends(get_current_admin_user)):
    success = user_db.create_user(user.username, user.password, user.role, user.full_name)
    if not success:
        raise HTTPException(status_code=400, detail="Username already exists")
    return {"message": "User created successfully"}

@app.delete("/users/{username}")
def remove_user(username: str, current_user: dict = Depends(get_current_admin_user)):
    if username == "admin": raise HTTPException(status_code=400, detail="Cannot delete root admin")
    success = user_db.delete_user(username)
    if not success: raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}

@app.get("/profiles")
def get_profiles(current_user: dict = Depends(get_current_user)):
    return config_manager.load_profiles()

@app.post("/profiles")
def save_profiles(config: ProfileConfigModel, current_user: dict = Depends(get_current_admin_user)):
    config_manager.save_profiles(config.profiles)
    return {"status": "success"}

@app.get("/queue/{profile_name}")
def get_profile_queue(profile_name: str, limit: int = 100, search: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    profiles = config_manager.load_profiles()
    if profile_name not in profiles: raise HTTPException(status_code=404, detail="Profile not found")
    db_path = profiles[profile_name].get("settings", {}).get("db_path")
    if not db_path or not os.path.exists(db_path): raise HTTPException(status_code=404, detail="Database not found")

    try:
        items = data_manager.get_all_queue_items(db_path, container_filter=None)
        formatted_items = []
        for item in items:
            f_name = os.path.basename(item[3] or item[7] or "N/A")
            units = item[8] or ""
            if search:
                search_terms = [t.strip().lower() for t in search.split(',')]
                match = False
                for term in search_terms:
                    if not term: continue
                    if (term in f_name.lower()) or (term in units.lower()):
                        match = True
                        break
                if not match: continue
            
            formatted_items.append({
                "id": item[0], "status": item[1], "retries": item[2], "filename": f_name,
                "hash": item[4], "added_at": item[5], "processed_at": item[6], "units": item[8]
            })
            if len(formatted_items) >= limit: break
        return formatted_items
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/stats/{profile_name}")
def get_profile_stats(profile_name: str, current_user: dict = Depends(get_current_user)):
    profiles = config_manager.load_profiles()
    if profile_name not in profiles: raise HTTPException(status_code=404)
    db_path = profiles[profile_name].get("settings", {}).get("db_path")
    if not db_path or not os.path.exists(db_path): return {"pending": 0, "sent": 0, "failed": 0, "duplicate": 0}
    return data_manager.get_queue_stats(db_path)

@app.post("/resend")
def force_resend(request: ForceResendRequest, current_user: dict = Depends(get_current_admin_user)):
    profiles = config_manager.load_profiles()
    db_path = profiles[request.profile_name].get("settings", {}).get("db_path")
    data_manager.force_resend_items(db_path, request.item_ids)
    return {"message": "Queued"}

@app.get("/system/drives")
def get_server_drives(current_user: dict = Depends(get_current_admin_user)):
    if platform.system() == "Windows": return ['%s:/' % d for d in string.ascii_uppercase if os.path.exists('%s:/' % d)]
    return ["/"]

@app.post("/system/browse")
def browse_server_path(request: BrowseRequest, current_user: dict = Depends(get_current_admin_user)):
    path = request.path.strip()
    path = os.path.normpath(path)
    if platform.system() == "Windows" and len(path) == 2 and path[1] == ":": path += "/"
    if not os.path.exists(path): raise HTTPException(404, "Path not found")
    items = []
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                if entry.is_dir(): items.append({"name": entry.name, "type": "folder", "path": entry.path})
        return sorted(items, key=lambda x: x["name"])
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/system/preview")
def preview_files(request: PreviewRequest, current_user: dict = Depends(get_current_admin_user)):
    try:
        matched = []
        with os.scandir(request.path.strip()) as entries:
            for entry in entries:
                if entry.is_file() and any(fnmatch.fnmatch(entry.name, p) for p in request.pattern.split(',')):
                    matched.append(entry.name)
                    if len(matched) >= 50: break
        return {"files": matched}
    except Exception as e: raise HTTPException(500, str(e))

@app.post("/sftp/browse")
def browse_sftp(request: SftpBrowseRequest, current_user: dict = Depends(get_current_admin_user)):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(request.host, port=request.port, username=request.username, password=request.password, timeout=10)
        sftp = ssh.open_sftp()
        items = []
        for attr in sftp.listdir_attr(request.path or "."):
            if str(attr).startswith('d'): items.append({"name": attr.filename, "type": "folder", "path": (request.path or "").rstrip('/') + '/' + attr.filename})
        return sorted(items, key=lambda x: x["name"])
    except Exception as e: raise HTTPException(500, str(e))
    finally: ssh.close()

# --- ROTA DE DETALHES INTELIGENTE ---
@app.get("/queue/{profile_name}/file/{file_id}")
def get_file_details_api(profile_name: str, file_id: int, current_user: dict = Depends(get_current_user)):
    print(f"\n[API DEBUG] Fetching details for File ID: {file_id} in Profile: {profile_name}")
    
    profiles = config_manager.load_profiles()
    if profile_name not in profiles:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    profile_data = profiles[profile_name]
    db_path = profile_data.get("settings", {}).get("db_path")
    
    # 1. Pega info do banco
    file_info = data_manager.get_file_details(db_path, file_id)
    if not file_info:
        print(f"[API DEBUG] ERROR: File ID {file_id} not found in DB at {db_path}")
        raise HTTPException(status_code=404, detail="File not found in DB")

    # 2. Estratégia de Busca do Arquivo Físico
    filename = os.path.basename(file_info.get("file_path") or "unknown.txt")
    possible_paths = []

    if file_info.get("original_path"): possible_paths.append(file_info["original_path"])
    if file_info.get("file_path"): possible_paths.append(file_info["file_path"])

    dest_config = profile_data.get("destination", {})
    if dest_config.get("type") == "local" and dest_config.get("path"):
        possible_paths.append(os.path.join(dest_config["path"], filename))

    backup_config = profile_data.get("settings", {}).get("backup", {})
    if backup_config.get("enabled") and backup_config.get("path"):
        possible_paths.append(os.path.join(backup_config["path"], filename))

    final_path = None
    print("[API DEBUG] Searching for file content in known locations:")
    for path in possible_paths:
        exists = os.path.exists(path)
        print(f"  - Check: {path} -> {'FOUND' if exists else 'MISSING'}")
        if exists:
            final_path = path
            break
    
    edi_data = [] # Retorna sempre LISTA
    content = ""
    
    if final_path:
        print(f"[API DEBUG] Reading content from: {final_path}")
        try:
            with open(final_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                print(f"[API DEBUG] Content read. Size: {len(content)} bytes")
                
                print("[API DEBUG] Parsing EDI content (Multi-Transaction)...")
                parser = edi_parser.EdiParser(content)
                # Pega a LISTA de transações
                edi_data = parser.transactions
                print(f"[API DEBUG] Parse result: {len(edi_data)} transactions found.")
                
        except Exception as e:
            print(f"[API DEBUG] ERROR reading/parsing file: {e}")
            traceback.print_exc()
            edi_data = [{"error": f"Could not parse file: {str(e)}", "type": "ERROR"}]
    else:
        print("[API DEBUG] ERROR: File content not found in any path.")
        edi_data = [{"error": "File content not accessible. It may have been moved or deleted.", "type": "ERROR"}]

    return {
        "db_info": file_info,
        "edi_info": edi_data, 
        "raw_content": content or f"File not found. Checked paths:\n" + "\n".join(possible_paths)
    }

if __name__ == "__main__":
    import uvicorn
    print("Starting API Server v3.4.0 (Robust)...")
    uvicorn.run(app, host="0.0.0.0", port=8000)