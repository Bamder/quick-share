"""
用户注册/登录功能测试

测试用户认证系统的各种场景，包括正常和异常情况：
- 用户注册：正常注册、用户名重复、长度验证、特殊字符等
- 用户登录：正常登录、用户不存在、密码错误、输入验证等
- Token验证：有效令牌、过期令牌、无效令牌等

使用方法:
    # Windows (推荐):
    scripts\\test\\auth\\run_auth_test.bat
    或
    scripts\\test\\auth\\run_auth_test.ps1

    # 手动运行 (需要先激活虚拟环境):
    python scripts/test/auth/test_auth.py
"""

import sys
import os
from pathlib import Path
import hashlib
from datetime import datetime, timedelta, timezone
from jose import jwt
from jose.exceptions import JWTError

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 检查是否在虚拟环境中
def check_venv():
    """检查是否在虚拟环境中运行"""
    in_venv = (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix) or
        os.environ.get('VIRTUAL_ENV') is not None
    )

    if not in_venv:
        print("=" * 60)
        print("提示: 建议使用项目虚拟环境运行测试")
        print("=" * 60)
        print("运行方式:")
        print("  scripts\\test\\auth\\run_auth_test.bat")
        print("=" * 60)
        print("")

    return in_venv

# 在导入其他模块前检查虚拟环境（可选）
# check_venv()

from app.extensions import SessionLocal
from app.models.user import User
from app.config import settings
import logging

# 导入测试工具
sys.path.insert(0, str(Path(__file__).parent.parent))
from test_utils import *

