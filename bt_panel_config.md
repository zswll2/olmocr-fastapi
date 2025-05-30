# 宝塔面板配置详细指南

本文档提供了在宝塔面板上配置olmOCR FastAPI服务的详细步骤。

## 1. 安装宝塔面板（如果尚未安装）

```bash
# CentOS
yum install -y wget && wget -O install.sh http://download.bt.cn/install/install_6.0.sh && sh install.sh

# Ubuntu/Debian
wget -O install.sh http://download.bt.cn/install/install-ubuntu_6.0.sh && sudo bash install.sh
```

## 2. 安装必要的软件

在宝塔面板中安装以下软件：

- Nginx（推荐1.20或更高版本）
- Supervisor管理器

## 3. 创建网站

1. 在宝塔面板中，点击「网站」>「添加站点」
2. 填写域名（例如：olmocr.yourdomain.com）
3. 选择纯静态，不需要数据库
4. 点击「提交」创建站点

## 4. 配置网站目录

1. 通过SSH连接到服务器
2. 导航到网站根目录：

```bash
cd /www/wwwroot/olmocr.yourdomain.com
```

3. 克隆olmocr-fastapi仓库：

```bash
git clone https://github.com/zswll2/olmocr-fastapi.git .
```

## 5. 安装系统依赖

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils ttf-mscorefonts-installer msttcorefonts fonts-crosextra-caladea fonts-crosextra-carlito gsfonts lcdf-typetools
```

## 6. 设置Python环境

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt --find-links https://flashinfer.ai/whl/cu124/torch2.4/flashinfer/
```

## 7. 生成安全密钥

```bash
python generate_secret_key.py
```

按照提示更新main.py中的SECRET_KEY。

## 8. 配置Supervisor

1. 在宝塔面板中，点击「软件商店」>「Supervisor管理器」
2. 点击「添加守护进程」
3. 填写以下信息：
   - 名称：olmocr_api
   - 启动用户：www
   - 运行目录：/www/wwwroot/olmocr.yourdomain.com
   - 启动命令：/www/wwwroot/olmocr.yourdomain.com/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
   - 进程数量：1
   - 优先级：999
4. 点击「确定」保存

## 9. 配置Nginx反向代理

1. 在宝塔面板中，点击「网站」>「olmocr.yourdomain.com」>「设置」
2. 点击「反向代理」>「添加反向代理」
3. 填写以下信息：
   - 名称：olmocr_api
   - 目标URL：http://127.0.0.1:8000
4. 点击「提交」保存

## 10. 配置Bearer认证安全性

1. 在宝塔面板中，点击「网站」>「olmocr.yourdomain.com」>「设置」>「SSL」
2. 申请或上传SSL证书，启用HTTPS

## 11. 启动服务

1. 在宝塔面板中，点击「软件商店」>「Supervisor管理器」
2. 找到olmocr_api进程，点击「启动」

## 12. 测试服务

1. 访问https://olmocr.yourdomain.com/docs查看API文档
2. 使用以下命令获取访问令牌：

```bash
curl -X POST "https://olmocr.yourdomain.com/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=secret"
```

## 13. 监控和日志

1. 在宝塔面板中，点击「软件商店」>「Supervisor管理器」>「olmocr_api」>「日志」查看运行日志
2. 在服务器上，可以查看以下日志文件：
   - `/www/wwwroot/olmocr.yourdomain.com/olmocr-pipeline-debug.log`

## 14. 常见问题排查

### 问题：服务无法启动

检查：
1. 确保NVIDIA驱动和CUDA已正确安装
2. 检查Python虚拟环境是否正确激活
3. 检查依赖是否全部安装成功

### 问题：上传文件失败

检查：
1. 确保工作目录有正确的写入权限
2. 检查Nginx上传文件大小限制（在宝塔面板中可调整）

### 问题：处理PDF时出错

检查：
1. 确保poppler-utils已正确安装
2. 检查GPU是否可用
3. 查看olmocr-pipeline-debug.log日志文件

## 15. 安全建议

1. 修改默认的admin用户密码
2. 限制API的访问IP（通过Nginx配置）
3. 设置适当的文件上传大小限制
4. 定期备份重要数据
