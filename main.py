import os
import uuid
import shutil
import asyncio
import tempfile
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# 创建应用
app = FastAPI(
    title="olmOCR API",
    description="用于PDF和图像文档OCR处理的API接口",
    version="1.0.0",
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 安全配置
SECRET_KEY = "YOUR_SECRET_KEY_HERE"  # 在生产环境中请使用安全的随机密钥
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# 用户数据库 - 在生产环境中应该使用真实的数据库
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 密码: secret
    }
}

# 工作目录
WORK_DIR = Path("./olmocr_workdir")
WORK_DIR.mkdir(exist_ok=True)

# 任务状态存储
TASKS = {}

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Bearer令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 模型定义
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class User(BaseModel):
    username: str

class UserInDB(User):
    hashed_password: str

class OCRRequest(BaseModel):
    task_id: str

class OCRStatus(BaseModel):
    task_id: str
    status: str
    progress: float = 0.0
    result_path: Optional[str] = None
    error: Optional[str] = None
    created_at: str

class OCRResult(BaseModel):
    task_id: str
    text: str
    metadata: Dict[str, Any] = {}

# 安全函数
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user

# olmocr处理函数
async def process_document(task_id: str, file_path: str):
    try:
        # 创建工作目录
        workspace_path = WORK_DIR / task_id
        workspace_path.mkdir(exist_ok=True)
        
        # 更新任务状态
        TASKS[task_id]["status"] = "processing"
        
        # 构建命令
        cmd = [
            "python", "-m", "olmocr.pipeline",
            str(workspace_path),
            "--markdown",
            "--pdfs", file_path
        ]
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            TASKS[task_id]["status"] = "failed"
            TASKS[task_id]["error"] = stderr.decode()
            return
        
        # 查找生成的markdown文件
        markdown_dir = workspace_path / "markdown"
        if markdown_dir.exists():
            markdown_files = list(markdown_dir.glob("**/*.md"))
            if markdown_files:
                md_file = markdown_files[0]
                with open(md_file, "r", encoding="utf-8") as f:
                    text_content = f.read()
                
                TASKS[task_id]["status"] = "completed"
                TASKS[task_id]["result"] = text_content
                TASKS[task_id]["result_path"] = str(md_file)
                return
        
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = "处理完成但未找到结果文件"
    except Exception as e:
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)

# API路由
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/ocr/upload", response_model=OCRStatus)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # 验证文件类型
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".png") or filename.endswith(".jpg") or filename.endswith(".jpeg")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持PDF, PNG, JPG文件格式"
        )
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 保存上传的文件
    file_path = WORK_DIR / f"{task_id}_{file.filename}"
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 创建任务记录
    TASKS[task_id] = {
        "status": "queued",
        "file_path": str(file_path),
        "created_at": datetime.now().isoformat(),
        "result": None,
        "result_path": None,
        "error": None
    }
    
    # 后台处理文档
    background_tasks.add_task(process_document, task_id, str(file_path))
    
    return OCRStatus(
        task_id=task_id,
        status="queued",
        created_at=TASKS[task_id]["created_at"]
    )

@app.get("/ocr/status/{task_id}", response_model=OCRStatus)
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    if task_id not in TASKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    task = TASKS[task_id]
    return OCRStatus(
        task_id=task_id,
        status=task["status"],
        progress=1.0 if task["status"] == "completed" else (0.5 if task["status"] == "processing" else 0.0),
        result_path=task.get("result_path"),
        error=task.get("error"),
        created_at=task["created_at"]
    )

@app.get("/ocr/result/{task_id}", response_model=OCRResult)
async def get_task_result(task_id: str, current_user: User = Depends(get_current_user)):
    if task_id not in TASKS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    task = TASKS[task_id]
    
    if task["status"] != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务尚未完成，当前状态: {task['status']}"
        )
    
    if not task.get("result"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="结果不存在"
        )
    
    return OCRResult(
        task_id=task_id,
        text=task["result"],
        metadata={
            "created_at": task["created_at"],
            "file_path": task["file_path"],
            "result_path": task["result_path"]
        }
    )

@app.get("/")
async def root():
    return {"message": "欢迎使用olmOCR API服务"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
