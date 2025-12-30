#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库连接诊断工具
检查 MySQL 服务状态和测试数据库连接
用于启动脚本的环境检查
"""
import subprocess
import re
import sys
import pymysql
from typing import Tuple, Optional


def check_mysql_service() -> Tuple[Optional[str], Optional[str]]:
    """
    检查 MySQL 服务状态
    
    Returns:
        tuple: (status, service_name)
        status: 'RUNNING', 'STOPPED', 或 None（未找到）
        service_name: 服务名称，如果未找到则为 None
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
                # 提取服务状态
                parts = line.split()
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
        return None, None


def start_mysql_service(service_name: str) -> bool:
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
        return False


def test_database_connection(host: str, port: int, user: str, password: str, database: str) -> Tuple[bool, Optional[str]]:
    """
    测试数据库连接
    
    Args:
        host: 数据库主机
        port: 数据库端口
        user: 数据库用户名
        password: 数据库密码
        database: 数据库名称
    
    Returns:
        tuple: (success, error_message)
        success: 连接是否成功
        error_message: 错误信息（如果失败）
    """
    try:
        # 先尝试连接到 MySQL 服务器（不指定数据库）
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            charset='utf8mb4',
            connect_timeout=5
        )
        
        # 测试是否可以执行查询
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        
        # 检查数据库是否存在
        with connection.cursor() as cursor:
            cursor.execute("SHOW DATABASES LIKE %s", (database,))
            exists = cursor.fetchone()
            if not exists:
                connection.close()
                return False, f"数据库 '{database}' 不存在"
        
        connection.close()
        return True, None
        
    except pymysql.err.OperationalError as e:
        error_code, error_msg = e.args
        if error_code == 1045:
            return False, "用户名或密码错误"
        elif error_code == 2003:
            return False, f"无法连接到 MySQL 服务器 {host}:{port}（服务可能未启动）"
        elif error_code == 1049:
            return False, f"数据库 '{database}' 不存在"
        else:
            return False, f"连接错误 ({error_code}): {error_msg}"
    except pymysql.err.Error as e:
        return False, f"MySQL 错误: {e}"
    except Exception as e:
        return False, f"未知错误: {e}"


def diagnose_database_connection(host: str, port: int, user: str, password: str, database: str) -> dict:
    """
    诊断数据库连接问题
    
    Args:
        host: 数据库主机
        port: 数据库端口
        user: 数据库用户名
        password: 数据库密码
        database: 数据库名称
    
    Returns:
        dict: 诊断结果
        {
            'service_status': 'RUNNING' | 'STOPPED' | None,
            'service_name': str | None,
            'connection_success': bool,
            'error_message': str | None,
            'recommendations': list[str]
        }
    """
    result = {
        'service_status': None,
        'service_name': None,
        'connection_success': False,
        'error_message': None,
        'recommendations': []
    }
    
    # 1. 检查 MySQL 服务状态
    service_status, service_name = check_mysql_service()
    result['service_status'] = service_status
    result['service_name'] = service_name
    
    if service_status is None:
        result['recommendations'].append("未检测到 MySQL 服务，请确认 MySQL 已安装")
    elif service_status == 'STOPPED':
        result['recommendations'].append(f"MySQL 服务未运行（服务名: {service_name}），请启动服务")
        result['recommendations'].append(f"启动命令: net start \"{service_name}\"（需要管理员权限）")
        return result  # 服务未运行，不需要测试连接
    
    # 2. 测试数据库连接
    connection_success, error_message = test_database_connection(host, port, user, password, database)
    result['connection_success'] = connection_success
    result['error_message'] = error_message
    
    if not connection_success:
        if "用户名或密码错误" in error_message:
            result['recommendations'].append("请检查数据库用户名和密码是否正确")
            result['recommendations'].append("可以尝试使用 MySQL 命令行工具测试: mysql -u {} -p -h {} -P {}".format(user, host, port))
        elif "不存在" in error_message:
            result['recommendations'].append(f"数据库 '{database}' 不存在，请先创建数据库")
            result['recommendations'].append("运行迁移脚本创建数据库: scripts\\setup\\migrate_database\\migrate_database.bat")
        elif "无法连接" in error_message or "服务可能未启动" in error_message:
            result['recommendations'].append("虽然检测到 MySQL 服务运行，但无法连接，请检查：")
            result['recommendations'].append("  1. 端口号是否正确（当前: {}）".format(port))
            result['recommendations'].append("  2. MySQL 是否监听在正确的地址上")
            result['recommendations'].append("  3. 防火墙是否阻止了连接")
        else:
            result['recommendations'].append(f"连接失败: {error_message}")
    
    return result

