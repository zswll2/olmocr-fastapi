import os
import uuid
import shutil
import asyncio
import logging
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

# 导入配置
try:
    from config import APP, SECURITY, USERS, OLMOCR, UPLOAD, LOGGING
    use_config_module = True
except ImportError:
    # 如果配置模块不可用，使用硬编码的配置
    use_config_module = False
    # 默认配置
    class SimpleNamespace:
        pass
    
    APP = SimpleNamespace()
    APP.title = "olmOCR API"
    APP.description = "用于PDF和图像文档OCR处理的API接口"
    APP.version = "1.0.0"
    APP.host = "0.0.0.0"
    APP.port = 8015
    APP.debug = False
    
    SECURITY = SimpleNamespace()
    SECURITY.secret_key = "your_secret_key_here"
    SECURITY.algorithm = "HS256"
    SECURITY.access_token_expire_minutes = 30
    
    class UserConfig:
        def __init__(self, username, password):
            self.username = username
            self.password = password
    
    USERS = [UserConfig("admin", "secret")]
    
    OLMOCR = SimpleNamespace()
    OLMOCR.work_dir = "./olmocr_workdir"
    OLMOCR.pipeline_options = {"markdown": True, "extract_tables": True, "extract_figures": True}
    
    UPLOAD = SimpleNamespace()
    UPLOAD.allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg"]
    UPLOAD.max_file_size_mb = 50
    
    LOGGING = SimpleNamespace()
    LOGGING.level = "INFO"
    LOGGING.file = "olmocr_api.log"
    LOGGING.format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 设置日志记录器
logging.basicConfig(
    level=getattr(logging, LOGGING.level.upper(), logging.INFO),
    format=LOGGING.format,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGGING.file, encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)

# 创建工作目录
work_dir = Path(OLMOCR.work_dir)
work_dir.mkdir(exist_ok=True)

# 创建应用
app = FastAPI(
    title=APP.title,
    description=APP.description,
    version=APP.version,
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 任务状态存储
TASKS = {}

# 密码上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 Bearer令牌
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 用户数据库 - 内存存储
fake_users_db = {}
for user in USERS:
    # 直接存储密码，登录时再哈希
    fake_users_db[user.username] = {
        "username": user.username,
        "hashed_password": user.password
    }

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
    # 如果密码是明文存储的，直接比较
    if not hashed_password.startswith("$2b$"):
        return plain_password == hashed_password
    # 否则使用bcrypt验证
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)
    return None

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
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
    encoded_jwt = jwt.encode(to_encode, SECURITY.secret_key, algorithm=SECURITY.algorithm)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECURITY.secret_key, algorithms=[SECURITY.algorithm])
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
        workspace_path = work_dir / task_id
        workspace_path.mkdir(exist_ok=True)
        
        # 更新任务状态
        TASKS[task_id]["status"] = "processing"
        logger.info(f"开始处理任务 {task_id}, 文件路径: {file_path}")
        
        # 构建命令
        cmd = [
            "python", "-m", "olmocr.pipeline",
            str(workspace_path),
        ]
        
        # 添加配置选项
        if OLMOCR.pipeline_options.get("markdown", True):
            cmd.append("--markdown")
        if OLMOCR.pipeline_options.get("extract_tables", True):
            cmd.append("--extract_tables")
        if OLMOCR.pipeline_options.get("extract_figures", True):
            cmd.append("--extract_figures")
        
        # 添加文件路径
        cmd.extend(["--pdfs", file_path])
        
        logger.debug(f"执行命令: {' '.join(cmd)}")
        
        # 执行命令
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"任务 {task_id} 处理失败: {stderr.decode()}")
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
                
                logger.info(f"任务 {task_id} 处理完成，结果保存在 {md_file}")
                TASKS[task_id]["status"] = "completed"
                TASKS[task_id]["result"] = text_content
                TASKS[task_id]["result_path"] = str(md_file)
                return
        
        logger.error(f"任务 {task_id} 处理完成但未找到结果文件")
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = "处理完成但未找到结果文件"
    except Exception as e:
        logger.exception(f"任务 {task_id} 处理异常: {str(e)}")
        TASKS[task_id]["status"] = "failed"
        TASKS[task_id]["error"] = str(e)

