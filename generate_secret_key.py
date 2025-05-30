#!/usr/bin/env python3

import secrets
import sys

def generate_secret_key(length=64):
    """
    生成一个安全的随机密钥
    """
    return secrets.token_hex(length)

def update_main_py(secret_key):
    """
    更新main.py中的SECRET_KEY
    """
    try:
        with open('main.py', 'r') as file:
            content = file.read()
        
        # 替换SECRET_KEY
        updated_content = content.replace(
            'SECRET_KEY = "YOUR_SECRET_KEY_HERE"', 
            f'SECRET_KEY = "{secret_key}"'
        )
        
        with open('main.py', 'w') as file:
            file.write(updated_content)
        
        print(f"已成功更新main.py中的SECRET_KEY")
        return True
    except Exception as e:
        print(f"更新main.py失败: {e}")
        return False

if __name__ == "__main__":
    key_length = 32  # 默认长度
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        try:
            key_length = int(sys.argv[1])
        except ValueError:
            print(f"错误: 长度参数必须是整数")
            sys.exit(1)
    
    # 生成密钥
    secret_key = generate_secret_key(key_length)
    
    print(f"生成的SECRET_KEY: {secret_key}")
    
    # 询问是否更新main.py
    response = input("是否更新main.py中的SECRET_KEY? (y/n): ")
    if response.lower() in ['y', 'yes']:
        update_main_py(secret_key)
    else:
        print("请手动更新main.py中的SECRET_KEY")
