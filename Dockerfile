FROM nvidia/cuda:12.4.0-devel-ubuntu22.04

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 python3-pip python3-dev \
    poppler-utils ttf-mscorefonts-installer fonts-crosextra-caladea \
    fonts-crosextra-carlito gsfonts lcdf-typetools \
    wget git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt --find-links https://flashinfer.ai/whl/cu124/torch2.4/flashinfer/

# 复制应用代码
COPY . .

# 创建工作目录
RUN mkdir -p /app/olmocr_workdir

# 暴露端口
EXPOSE 8000

# 启动应用
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