# API路由
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        logger.warning(f"登录失败: 用户名 {form_data.username} 认证失败")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=SECURITY.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    logger.info(f"用户 {user.username} 登录成功")
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@app.post("/ocr/upload", response_model=OCRStatus)
async def upload_document(background_tasks: BackgroundTasks, file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    # 验证文件类型
    filename = file.filename.lower()
    file_ext = Path(filename).suffix
    if file_ext not in UPLOAD.allowed_extensions:
        logger.warning(f"用户 {current_user.username} 上传了不支持的文件类型: {file_ext}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式，仅支持: {', '.join(UPLOAD.allowed_extensions)}"
        )
    
    # 检查文件大小
    file_size = 0
    chunk_size = 1024 * 1024  # 1MB
    
    # 创建临时文件
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    try:
        # 读取并写入临时文件，同时计算大小
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_size += len(chunk)
            if file_size > UPLOAD.max_file_size_mb * 1024 * 1024:
                temp_file.close()
                os.unlink(temp_file.name)
                logger.warning(f"用户 {current_user.username} 上传了过大的文件: {file_size/(1024*1024):.2f}MB")
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"文件大小超过限制，最大允许: {UPLOAD.max_file_size_mb}MB"
                )
            temp_file.write(chunk)
        
        temp_file.close()
        
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 保存上传的文件
        file_path = work_dir / f"{task_id}_{file.filename}"
        shutil.copy(temp_file.name, file_path)
        
        logger.info(f"用户 {current_user.username} 上传文件 {file.filename}，创建任务 {task_id}")
        
        # 创建任务记录
        TASKS[task_id] = {
            "status": "queued",
            "file_path": str(file_path),
            "created_at": datetime.now().isoformat(),
            "result": None,
            "result_path": None,
            "error": None,
            "user": current_user.username
        }
        
        # 后台处理文档
        background_tasks.add_task(process_document, task_id, str(file_path))
        
        return OCRStatus(
            task_id=task_id,
            status="queued",
            created_at=TASKS[task_id]["created_at"]
        )
    finally:
        # 确保临时文件被删除
        try:
            os.unlink(temp_file.name)
        except:
            pass

@app.get("/ocr/status/{task_id}", response_model=OCRStatus)
async def get_task_status(task_id: str, current_user: User = Depends(get_current_user)):
    if task_id not in TASKS:
        logger.warning(f"用户 {current_user.username} 查询不存在的任务 {task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    task = TASKS[task_id]
    
    # 检查任务所有权（可选）
    if "user" in task and task["user"] != current_user.username:
        logger.warning(f"用户 {current_user.username} 尝试访问其他用户的任务 {task_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    logger.debug(f"用户 {current_user.username} 查询任务 {task_id} 状态: {task['status']}")
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
        logger.warning(f"用户 {current_user.username} 查询不存在的任务结果 {task_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务不存在"
        )
    
    task = TASKS[task_id]
    
    # 检查任务所有权（可选）
    if "user" in task and task["user"] != current_user.username:
        logger.warning(f"用户 {current_user.username} 尝试访问其他用户的任务结果 {task_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="无权访问此任务"
        )
    
    if task["status"] != "completed":
        logger.warning(f"用户 {current_user.username} 尝试获取未完成的任务结果 {task_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"任务尚未完成，当前状态: {task['status']}"
        )
    
    if not task.get("result"):
        logger.error(f"任务 {task_id} 标记为完成但结果不存在")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="结果不存在"
        )
    
    logger.info(f"用户 {current_user.username} 获取任务 {task_id} 结果")
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
    return {"message": f"欢迎使用{APP.title}服务"}

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.on_event("startup")
async def startup_event():
    logger.info(f"{APP.title} 启动成功，监听地址: {APP.host}:{APP.port}")
    logger.info(f"工作目录: {work_dir}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=APP.host, port=APP.port, reload=APP.debug)
