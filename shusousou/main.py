"""
书搜搜 - 主入口文件
启动整个网站服务
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os

from .config import HOST, PORT, DEBUG, SITE_NAME, DEFAULT_LANGUAGE
from .database.models import init_database

# 获取项目根目录 (shusousou 即 D:\shusousou\shusousou)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 创建FastAPI应用
app = FastAPI(title="书搜搜 / BookSearch")

# 挂载静态文件
static_dir = os.path.join(BASE_DIR, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

from .modules.auth.routes import router as auth_router
app.include_router(auth_router)
from .modules.search.routes import router as search_router
app.include_router(search_router)
from .modules.forum.routes import router as forum_router
app.include_router(forum_router)
from .modules.exchange.routes import router as exchange_router
from .modules.exchange.routes import run_match_check
app.include_router(exchange_router)
from .modules.profile.routes import router as profile_router
app.include_router(profile_router)

# 启动定时匹配扫描（每60秒一次）
import threading
def match_loop():
    import time
    while True:
        time.sleep(60)
        try:
            run_match_check()
        except Exception as e:
            print(f"[Scheduler] 匹配出错: {e}")

thread = threading.Thread(target=match_loop, daemon=True)
thread.start()

# 配置模板
templates_dir = os.path.join(BASE_DIR, "templates")
from jinja2 import Environment, FileSystemLoader
jinja_env = Environment(loader=FileSystemLoader(templates_dir), cache_size=0)
templates = Jinja2Templates(env=jinja_env)


# ============================================
# 首页
# ============================================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """网站首页"""
    # 获取语言设置
    lang = request.cookies.get("language", DEFAULT_LANGUAGE)
    site_name = SITE_NAME.get(lang, SITE_NAME["zh"])
    
    # 获取当前用户
    from .utils import get_current_user
    current_user = get_current_user(request)
    
    return templates.TemplateResponse(
        request, "index.html", {
        "site_name": site_name,
        "language": lang,
        "current_user": current_user
    })


# ============================================
# 启动事件
# ============================================
@app.on_event("startup")
async def startup():
    """启动时初始化数据库"""
    init_database()
    print("书搜搜服务已启动！")
    print(f"访问地址：http://localhost:{PORT}")


# ============================================
# 程序入口
# ============================================
if __name__ == "__main__":
    uvicorn.run(
        "shusousou.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG
    )
