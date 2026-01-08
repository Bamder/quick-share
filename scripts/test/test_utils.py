"""
测试工具模块 - 提供统一的格式化和工具函数

所有测试脚本都可以导入此模块使用统一的格式化功能。
提供美观的视觉效果和一致的日志格式。
"""

import logging
import sys

logger = logging.getLogger(__name__)

# 定义颜色代码（如果终端支持）
class Colors:
    GREEN = '\033[92m'    # 成功 - 绿色
    RED = '\033[91m'      # 错误 - 红色
    YELLOW = '\033[93m'   # 警告 - 黄色
    BLUE = '\033[94m'     # 信息 - 蓝色
    CYAN = '\033[96m'     # 章节标题 - 青色
    MAGENTA = '\033[95m'  # 分隔符 - 品红
    BOLD = '\033[1m'      # 加粗
    RESET = '\033[0m'     # 重置

# 检查终端是否支持颜色
def _supports_color():
    """检查终端是否支持ANSI颜色"""
    if sys.platform.startswith('win'):
        # Windows 10 version 1511+ 支持ANSI颜色
        try:
            import os
            return os.environ.get('TERM') == 'xterm-256color' or 'ANSICON' in os.environ
        except:
            return False
    else:
        # Unix-like系统通常支持
        return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

SUPPORTS_COLOR = _supports_color()

def _colorize(text, color):
    """为文本添加颜色（如果支持）"""
    if SUPPORTS_COLOR:
        return f"{color}{text}{Colors.RESET}"
    return text


def log_separator(title="", char="═", length=70):
    """统一的日志分隔符，确保格式一致性

    Args:
        title: 分隔符标题，如果为空则只显示分隔线
        char: 分隔符字符，默认为'═' (双线)
        length: 分隔符总长度，默认为70
    """
    print()  # 使用print添加换行，避免logger的格式问题

    if title:
        # 计算标题长度，确保居中
        title_line = f" {title} "
        padding = (length - len(title_line)) // 2
        left_pad = char * padding
        right_pad = char * (length - padding - len(title_line))

        # 为标题添加颜色
        colored_title = _colorize(title_line, Colors.CYAN + Colors.BOLD)
        separator = f"{left_pad}{colored_title}{right_pad}"
        logger.info(separator)
    else:
        # 为分隔符添加颜色
        colored_separator = _colorize(char * length, Colors.MAGENTA)
        logger.info(colored_separator)

    print()  # 使用print添加换行


def log_section(title):
    """记录一个新的测试章节

    Args:
        title: 章节标题
    """
    log_separator(f"🔹 {title}", "═", 70)


def log_subsection(title):
    """记录一个子章节

    Args:
        title: 子章节标题
    """
    # 使用简单的格式，带颜色
    colored_title = _colorize(f"└── {title}", Colors.BLUE + Colors.BOLD)
    logger.info(colored_title)


def log_test_start(test_name):
    """记录测试开始

    Args:
        test_name: 测试名称
    """
    colored_name = _colorize(f"🧪 {test_name}", Colors.BLUE + Colors.BOLD)
    logger.info(f"开始执行: {colored_name}")


def log_test_step(step_num, description):
    """记录测试步骤

    Args:
        step_num: 步骤编号
        description: 步骤描述
    """
    colored_step = _colorize(f"{step_num:2d}", Colors.YELLOW)
    logger.info(f"步骤 {colored_step}: {description}")


def log_success(message):
    """记录成功消息

    Args:
        message: 成功消息
    """
    colored_message = _colorize(f"✅ {message}", Colors.GREEN + Colors.BOLD)
    logger.info(colored_message)


def log_error(message):
    """记录错误消息

    Args:
        message: 错误消息
    """
    colored_message = _colorize(f"❌ {message}", Colors.RED + Colors.BOLD)
    logger.error(colored_message)


def log_info(message):
    """记录信息消息

    Args:
        message: 信息消息
    """
    colored_message = _colorize(f"ℹ️  {message}", Colors.BLUE)
    logger.info(colored_message)


def log_warning(message):
    """记录警告消息

    Args:
        message: 警告消息
    """
    colored_message = _colorize(f"⚠️  {message}", Colors.YELLOW + Colors.BOLD)
    logger.warning(colored_message)


def log_progress(current, total, message=""):
    """记录进度信息

    Args:
        current: 当前进度
        total: 总进度
        message: 额外消息
    """
    percentage = (current / total * 100) if total > 0 else 0
    progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
    colored_progress = _colorize(f"[{progress_bar}]", Colors.GREEN)
    colored_percent = _colorize(f"{percentage:5.1f}%", Colors.CYAN + Colors.BOLD)

    progress_text = f"进度: {colored_progress} {colored_percent}"
    if message:
        progress_text += f" - {message}"

    logger.info(progress_text)


def format_test_result(passed, total, test_name=""):
    """格式化测试结果摘要

    Args:
        passed: 通过的测试数量
        total: 总测试数量
        test_name: 测试名称（可选）

    Returns:
        格式化的结果字符串
    """
    failed = total - passed
    success_rate = (passed / total * 100) if total > 0 else 0

    result = f"总计: {total} 个测试用例\n"
    result += f"通过: {passed} 个\n"
    result += f"失败: {failed} 个\n"
    result += f"成功率: {success_rate:.1f}%"

    return result
