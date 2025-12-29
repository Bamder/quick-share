#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检测和启动 MySQL 服务
动态检测所有包含 MySQL 的服务（不硬编码任何服务名称）
支持自动启动服务（需要管理员权限）
"""
import subprocess
import sys
import re
import os


def check_mysql_service():
    """
    检测 MySQL 服务状态
    
    Returns:
        tuple: (status, service_name) 或 (None, None) 如果未找到
        status: 'RUNNING' 或 'STOPPED'
        service_name: 服务名称
    """
    try:
        # 使用 sc query 获取所有服务
        result = subprocess.run(
            ['sc', 'query', 'type=', 'service', 'state=', 'all'],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        if result.returncode != 0:
            return None, None
        
        services = []
        current_service = None
        
        # 解析服务列表
        for line in result.stdout.split('\n'):
            line = line.strip()
            if line.startswith('SERVICE_NAME:'):
                # 提取服务名称
                service_name = line.split(':', 1)[1].strip()
                # 检查是否包含 mysql（不区分大小写）
                if re.search(r'mysql', service_name, re.IGNORECASE):
                    current_service = {'name': service_name, 'state': None}
            elif line.startswith('STATE') and current_service:
                # 提取服务状态（可能是 STATE : 1 RUNNING 或 STATE : 4 RUNNING 等格式）
                parts = line.split()
                # 查找 RUNNING、STOPPED、START_PENDING 等状态
                state = None
                for part in parts:
                    if part in ['RUNNING', 'STOPPED', 'START_PENDING', 'STOP_PENDING', 'PAUSED']:
                        state = part
                        break
                # 如果没有找到明确状态，尝试从数字判断
                # Windows 服务状态码：1=STOPPED, 2=START_PENDING, 3=STOP_PENDING, 4=RUNNING, 7=PAUSED
                if not state and len(parts) >= 3:
                    try:
                        state_num = int(parts[2])
                        if state_num == 1:  # STOPPED
                            state = 'STOPPED'
                        elif state_num == 4:  # RUNNING
                            state = 'RUNNING'
                        elif state_num == 2:  # START_PENDING
                            state = 'START_PENDING'
                        elif state_num == 3:  # STOP_PENDING
                            state = 'STOP_PENDING'
                        elif state_num == 7:  # PAUSED
                            state = 'PAUSED'
                    except (ValueError, IndexError):
                        pass
                
                if state:
                    current_service['state'] = state
                    services.append(current_service)
                current_service = None
        
        if not services:
            return None, None
        
        # 优先返回运行中的服务（包括正在启动的服务）
        for svc in services:
            if svc['state'] in ['RUNNING', 'START_PENDING']:
                return 'RUNNING', svc['name']
        
        # 如果没有运行中的，返回第一个找到的服务
        return 'STOPPED', services[0]['name']
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return None, None


def start_mysql_service(service_name):
    """
    启动 MySQL 服务
    
    Args:
        service_name: 服务名称
    
    Returns:
        bool: 成功返回 True，失败返回 False
    """
    try:
        result = subprocess.run(
            ['net', 'start', service_name],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error starting service: {e}", file=sys.stderr)
        return False


def main():
    """主函数，支持命令行参数"""
    # 检查是否需要启动服务
    auto_start = len(sys.argv) > 1 and sys.argv[1] == '--auto-start'
    
    status, service_name = check_mysql_service()
    
    if not service_name:
        print("NOT_FOUND")
        sys.exit(1)
    
    if status == 'RUNNING':
        print(f"RUNNING|{service_name}")
        sys.exit(0)
    elif status == 'STOPPED':
        if auto_start:
            # 尝试自动启动
            print(f"尝试启动服务: {service_name}", file=sys.stderr)
            if start_mysql_service(service_name):
                # 再次检查状态
                new_status, _ = check_mysql_service()
                if new_status == 'RUNNING':
                    print(f"RUNNING|{service_name}")
                    sys.exit(0)
                else:
                    print(f"STOPPED|{service_name}|START_FAILED")
                    sys.exit(1)
            else:
                print(f"STOPPED|{service_name}|START_FAILED")
                sys.exit(1)
        else:
            print(f"STOPPED|{service_name}")
            sys.exit(0)
    else:
        print("NOT_FOUND")
        sys.exit(1)


if __name__ == '__main__':
    main()

