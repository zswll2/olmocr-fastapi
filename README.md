# olmOCR FastAPI服务

这是一个基于[allenai/olmocr](https://github.com/allenai/olmocr)的FastAPI包装器，提供了REST API接口，用于将PDF和图像文档转换为可读文本。

## 功能特点

- 使用Bearer令牌进行API认证
- 支持PDF、PNG、JPG文件处理
- 异步任务处理
- 完整的任务状态跟踪
- 基于FastAPI的现代API设计
- 支持Docker容器化部署

## 系统要求

- NVIDIA GPU (至少20GB显存)
- CUDA 12.x
- Ubuntu 20.04或更高版本

## 安装方法

### 方法1：直接安装

1. 安装系统依赖：

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils ttf-mscorefonts-installer msttcorefonts fonts-crosextra-caladea fonts-crosextra-carlito gsfonts lcdf-typetools
```

2. 创建Python虚拟环境：

```bash
python -m venv venv
source venv/bin/activate
```

3. 安装Python依赖：

```bash
pip install -r requirements.txt --find-links https://flashinfer.ai/whl/cu124/torch2.4/flashinfer/
```

4. 启动服务：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 方法2：Docker部署

1. 构建Docker镜像：

```bash
docker build -t olmocr-api .
```

2. 运行容器：

```bash
docker run -d --gpus all -p 8000:8000 --name olmocr-api olmocr-api
```

## 宝塔面板部署指南

### 1. 准备工作

1. 确保服务器已安装NVIDIA驱动和CUDA 12.x
2. 确保已安装宝塔面板

### 2. 创建网站

1. 在宝塔面板中创建一个新网站，例如`olmocr.yourdomain.com`
2. 选择纯静态网站，不需要安装任何环境

### 3. 安装依赖

1. 通过SSH连接到服务器
2. 安装系统依赖：

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils ttf-mscorefonts-installer msttcorefonts fonts-crosextra-caladea fonts-crosextra-carlito gsfonts lcdf-typetools
```

3. 在网站根目录创建Python虚拟环境：

```bash
cd /www/wwwroot/olmocr.yourdomain.com
python -m venv venv
source venv/bin/activate
```

4. 安装Python依赖：

```bash
pip install -r requirements.txt --find-links https://flashinfer.ai/whl/cu124/torch2.4/flashinfer/
```

### 4. 配置ASGI服务

1. 在宝塔面板中，选择「网站」>「olmocr.yourdomain.com」>「网站设置」>「反向代理」
2. 添加一个新的反向代理，目标URL设置为`http://127.0.0.1:8000`

### 5. 创建Supervisor配置

1. 在宝塔面板中，选择「软件商店」>「Supervisor管理器」>「安装」
2. 安装完成后，添加一个新的守护进程：
   - 名称：`olmocr_api`
   - 启动用户：`www`
   - 运行目录：`/www/wwwroot/olmocr.yourdomain.com`
   - 启动命令：`/www/wwwroot/olmocr.yourdomain.com/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`

### 6. 启动服务

1. 点击Supervisor中的「启动」按钮启动服务
2. 访问`https://olmocr.yourdomain.com/docs`查看API文档

## API使用指南

### 1. 获取访问令牌

```bash
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret"
```

响应：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. 上传文档进行OCR处理

```bash
curl -X POST "http://localhost:8000/ocr/upload" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -F "file=@/path/to/your/document.pdf"
```

响应：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "progress": 0,
  "created_at": "2025-05-30T12:34:56.789012"
}
```

### 3. 查询任务状态

```bash
curl -X GET "http://localhost:8000/ocr/status/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

响应：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 0.5,
  "created_at": "2025-05-30T12:34:56.789012"
}
```

### 4. 获取处理结果

```bash
curl -X GET "http://localhost:8000/ocr/result/550e8400-e29b-41d4-a716-446655440000" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

响应：

```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "text": "这是从PDF提取的文本内容...",
  "metadata": {
    "created_at": "2025-05-30T12:34:56.789012",
    "file_path": "/app/olmocr_workdir/550e8400-e29b-41d4-a716-446655440000_document.pdf",
    "result_path": "/app/olmocr_workdir/550e8400-e29b-41d4-a716-446655440000/markdown/document.md"
  }
}
```

## 安全注意事项

1. 在生产环境中，请修改`main.py`中的`SECRET_KEY`为一个安全的随机字符串
2. 建议配置HTTPS以保护API通信
3. 可以修改`fake_users_db`字典，添加更多用户或集成数据库认证

## 许可证

本项目遵循Apache 2.0许可证。olmOCR的原始代码版权归Allen Institute for Artificial Intelligence所有。

## 贡献

欢迎提交问题和拉取请求！
