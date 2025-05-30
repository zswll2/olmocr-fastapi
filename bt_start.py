#!/usr/bin/env python3
"""
宝塔面板启动脚本

此脚本用于在宝塔面板中启动olmocr-fastapi服务，提供更好的错误处理和日志记录
"""

import os
import sys
import logging
from pathlib import Path

# 设置基本日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("olmocr_startup.log", encoding='utf-8'),
    ]
)
logger = logging.getLogger("olmocr_startup")

def check_dependencies():
    """检查必要的依赖是否已安装"""
    required_packages = [
        "fastapi", "uvicorn", "python-multipart", "python-jose", 
        "passlib", "olmocr", "pyyaml", "python-dotenv"
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.split("[")[0])  # 处理如 'python-jose[cryptography]' 的情况
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        logger.error(f"缺少必要的依赖: {', '.join(missing_packages)}")
        logger.error("请运行: pip install -r requirements.txt --find-links https://flashinfer.ai/whl/cu124/torch2.4/flashinfer/")
        return False
    
    return True

def check_config_files():
    """检查配置文件是否存在，如果不存在则创建示例文件"""
    config_yaml = Path("config.yaml")
    env_file = Path(".env")
    
    if not config_yaml.exists():
        example_file = Path("config.yaml.example")
        if example_file.exists():
            logger.warning(f"配置文件 {config_yaml} 不存在，从示例创建...")
            with open(example_file, "r", encoding="utf-8") as src:
                with open(config_yaml, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            logger.info(f"已创建配置文件 {config_yaml}，请检查并编辑配置!")
        else:
            logger.error(f"配置文件 {config_yaml} 和示例文件都不存在!")
            return False
    
    if not env_file.exists():
        example_file = Path(".env.example")
        if example_file.exists():
            logger.warning(f"环境变量文件 {env_file} 不存在，从示例创建...")
            with open(example_file, "r", encoding="utf-8") as src:
                with open(env_file, "w", encoding="utf-8") as dst:
                    dst.write(src.read())
            logger.info(f"已创建环境变量文件 {env_file}，请检查并编辑配置!")
    
    return True

def check_work_directory():
    """检查工作目录是否存在，如果不存在则创建"""
    # 尝试从配置中获取工作目录
    work_dir = os.getenv("WORK_DIR", "./olmocr_workdir")
    
    try:
        # 尝试从YAML配置获取
        import yaml
        if Path("config.yaml").exists():
            with open("config.yaml", "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
                if "olmocr" in config and "work_dir" in config["olmocr"]:
                    work_dir = config["olmocr"]["work_dir"]
    except Exception as e:
        logger.warning(f"读取YAML配置时出错: {e}")
    
    work_dir_path = Path(work_dir)
    if not work_dir_path.exists():
        logger.info(f"创建工作目录: {work_dir}")
        try:
            work_dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"工作目录创建成功: {work_dir}")
        except Exception as e:
            logger.error(f"创建工作目录时出错: {e}")
            return False
    
    # 检查权限
    try:
        test_file = work_dir_path / ".write_test"
        with open(test_file, "w") as f:
            f.write("test")
        test_file.unlink()
        logger.info(f"工作目录权限正常: {work_dir}")
    except Exception as e:
        logger.error(f"工作目录权限检查失败: {e}")
        logger.error(f"请确保用户对工作目录 {work_dir} 有写入权限")
        return False
    
    return True

def start_service():
    """启动服务"""
    try:
        import uvicorn
        from main import app
        
        # 尝试从配置获取主机和端口
        host = os.getenv("APP_HOST", "0.0.0.0")
        port = int(os.getenv("APP_PORT", "8000"))
        
        # 尝试从YAML配置获取
        try:
            import yaml
            if Path("config.yaml").exists():
                with open("config.yaml", "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if "app" in config:
                        if "host" in config["app"]:
                            host = config["app"]["host"]
                        if "port" in config["app"]:
                            port = config["app"]["port"]
        except Exception as e:
            logger.warning(f"读取YAML配置时出错: {e}")
        
        logger.info(f"启动olmOCR API服务，监听地址: {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        logger.error(f"启动服务时出错: {e}")
        return False
    
    return True

def main():
    """主函数"""
    logger.info("正在启动olmOCR API服务...")
    
    # 检查当前目录
    current_dir = Path.cwd()
    logger.info(f"当前工作目录: {current_dir}")
    
    # 检查依赖
    if not check_dependencies():
        return 1
    
    # 检查配置文件
    if not check_config_files():
        return 1
    
    # 检查工作目录
    if not check_work_directory():
        return 1
    
    # 启动服务
    if not start_service():
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
