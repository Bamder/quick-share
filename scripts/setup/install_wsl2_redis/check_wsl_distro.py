#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 WSL 发行版信息
返回默认发行版名称和版本
"""
import subprocess
import sys
import re

def get_wsl_distros():
    """获取 WSL 发行版列表"""
    try:
        result = subprocess.run(
            ["wsl", "--list", "--verbose"],
            capture_output=True,
            text=False,  # 先获取字节数据
            timeout=10
        )
        if result.returncode != 0:
            return None
        
        # 尝试解码为 UTF-16（Windows 命令通常使用 UTF-16）
        try:
            output = result.stdout.decode('utf-16-le')
        except UnicodeDecodeError:
            # 如果 UTF-16 失败，尝试 UTF-8
            try:
                output = result.stdout.decode('utf-8')
            except UnicodeDecodeError:
                # 最后尝试使用错误处理
                output = result.stdout.decode('utf-8', errors='ignore')
        
        return output
    except Exception as e:
        print(f"错误: 无法获取 WSL 发行版列表: {e}", file=sys.stderr)
        return None

def parse_wsl_distros(output):
    """解析 WSL 发行版输出"""
    if not output:
        return None, None
    
    lines = output.strip().split('\n')
    default_distro = None
    default_version = None
    
    # 首先查找带 * 标记的默认发行版
    for line in lines:
        line = line.strip()
        if not line or 'NAME' in line.upper():
            continue
        
        # 检查是否是默认发行版（包含 * 标记）
        if '*' in line:
            # 提取发行版名称和版本
            # 格式: * Ubuntu-22.04      Running         2
            # 或者:   * Ubuntu-22.04      Running         2 (前面可能有空格)
            
            # 移除开头的 * 和空格（使用正则表达式更可靠）
            line_clean = re.sub(r'^\s*\*\s*', '', line).strip()
            # 使用正则表达式分割多个空格
            parts = re.split(r'\s+', line_clean)
            
            if len(parts) >= 3:
                # 第一个字段是发行版名称
                distro_name = parts[0]
                # 最后一个字段应该是版本号（1 或 2）
                version = parts[-1]
                
                # 验证版本号（应该是 1 或 2）
                if version in ['1', '2']:
                    default_distro = distro_name
                    default_version = version
                    break
                else:
                    # 如果最后一个字段不是版本号，尝试倒数第二个
                    if len(parts) >= 4 and parts[-2] in ['1', '2']:
                        default_distro = distro_name
                        default_version = parts[-2]
                        break
                    # 如果都不匹配，仍然使用最后一个字段（可能是未知格式，但保持兼容性）
                    default_distro = distro_name
                    default_version = version
                    break
    
    # 如果没有找到默认发行版，取第一个有效的发行版
    if not default_distro:
        for line in lines:
            line = line.strip()
            if not line or 'NAME' in line.upper() or '*' in line:
                continue
            
            # 使用正则表达式分割多个空格
            parts = re.split(r'\s+', line)
            if len(parts) >= 3:
                distro_name = parts[0]
                version = parts[-1]
                
                # 验证版本号
                if version in ['1', '2']:
                    default_distro = distro_name
                    default_version = version
                    break
                elif len(parts) >= 4 and parts[-2] in ['1', '2']:
                    default_distro = distro_name
                    default_version = parts[-2]
                    break
                else:
                    # 如果都不匹配，使用最后一个字段并假设是版本号
                    default_distro = distro_name
                    default_version = version
                    break
    
    return default_distro, default_version

def main():
    """主函数"""
    output = get_wsl_distros()
    if output is None:
        print("ERROR:无法获取WSL发行版列表", file=sys.stderr)
        sys.exit(1)
    
    distro, version = parse_wsl_distros(output)
    
    if distro:
        # 输出格式: DISTRO|VERSION
        print(f"{distro}|{version}")
        sys.exit(0)
    else:
        print("ERROR:未找到WSL发行版", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

