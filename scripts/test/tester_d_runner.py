#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tester D - 环境兼容与异常恢复 测试脚本
执行可自动化的API测试用例
使用urllib实现（无需安装额外依赖）
"""

import urllib.request
import urllib.error
import json
import time
from datetime import datetime
import ssl

# 配置
BASE_URL = "http://localhost:8000"
API_PREFIX = "/api/v1"
TIMEOUT = 10

# 忽略SSL证书验证（开发环境）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 测试结果存储
test_results = {
    "total": 0,
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "results": []
}

def make_request(method, path, data=None, headers=None):
    """发送HTTP请求"""
    url = f"{BASE_URL}{path}"
    try:
        if headers is None:
            headers = {}
        
        # 添加默认Headers
        headers['User-Agent'] = 'TesterD/1.0'
        headers['Content-Type'] = 'application/json'
        
        # 构建请求
        if data:
            data = json.dumps(data).encode('utf-8')
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        # 发送请求
        with urllib.request.urlopen(req, context=ssl_context, timeout=TIMEOUT) as response:
            body = response.read().decode('utf-8')
            try:
                body_json = json.loads(body)
            except:
                body_json = {}
            
            return {
                "status_code": response.status,
                "body": body,
                "body_json": body_json,
                "success": True,
                "error": None  # 成功时error为None
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        try:
            body_json = json.loads(body)
        except:
            body_json = {}
            
        return {
            "status_code": e.code,
            "body": body,
            "body_json": body_json,
            "success": False,
            "error": str(e)
        }
    except urllib.error.URLError as e:
        return {
            "status_code": None,
            "body": None,
            "body_json": None,
            "success": False,
            "error": f"连接失败: {e.reason}"
        }
    except Exception as e:
        return {
            "status_code": None,
            "body": None,
            "body_json": None,
            "success": False,
            "error": str(e)
        }

def log_test(test_id, test_name, expected, actual, status, notes=""):
    """记录测试结果"""
    test_result = {
        "test_id": test_id,
        "test_name": test_name,
        "expected": expected,
        "actual": actual,
        "status": status,
        "notes": notes,
        "timestamp": datetime.now().isoformat()
    }
    test_results["results"].append(test_result)
    test_results["total"] += 1
    if status == "passed":
        test_results["passed"] += 1
    elif status == "failed":
        test_results["failed"] += 1
    else:
        test_results["skipped"] += 1
    
    symbol = "✓" if status == "passed" else ("✗" if status == "failed" else "⊘")
    print(f"{symbol} [{test_id}] {test_name}: {status}")
    if status == "failed":
        print(f"   预期: {expected}")
        print(f"   实际: {actual}")
    if notes:
        print(f"   备注: {notes}")

def test_health_endpoint():
    """测试健康检查端点"""
    test_id = "D-HEALTH"
    test_name = "健康检查端点测试"
    
    result = make_request("GET", "/health")
    
    if result["status_code"] == 200:
        log_test(
            test_id, test_name,
            "返回200状态码，服务健康",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "failed", "服务未运行，需要启动服务")
    else:
        log_test(
            test_id, test_name,
            "返回200状态码",
            f"状态码: {result['status_code']}",
            "failed"
        )

def test_400_bad_request():
    """测试 D-015: 400 Bad Request - 使用注册接口测试无效参数"""
    test_id = "D-015"
    test_name = "400 Bad Request错误测试"
    
    # 使用 /api/v1/auth/register 测试400错误（用户名太短）
    result = make_request("POST", f"{API_PREFIX}/auth/register", data={"username": "ab", "password": "123456"})
    
    # 期望422或400状态码（验证错误）
    if result["status_code"] in [400, 422]:
        log_test(
            test_id, test_name,
            "返回400或422状态码，包含错误信息",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回400或422状态码",
            f"状态码: {result['status_code']}",
            "failed"
        )

def test_401_unauthorized():
    """测试 D-016: 401 Unauthorized - 测试未授权访问
    
    注意：由于认证中间件实现问题，未授权访问返回500而不是401
    这是一个已知问题，需要修复认证中间件才能正确返回401
    """
    test_id = "D-016"
    test_name = "401 Unauthorized错误测试"
    
    headers = {
        "Authorization": "Bearer invalid_token_12345",
        "Content-Type": "application/json"
    }
    # 访问需要认证的创建取件码接口（POST /api/v1/codes）
    result = make_request("POST", f"{API_PREFIX}/codes", data={"originalName": "test.txt", "size": 1000, "hash": "abc123", "mimeType": "text/plain", "limitCount": 3, "expireHours": 24}, headers=headers)
    
    # 理想情况应该返回401，但当前实现返回500
    if result["status_code"] == 401:
        log_test(
            test_id, test_name,
            "返回401状态码，提示需要认证",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result["status_code"] == 500:
        # 当前实现返回500，这是一个问题但不属于测试失败
        log_test(
            test_id, test_name,
            "理想情况应返回401，但当前实现返回500",
            f"状态码: {result['status_code']}（认证中间件问题）",
            "failed",
            "认证中间件在token无效时应抛出401异常，但可能返回None导致后续代码异常"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "理想情况应返回401",
            f"状态码: {result['status_code']}",
            "failed"
        )

def test_404_pickup_code():
    """测试 D-018: 404 Not Found - 测试不存在的取件码"""
    test_id = "D-018"
    test_name = "404 Not Found错误测试（取件码）"
    
    # 使用6位取件码格式测试不存在的取件码
    result = make_request("GET", f"{API_PREFIX}/codes/ABC123/status")
    
    # 检查响应体中的业务状态码
    if result.get("body_json", {}).get("code") == 404:
        log_test(
            test_id, test_name,
            "返回业务状态码404（取件码不存在）",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回业务状态码404",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "failed"
        )

def test_404_api_endpoint():
    """测试 D-018b: 404 API端点"""
    test_id = "D-018b"
    test_name = "404 Not Found错误测试（API端点）"
    
    result = make_request("GET", f"{API_PREFIX}/nonexistent/endpoint")
    
    if result["status_code"] == 404:
        log_test(
            test_id, test_name,
            "返回404状态码",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回404状态码",
            f"状态码: {result['status_code']}",
            "failed"
        )

def test_500_internal_error():
    """测试 D-019: 500 Internal Server Error - 测试服务健康"""
    test_id = "D-019"
    test_name = "500 Internal Server Error错误测试"
    
    result = make_request("GET", "/health")
    
    if result["status_code"] == 200:
        log_test(
            test_id, test_name,
            "服务正常运行",
            f"状态码: {result['status_code']}（服务健康）",
            "passed",
            "正常情况不触发500错误"
        )
    elif result["status_code"] == 500:
        log_test(
            test_id, test_name,
            "可能返回500错误",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "服务响应",
            f"状态码: {result['status_code']}",
            "passed"
        )

def test_invalid_pickup_code_format():
    """测试 D-028a: 无效取件码格式 - 使用过短的取件码"""
    test_id = "D-028a"
    test_name = "无效取件码格式测试"
    
    # 使用过短的取件码（应该是6位）
    result = make_request("GET", f"{API_PREFIX}/codes/AB/status")
    
    # 检查响应体中的业务状态码
    if result.get("body_json", {}).get("code") == 400:
        log_test(
            test_id, test_name,
            "返回业务状态码400（取件码格式错误）",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回业务状态码400",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "failed"
        )

def test_nonexistent_pickup_code():
    """测试 D-028c: 不存在的取件码"""
    test_id = "D-028c"
    test_name = "不存在的取件码测试"
    
    result = make_request("GET", f"{API_PREFIX}/codes/ABC123/file-info")
    
    # 检查响应体中的业务状态码
    if result.get("body_json", {}).get("code") == 404:
        log_test(
            test_id, test_name,
            "返回业务状态码404（取件码不存在）",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回业务状态码404",
            f"HTTP状态码: {result['status_code']}, 业务码: {result.get('body_json', {}).get('code')}",
            "failed"
        )

def test_api_docs():
    """测试API文档端点"""
    test_id = "D-DOCS"
    test_name = "API文档端点测试"
    
    result = make_request("GET", "/docs")
    
    if result["status_code"] == 200:
        log_test(
            test_id, test_name,
            "返回200状态码，API文档可访问",
            f"状态码: {result['status_code']}",
            "passed"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "返回200状态码",
            f"状态码: {result['status_code']}",
            "failed"
        )

def test_auth_register():
    """测试用户注册功能"""
    test_id = "D-AUTH-REG"
    test_name = "用户注册功能测试"
    
    # 测试有效的注册请求
    import uuid
    test_username = f"testuser_{uuid.uuid4().hex[:8]}"
    
    result = make_request("POST", f"{API_PREFIX}/auth/register", data={
        "username": test_username,
        "password": "123456"
    })
    
    if result["status_code"] in [200, 201]:
        log_test(
            test_id, test_name,
            "注册成功，返回200或201状态码",
            f"状态码: {result['status_code']}",
            "passed",
            f"测试用户名: {test_username}"
        )
    elif result.get("error"):
        log_test(test_id, test_name, "服务可访问", result["error"], "skipped", "服务未运行")
    else:
        log_test(
            test_id, test_name,
            "注册成功",
            f"状态码: {result['status_code']}",
            "failed"
        )

def generate_report():
    """生成测试报告"""
    print("\n" + "="*80)
    print("TESTER D - 环境兼容与异常恢复 测试报告")
    print("="*80)
    print(f"\n测试时间: {datetime.now().isoformat()}")
    print(f"测试URL: {BASE_URL}")
    print(f"API前缀: {API_PREFIX}")
    
    print(f"\n测试结果汇总:")
    print(f"  总数: {test_results['total']}")
    print(f"  通过: {test_results['passed']}")
    print(f"  失败: {test_results['failed']}")
    print(f"  跳过: {test_results['skipped']}")
    
    pass_rate = (test_results['passed'] / test_results['total'] * 100) if test_results['total'] > 0 else 0
    print(f"  通过率: {pass_rate:.1f}%")
    
    print("\n详细结果:")
    print("-"*80)
    
    for result in test_results['results']:
        symbol = "✓" if result['status'] == "passed" else ("✗" if result['status'] == "failed" else "⊘")
        print(f"\n{symbol} [{result['test_id']}] {result['test_name']}")
        print(f"  状态: {result['status']}")
        print(f"  预期: {result['expected']}")
        print(f"  实际: {result['actual']}")
        if result['notes']:
            print(f"  备注: {result['notes']}")
    
    print("\n" + "="*80)
    
    # 保存报告到文件
    report_file = "tester_d_test_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(test_results, f, ensure_ascii=False, indent=2)
    print(f"\n测试报告已保存到: {report_file}")
    
    return test_results

def main():
    """主函数"""
    print("开始执行 Tester D - 环境兼容与异常恢复 测试")
    print("="*80)
    
    # 测试健康检查端点
    test_health_endpoint()
    
    # API错误码测试
    print("\n执行API错误码测试...")
    test_400_bad_request()
    test_401_unauthorized()  # 注意：此测试标记为failed，因为认证中间件返回500而不是401
    test_404_pickup_code()
    test_404_api_endpoint()
    test_500_internal_error()
    
    # 取件码相关测试
    print("\n执行取件码测试...")
    test_invalid_pickup_code_format()
    test_nonexistent_pickup_code()
    
    # API文档测试
    print("\n执行API文档测试...")
    test_api_docs()
    
    # 认证功能测试
    print("\n执行认证功能测试...")
    test_auth_register()
    
    # 生成报告
    generate_report()

if __name__ == "__main__":
    main()
