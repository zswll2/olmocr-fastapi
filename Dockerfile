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

# 复制配置文件（如果不存在则使用示例）
RUN if [ ! -f "config.yaml" ]; then cp config.yaml.example config.yaml; fi \
    && if [ ! -f ".env" ]; then cp .env.example .env; fi

# 暴露端口
EXPOSE 8000

# 设置启动脚本为可执行
RUN chmod +x start.sh

# 启动应用
CMD ["./start.sh"]