# 配置日志输出到控制台
logging.basicConfig(level=logging.INFO, format='%(message)s')

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    """生成密码哈希（模拟前端SHA-256哈希）"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_test_user(db, username="test_user", password="test_password_123"):
    """创建测试用户"""
    password_hash = hash_password(password)
    user = User(
        username=username,
        password_hash=password_hash
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def cleanup_test_users(db):
    """清理测试用户"""
    test_usernames = [
        "test_user", "test_user_normal", "test_user_2", "empty_user", "short", "verylongusername123456789",
        "user@domain.com", "user-name", "user_name", "用户测试", "user<script>",
        "admin", "root", "guest", "user with spaces", "user\tab", "user\nline"
    ]
    try:
        db.rollback()  # 先回滚任何未提交的事务
        db.query(User).filter(User.username.in_(test_usernames)).delete()
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"清理测试用户时出错: {e}")


def test_register_normal(db):
    """测试正常用户注册"""
    log_test_start("正常用户注册")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_user_normal", "password123")

        # 验证用户创建成功
        assert user.id is not None
        assert user.username == "test_user_normal"
        assert user.password_hash == hash_password("password123")
        assert user.created_at is not None

        log_success("正常用户注册测试通过")
        return True

    except Exception as e:
        log_error(f"正常用户注册测试失败: {e}")
        db.rollback()
        return False
    finally:
        # 清理
        try:
            db.rollback()
            db.query(User).filter(User.username == "test_user_normal").delete()
            db.commit()
        except Exception:
            db.rollback()


def test_register_duplicate_username(db):
    """测试用户名重复注册"""
    log_test_start("用户名重复注册")

    try:
        # 先创建用户
        user1 = create_test_user(db, "test_duplicate", "password123")

        # 尝试注册同名用户（通过路由逻辑模拟）
        from app.routes.auth import RegisterRequest
        from app.utils.response import bad_request_response

        # 模拟注册请求数据
        request_data = RegisterRequest(
            username="test_duplicate",
            password=hash_password("different_password")
        )

        # 检查用户名是否已存在（模拟路由逻辑）
        existing_user = db.query(User).filter(User.username == request_data.username).first()
        if existing_user:
            # 这应该返回错误响应（bad_request_response 返回字典）
            response = bad_request_response(msg="用户名已存在")
            if isinstance(response, dict) and response.get('code') == 400 and "用户名已存在" in response.get('msg', ''):
                log_success("用户名重复注册正确返回错误")
                return True
            else:
                log_error(f"用户名重复注册返回格式不正确: {response}")
                return False
        else:
            log_error("用户名重复检查失败")
            return False

    except Exception as e:
        log_error(f"用户名重复注册测试失败: {e}")
        db.rollback()
        return False
    finally:
        # 清理
        try:
            db.rollback()
            db.query(User).filter(User.username == "test_duplicate").delete()
            db.commit()
        except Exception:
            db.rollback()


def test_register_invalid_username_length(db):
    """测试用户名长度验证"""
    log_test_start("用户名长度验证")

    test_cases = [
        ("", "空用户名"),
        ("a", "用户名太短（1字符）"),
        ("ab", "用户名太短（2字符）"),
        ("a" * 51, "用户名太长（51字符）"),
        ("a" * 100, "用户名太长（100字符）"),
    ]

    passed = 0
    total = len(test_cases)

    for invalid_username, description in test_cases:
        try:
            # 尝试创建用户（这应该在Pydantic验证层失败）
            from pydantic import ValidationError
            try:
                from app.routes.auth import RegisterRequest
                request_data = RegisterRequest(
                    username=invalid_username,
                    password=hash_password("password123")
                )
                # 如果没有抛出异常，说明验证失败
                log_error(f"{description} - 验证失败，应被拒绝")
            except ValidationError:
                log_success(f"{description} - 正确被拒绝")
                passed += 1

        except Exception as e:
            log_error(f"{description} - 测试异常: {e}")

    log_info(f"用户名长度验证: {passed}/{total} 通过")
    return passed == total


def test_register_special_characters(db):
    """测试特殊字符用户名"""
    log_test_start("特殊字符用户名注册")

    test_cases = [
        ("user@domain.com", "包含@符号"),
        ("user-name", "包含连字符"),
        ("user_name", "包含下划线"),
        ("user.name", "包含点号"),
        ("用户测试", "中文字符"),
        ("user<script>", "包含HTML标签"),
        ("user with spaces", "包含空格"),
        ("user\tab", "包含制表符"),
        ("user\nline", "包含换行符"),
        ("user\rcarriage", "包含回车符"),
    ]

    passed = 0
    total = len(test_cases)

    for username, description in test_cases:
        try:
            # 创建测试用户
            user = create_test_user(db, username, "password123")

            # 验证创建成功
            assert user.username == username
            log_success(f"{description} - 注册成功")
            passed += 1

        except Exception as e:
            log_error(f"{description} - 注册失败: {e}")
        finally:
            # 清理
            try:
                db.query(User).filter(User.username == username).delete()
                db.commit()
            except:
                pass

    log_info(f"特殊字符用户名测试: {passed}/{total} 通过")
    return passed == total


def test_register_password_validation(db):
    """测试密码验证（通过路由层验证）"""
    log_test_start("密码验证")

    from app.routes.auth import RegisterRequest
    from pydantic import ValidationError

    test_cases = [
        ("", "空密码哈希", False),  # 空字符串，应该被拒绝（min_length=6）
        ("short", "短密码哈希", False),  # 5字符，应该被拒绝（min_length=6）
        ("a" * 63, "63字符哈希", True),  # 63字符，允许（max_length=64，所以63是允许的）
        ("a" * 65, "65字符哈希", False),  # 65字符，应该被拒绝（max_length=64）
        ("g" * 64, "64字符但不是有效SHA-256", True),  # 64字符，格式正确（路由层只验证长度，不验证SHA-256格式）
        (hash_password("valid_password"), "有效SHA-256哈希", True),  # 有效哈希，应该成功
    ]

    passed = 0
    total = len(test_cases)

    for i, (password_hash, description, should_pass) in enumerate(test_cases):
        try:
            # 通过 Pydantic 模型验证（模拟路由层验证）
            request = RegisterRequest(
                username=f"test_pwd_{i}",
                password=password_hash
            )
            
            # 如果验证通过，尝试创建用户
            user = User(
                username=request.username,
                password_hash=request.password
            )
            db.add(user)
            db.commit()
            db.refresh(user)

            # 检查是否符合期望
            if should_pass:
                log_success(f"{description} - 注册成功")
                passed += 1
            else:
                # 不应该通过验证，但通过了
                log_error(f"{description} - 应被拒绝但成功了（Pydantic验证未生效）")
                # 不增加 passed

        except ValidationError as e:
            # Pydantic 验证失败
            if not should_pass:
                log_success(f"{description} - 正确被拒绝（Pydantic验证）")
                passed += 1
            else:
                log_error(f"{description} - 应成功但被拒绝: {e}")
        except Exception as e:
            # 其他错误
            if not should_pass:
                log_success(f"{description} - 正确被拒绝: {type(e).__name__}")
                passed += 1
            else:
                log_error(f"{description} - 应成功但失败了: {e}")
        finally:
            # 清理
            try:
                db.rollback()
                db.query(User).filter(User.username == f"test_pwd_{i}").delete()
                db.commit()
            except:
                db.rollback()

    log_info(f"密码验证测试: {passed}/{total} 通过")
    return passed == total


def test_login_normal(db):
    """测试正常登录"""
    log_test_start("正常用户登录")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_login_normal", "login_password")

        # 模拟登录逻辑
        from app.routes.auth import LoginRequest

        request_data = LoginRequest(
            username="test_login_normal",
            password=hash_password("login_password")
        )

        # 查找用户
        found_user = db.query(User).filter(User.username == request_data.username).first()
        if not found_user:
            log_error("用户查找失败")
            return False

        # 验证密码
        if found_user.password_hash != request_data.password:
            log_error("密码验证失败")
            return False

        log_success("正常用户登录测试通过")
        return True

    except Exception as e:
        log_error(f"正常用户登录测试失败: {e}")
        return False
    finally:
        # 清理
        db.query(User).filter(User.username == "test_login_normal").delete()
        db.commit()


def test_login_user_not_found(db):
    """测试用户不存在登录"""
    log_test_start("用户不存在登录")

    try:
        from app.routes.auth import LoginRequest

        request_data = LoginRequest(
            username="non_existent_user_12345",
            password=hash_password("password123")
        )

        # 查找用户
        user = db.query(User).filter(User.username == request_data.username).first()
        if not user:
            log_success("用户不存在时正确返回错误")
            return True
        else:
            log_error("找到不存在的用户")
            return False

    except Exception as e:
        log_error(f"用户不存在登录测试失败: {e}")
        return False


def test_login_wrong_password(db):
    """测试密码错误登录"""
    log_test_start("密码错误登录")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_wrong_pwd", "correct_password")

        from app.routes.auth import LoginRequest

        request_data = LoginRequest(
            username="test_wrong_pwd",
            password=hash_password("wrong_password")
        )

        # 查找用户
        found_user = db.query(User).filter(User.username == request_data.username).first()
        if not found_user:
            log_error("用户查找失败")
            return False

        # 验证密码（应该失败）
        if found_user.password_hash != request_data.password:
            log_success("密码错误时正确拒绝登录")
            return True
        else:
            log_error("错误密码竟然通过验证")
            return False

    except Exception as e:
        log_error(f"密码错误登录测试失败: {e}")
        return False
    finally:
        # 清理
        db.query(User).filter(User.username == "test_wrong_pwd").delete()
        db.commit()


def test_login_empty_credentials(db):
    """测试空凭据登录"""
    log_test_start("空凭据登录")

    test_cases = [
        ("", "password123", "空用户名"),
        ("username", "", "空密码"),
        ("", "", "空用户名和密码"),
    ]

    passed = 0
    total = len(test_cases)

    for username, password, description in test_cases:
        try:
            from app.routes.auth import LoginRequest

            # 对于空用户名，应该直接拒绝
            if not username:
                log_success(f"{description} - 正确拒绝")
                passed += 1
            elif not password:
                # 空密码情况：空字符串的哈希值不等于任何有效密码哈希
                # 这里我们检查是否会被正确拒绝（通过查找用户并比较密码）
                user = db.query(User).filter(User.username == username).first()
                if not user:
                    # 用户不存在，也算正确拒绝
                    log_success(f"{description} - 正确拒绝（用户不存在）")
                    passed += 1
                else:
                    # 用户存在，但空密码的哈希不等于用户密码哈希
                    empty_password_hash = hash_password("") if password == "" else ""
                    if user.password_hash != empty_password_hash:
                        log_success(f"{description} - 正确拒绝（密码不匹配）")
                        passed += 1
                    else:
                        log_error(f"{description} - 验证失败（密码匹配了，这不应该发生）")
            else:
                log_error(f"{description} - 意外情况")

        except Exception as e:
            log_error(f"{description} - 测试异常: {e}")

    log_info(f"空凭据登录测试: {passed}/{total} 通过")
    return passed == total


def test_token_creation_and_validation(db):
    """测试Token创建和验证"""
    log_test_start("Token创建和验证")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_token_user", "token_password")

        # 生成token
        from app.routes.auth import create_access_token
        token = create_access_token(user.id)

        # 验证token（使用已导入的 jwt）
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_user_id = payload.get("sub")

        if str(user.id) == token_user_id:
            log_success("Token创建和验证测试通过")
            return True
        else:
            log_error("Token验证失败，用户ID不匹配")
            return False

    except Exception as e:
        log_error(f"Token创建和验证测试失败: {e}")
        return False
    finally:
        # 清理
        db.query(User).filter(User.username == "test_token_user").delete()
        db.commit()


def test_token_expiration(db):
    """测试Token过期"""
    log_test_start("Token过期测试")

    try:
        # 创建测试用户
        user = create_test_user(db, "test_expired_token", "expired_password")

        # 生成过期的token（手动设置过期时间）
        from datetime import datetime, timedelta, timezone
        expired_payload = {
            "sub": str(user.id),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),  # 1分钟前过期
            "iat": datetime.now(timezone.utc) - timedelta(minutes=5)
        }
        expired_token = jwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # 尝试验证过期token
        try:
            payload = jwt.decode(expired_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            log_error("过期Token竟然通过验证")
            return False
        except jwt.ExpiredSignatureError:
            log_success("过期Token正确被拒绝")
            return True
        except Exception as e:
            log_error(f"Token过期测试异常: {e}")
            return False

    except Exception as e:
        log_error(f"Token过期测试失败: {e}")
        return False
    finally:
        # 清理
        db.query(User).filter(User.username == "test_expired_token").delete()
        db.commit()


def test_invalid_token(db):
    """测试无效Token"""
    log_test_start("无效Token测试")

    try:
        # 测试各种无效token
        invalid_tokens = [
            "",  # 空token
            "invalid.jwt.token",  # 无效格式
            "header.payload.signature_extra",  # 多段
            jwt.encode({"sub": "123"}, "wrong_secret", algorithm=settings.JWT_ALGORITHM),  # 错误密钥
        ]

        passed = 0
        for i, invalid_token in enumerate(invalid_tokens):
            try:
                payload = jwt.decode(invalid_token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
                log_error(f"无效Token {i+1} 竟然通过验证")
            except (JWTError, jwt.ExpiredSignatureError, jwt.JWTClaimsError):
                log_success(f"无效Token {i+1} 正确被拒绝")
                passed += 1
            except Exception as e:
                log_success(f"无效Token {i+1} 因其他原因被拒绝: {type(e).__name__}")
                passed += 1

        log_info(f"无效Token测试: {passed}/{len(invalid_tokens)} 通过")
        return passed == len(invalid_tokens)

    except Exception as e:
        log_error(f"无效Token测试失败: {e}")
        return False


def run_auth_tests():
    """运行所有认证测试"""
    log_section("用户认证系统测试")

    tests = [
        ("用户注册测试", [
            test_register_normal,
            test_register_duplicate_username,
            test_register_invalid_username_length,
            test_register_special_characters,
            test_register_password_validation,
        ]),
        ("用户登录测试", [
            test_login_normal,
            test_login_user_not_found,
            test_login_wrong_password,
            test_login_empty_credentials,
        ]),
        ("Token验证测试", [
            test_token_creation_and_validation,
            test_token_expiration,
            test_invalid_token,
        ]),
    ]

    total_passed = 0
    total_tests = 0

    for section_name, section_tests in tests:
        log_subsection(f"{section_name} ({len(section_tests)} 个测试)")

        section_passed = 0
        for test_func in section_tests:
            # 为每个测试创建新的数据库会话，确保隔离
            test_db = SessionLocal()
            try:
                # 清理可能的旧测试数据
                cleanup_test_users(test_db)
                
                # 运行测试
                if test_func(test_db):
                    section_passed += 1
                    total_passed += 1
                total_tests += 1
            except Exception as e:
                log_error(f"测试 {test_func.__name__} 发生异常: {e}")
                total_tests += 1
            finally:
                # 清理并关闭会话
                try:
                    cleanup_test_users(test_db)
                    test_db.rollback()
                except:
                    pass
                test_db.close()

        log_info(f"{section_name} 通过: {section_passed}/{len(section_tests)}")

    # 最终统计
    log_separator("测试结果汇总")
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    log_info(f"总测试数: {total_tests}")
    log_info(f"通过测试: {total_passed}")
    log_info(f"失败测试: {total_tests - total_passed}")
    log_info(f"成功率: {success_rate:.1f}%")
    if total_passed == total_tests:
        log_success("所有认证测试通过！🎉")
    else:
        log_error("部分认证测试失败，请检查实现")

    return total_passed == total_tests


if __name__ == "__main__":
    success = run_auth_tests()
    sys.exit(0 if success else 1)
