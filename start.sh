#!/bin/bash

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "配置文件 config.yaml 不存在，从示例创建..."
    cp config.yaml.example config.yaml
    echo "请编辑 config.yaml 文件设置正确的配置！"
    exit 1
fi

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "环境变量文件 .env 不存在，从示例创建..."
    cp .env.example .env
    echo "请编辑 .env 文件设置正确的环境变量！"
    exit 1
fi

# 检查工作目录
WORK_DIR=$(grep "WORK_DIR" .env | cut -d'=' -f2)
if [ -z "$WORK_DIR" ]; then
    WORK_DIR="./olmocr_workdir"
fi

mkdir -p "$WORK_DIR"
echo "使用工作目录: $WORK_DIR"

# 启动服务
echo "启动 olmOCR API 服务..."
uvicorn main:app --host 0.0.0.0 --port 8000
