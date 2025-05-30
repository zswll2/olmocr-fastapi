import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

# 尝试导入dotenv，如果不可用则跳过
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed, skipping .env loading")

# 配置模型
class AppConfig(BaseModel):
    title: str
    description: str
    version: str
    host: str
    port: int
    debug: bool

class SecurityConfig(BaseModel):
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int

class UserConfig(BaseModel):
    username: str
    password: str

class OlmocrConfig(BaseModel):
    work_dir: str
    pipeline_options: Dict[str, Any]

class UploadConfig(BaseModel):
    allowed_extensions: List[str]
    max_file_size_mb: int

class LoggingConfig(BaseModel):
    level: str
    file: str
    format: str

class Config(BaseModel):
    app: AppConfig
    security: SecurityConfig
    users: List[UserConfig]
    olmocr: OlmocrConfig
    upload: UploadConfig
    logging: LoggingConfig

# 加载配置
def load_config() -> Config:
    """加载配置文件和环境变量"""
    # 默认配置文件路径
    config_path = Path(os.getenv("CONFIG_PATH", "config.yaml"))
    
    # 如果配置文件存在，从文件加载配置
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config file: {e}")
            config_data = create_default_config()
    else:
        # 否则使用默认配置
        config_data = create_default_config()
    
    # 环境变量覆盖配置文件
    override_config_with_env(config_data)
    
    try:
        return Config(**config_data)
    except Exception as e:
        print(f"Error validating config: {e}")
        # 如果验证失败，使用最小配置
        return Config(**create_minimal_config())

def create_default_config() -> Dict[str, Any]:
    """创建默认配置"""
    return {
        "app": {
            "title": "olmOCR API",
            "description": "用于PDF和图像文档OCR处理的API接口",
            "version": "1.0.0",
            "host": os.getenv("APP_HOST", "0.0.0.0"),
            "port": int(os.getenv("APP_PORT", "8000")),
            "debug": os.getenv("DEBUG", "false").lower() == "true",
        },
        "security": {
            "secret_key": os.getenv("SECRET_KEY", "your_secret_key_here"),
            "algorithm": "HS256",
            "access_token_expire_minutes": int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")),
        },
        "users": [
            {
                "username": os.getenv("ADMIN_USERNAME", "admin"),
                "password": os.getenv("ADMIN_PASSWORD", "secret"),
            }
        ],
        "olmocr": {
            "work_dir": os.getenv("WORK_DIR", "./olmocr_workdir"),
            "pipeline_options": {
                "markdown": True,
                "extract_tables": True,
                "extract_figures": True,
            },
        },
        "upload": {
            "allowed_extensions": [".pdf", ".png", ".jpg", ".jpeg"],
            "max_file_size_mb": 50,
        },
        "logging": {
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "file": os.getenv("LOG_FILE", "olmocr_api.log"),
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }

def create_minimal_config() -> Dict[str, Any]:
    """创建最小配置，用于配置验证失败时"""
    return {
        "app": {
            "title": "olmOCR API",
            "description": "API Interface",
            "version": "1.0.0",
            "host": "0.0.0.0",
            "port": 8000,
            "debug": False,
        },
        "security": {
            "secret_key": "fallback_secret_key",
            "algorithm": "HS256",
            "access_token_expire_minutes": 30,
        },
        "users": [
            {
                "username": "admin",
                "password": "secret",
            }
        ],
        "olmocr": {
            "work_dir": "./olmocr_workdir",
            "pipeline_options": {
                "markdown": True,
            },
        },
        "upload": {
            "allowed_extensions": [".pdf", ".png", ".jpg", ".jpeg"],
            "max_file_size_mb": 50,
        },
        "logging": {
            "level": "INFO",
            "file": "olmocr_api.log",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
    }

def override_config_with_env(config_data: Dict[str, Any]) -> None:
    """使用环境变量覆盖配置"""
    # 应用设置
    if os.getenv("APP_HOST"):
        config_data["app"]["host"] = os.getenv("APP_HOST")
    if os.getenv("APP_PORT"):
        config_data["app"]["port"] = int(os.getenv("APP_PORT"))
    if os.getenv("DEBUG"):
        config_data["app"]["debug"] = os.getenv("DEBUG").lower() == "true"
    
    # 安全设置
    if os.getenv("SECRET_KEY"):
        config_data["security"]["secret_key"] = os.getenv("SECRET_KEY")
    if os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"):
        config_data["security"]["access_token_expire_minutes"] = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
    
    # 用户设置
    if os.getenv("ADMIN_USERNAME") and os.getenv("ADMIN_PASSWORD"):
        admin_found = False
        for user in config_data["users"]:
            if user["username"] == "admin":
                user["username"] = os.getenv("ADMIN_USERNAME")
                user["password"] = os.getenv("ADMIN_PASSWORD")
                admin_found = True
                break
        if not admin_found:
            config_data["users"].append({
                "username": os.getenv("ADMIN_USERNAME"),
                "password": os.getenv("ADMIN_PASSWORD")
            })
    
    # olmocr设置
    if os.getenv("WORK_DIR"):
        config_data["olmocr"]["work_dir"] = os.getenv("WORK_DIR")
    
    # 日志设置
    if os.getenv("LOG_LEVEL"):
        config_data["logging"]["level"] = os.getenv("LOG_LEVEL")
    if os.getenv("LOG_FILE"):
        config_data["logging"]["file"] = os.getenv("LOG_FILE")

# 设置日志
def setup_logging(config: LoggingConfig) -> None:
    """设置日志"""
    log_level = getattr(logging, config.level.upper(), logging.INFO)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format=config.format,
        handlers=[
            logging.FileHandler(config.file, encoding='utf-8'),
            logging.StreamHandler(),
        ]
    )

try:
    # 全局配置实例
    config = load_config()

    # 设置日志
    setup_logging(config.logging)

    # 导出配置
    APP = config.app
    SECURITY = config.security
    USERS = config.users
    OLMOCR = config.olmocr
    UPLOAD = config.upload
    LOGGING = config.logging
except Exception as e:
    print(f"Error initializing config: {e}")
    # 创建一个简单的命名空间作为回退
    class SimpleNamespace:
        pass
    
    APP = SimpleNamespace()
    APP.title = "olmOCR API"
    APP.description = "API Interface"
    APP.version = "1.0.0"
    APP.host = "0.0.0.0"
    APP.port = 8000
    APP.debug = False
    
    SECURITY = SimpleNamespace()
    SECURITY.secret_key = "fallback_secret_key"
    SECURITY.algorithm = "HS256"
    SECURITY.access_token_expire_minutes = 30
    
    class UserConfig:
        def __init__(self, username, password):
            self.username = username
            self.password = password
    
    USERS = [UserConfig("admin", "secret")]
    
    OLMOCR = SimpleNamespace()
    OLMOCR.work_dir = "./olmocr_workdir"
    OLMOCR.pipeline_options = {"markdown": True}
    
    UPLOAD = SimpleNamespace()
    UPLOAD.allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg"]
    UPLOAD.max_file_size_mb = 50
    
    LOGGING = SimpleNamespace()
    LOGGING.level = "INFO"
    LOGGING.file = "olmocr_api.log"
    LOGGING.format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # 设置基本日志
    logging.basicConfig(
        level=logging.INFO,
        format=LOGGING.format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOGGING.file, encoding='utf-8'),
        ]
    )
