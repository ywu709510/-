"""
书搜搜 - 配置文件
所有可配置的参数都在这里，方便统一管理
"""

import os

# ============================================
# DeepSeek AI 配置
# ============================================
# 在下方填入你的 DeepSeek API Key
# 获取方式：https://platform.deepseek.com/
DEEPSEEK_API_KEY = ""  # ← 请替换为你的真实Key
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash"

# ============================================
# 网站基本配置
# ============================================
SITE_NAME = {
    "zh": "书搜搜",
    "en": "BookSearch"
}
SITE_DESCRIPTION = {
    "zh": "AI智能图书推荐平台",
    "en": "AI-Powered Book Recommendation Platform"
}

# 默认语言
DEFAULT_LANGUAGE = "zh"  # zh = 中文, en = English

# ============================================
# 数据库配置
# ============================================
# 开发阶段使用SQLite
DATABASE_URL = "sqlite:///./shusousou/database/database.db"

# ============================================
# 邮件服务配置
# ============================================
# 用于发送验证邮件和通知邮件
# 以QQ邮箱为例（需要开启SMTP服务）
MAIL_SERVER = "smtp.qq.com"
MAIL_PORT = 587
MAIL_USERNAME = "2024604689@qq.com"  # ← 请替换为你的邮箱
MAIL_PASSWORD = ""  # ← 请替换为你的SMTP授权码
MAIL_FROM = "2024604689@qq.com"      # ← 请替换为发件人邮箱

# ============================================
# 服务器配置
# ============================================
HOST = "0.0.0.0"
PORT = 8000
DEBUG = True

# ============================================
# 图书馆模拟API配置
# ============================================
# 开发阶段使用模拟数据
LIBRARY_API_MODE = "mock"  # "mock" = 模拟数据, "real" = 真实API
LIBRARY_API_URL = "http://localhost:8000/api/library"  # 模拟API地址

