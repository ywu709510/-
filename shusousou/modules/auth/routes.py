"""
书搜搜 - 用户认证模块
负责：注册、登录、退出、邮箱验证
"""

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import hashlib
import os

from ...database.models import User
from jinja2 import Environment, FileSystemLoader, ChoiceLoader

router = APIRouter(prefix="/auth", tags=["auth"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
auth_templates = os.path.join(BASE_DIR, "modules", "auth", "templates")
global_templates = os.path.join(BASE_DIR, "templates")

loader = ChoiceLoader([
    FileSystemLoader(auth_templates),
    FileSystemLoader(global_templates)
])
env = Environment(loader=loader, cache_size=0)
templates = Jinja2Templates(env=env)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


from ...utils import get_db, get_current_user
from datetime import datetime


# ============================================
# 登录/注册合并页面
# ============================================
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """显示登录/注册页面"""
    lang = request.cookies.get("language", "zh")
    current_user = get_current_user(request)
    return templates.TemplateResponse(request, "login_register.html", {
        "language": lang,
        "current_user": current_user,
        "login_error": None,
        "register_error": None,
        "register_success": None,
        "login_success": None,
        "mode": "login"
    })


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """显示注册页面"""
    lang = request.cookies.get("language", "zh")
    current_user = get_current_user(request)
    return templates.TemplateResponse(request, "login_register.html", {
        "language": lang,
        "current_user": current_user,
        "login_error": None,
        "register_error": None,
        "register_success": None,
        "login_success": None,
        "mode": "register"
    })


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    """处理登录"""
    lang = request.cookies.get("language", "zh")
    current_user = get_current_user(request)
    
    with get_db() as session:
        user = session.query(User).filter(User.email == email).first()
        
        if not user:
            msg = "该邮箱未注册" if lang == "zh" else "Email not registered"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": msg, "register_error": None,
                "register_success": None, "login_success": None,
                "mode": "login"
            })
        
        if user.password_hash != hash_password(password):
            msg = "密码错误" if lang == "zh" else "Incorrect password"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": msg, "register_error": None,
                "register_success": None, "login_success": None,
                "mode": "login"
            })
        
        if not user.is_verified:
            msg = "请先验证邮箱再登录" if lang == "zh" else "Please verify your email first"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": msg, "register_error": None,
                "register_success": None, "login_success": None,
                "mode": "login"
            })
    
    # 登录成功
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id))
    return response


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    verify_code: str = Form(...)
):
    """处理注册"""
    lang = request.cookies.get("language", "zh")
    current_user = get_current_user(request)
    
    if len(password) < 6:
        msg = "密码太短，至少6位" if lang == "zh" else "Password too short"
        return templates.TemplateResponse(request, "login_register.html", {
            "language": lang, "current_user": current_user,
            "login_error": None, "register_error": msg,
            "register_success": None, "login_success": None,
        "mode": "login"
        })
    
    with get_db() as session:
        existing = session.query(User).filter(
            (User.email == email) | (User.username == username)
        ).first()
        if existing and existing.password_hash:
            msg = "用户名或邮箱已被注册" if lang == "zh" else "Username or email already exists"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": None, "register_error": msg,
                "register_success": None, "login_success": None,
                "mode": "register"
            })
        
        # 查找临时用户（通过send-code-ajax创建的）
        temp_user = session.query(User).filter(User.email == email).first()
        if not temp_user:
            msg = "请先发送验证码" if lang == "zh" else "Please send verification code first"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": None, "register_error": msg,
                "register_success": None, "login_success": None,
                "mode": "register"
            })
        
        # 检查验证码是否过期
        if temp_user.verify_code_expire and datetime.now() > temp_user.verify_code_expire:
            msg = "验证码已过期，请重新获取" if lang == "zh" else "Verification code expired"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": None, "register_error": msg,
                "register_success": None, "login_success": None,
                "mode": "register"
            })
        
        # 检查验证码
        if temp_user.verify_code != verify_code:
            msg = "验证码错误" if lang == "zh" else "Incorrect verification code"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": None, "register_error": msg,
                "register_success": None, "login_success": None,
                "mode": "register"
            })
        
        # 更新临时用户为真实用户
        temp_user.username = username
        temp_user.password_hash = hash_password(password)
        temp_user.is_verified = True
        temp_user.verify_code = None
        temp_user.verify_code_expire = None
        session.commit()
    
    msg = "注册成功！请登录" if lang == "zh" else "Registration successful! Please login"
    return templates.TemplateResponse(request, "login_register.html", {
        "language": lang, "current_user": current_user,
        "login_error": None, "register_error": None,
        "register_success": msg, "login_success": None,
        "mode": "register"
    })


# ============================================
# 邮箱验证
# ============================================
@router.get("/verify")
async def verify_email(request: Request, token: str = ""):
    """验证邮箱"""
    lang = request.cookies.get("language", "zh")
    current_user = get_current_user(request)
    
    if not token:
        msg = "无效的验证链接" if lang == "zh" else "Invalid verification link"
        return templates.TemplateResponse(request, "login_register.html", {
            "language": lang, "current_user": current_user,
            "login_error": msg, "register_error": None,
            "register_success": None, "login_success": None,
        "mode": "login"
        })
    
    with get_db() as session:
        user = session.query(User).filter(User.verify_token == token).first()
        if not user:
            msg = "验证链接已失效，请重新注册" if lang == "zh" else "Invalid or expired verification link"
            return templates.TemplateResponse(request, "login_register.html", {
                "language": lang, "current_user": current_user,
                "login_error": msg, "register_error": None,
                "register_success": None, "login_success": None,
                "mode": "login"
            })
        
        user.is_verified = True
        user.verify_token = None
        session.commit()
    
    msg = "邮箱验证成功！请登录" if lang == "zh" else "Email verified! Please login"
    return templates.TemplateResponse(request, "login_register.html", {
        "language": lang, "current_user": current_user,
        "login_error": None, "register_error": None,
        "register_success": msg, "login_success": None,
        "mode": "register"
    })


# ============================================
# 退出
# ============================================
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_id")
    return response


# ============================================
# 发送验证码（Ajax，不刷新页面）
# ============================================
from fastapi.responses import JSONResponse
import random

@router.post("/send-code-ajax")
async def send_verify_code_ajax(request: Request, email: str = Form(...)):
    """发送邮箱验证码（异步，不刷新页面）"""
    from datetime import timedelta
    
    code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    expire_time = datetime.now() + timedelta(minutes=5)
    
    with get_db() as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing and existing.is_verified:
            return JSONResponse({"success": False, "message": "该邮箱已注册"})
        
        temp_user = session.query(User).filter(User.email == email).first()
        if not temp_user:
            temp_user = User(
                username=f"_temp_{email.replace('@','_').replace('.','_')}",
                email=email,
                password_hash="",
                is_verified=False,
                verify_code=code,
                verify_code_expire=expire_time
            )
            session.add(temp_user)
        else:
            temp_user.verify_code = code
            temp_user.verify_code_expire = expire_time
        session.commit()
    
    from ...mailer import send_email
    subject = "书搜搜 - 注册验证码 / Registration Code"
    body = f"""
    <div>
        <h2>书搜搜 BookSearch</h2>
        <p>你的注册验证码是：</p>
        <p style="font-size:36px;font-weight:bold;letter-spacing:8px;">{code}</p>
        <p>验证码有效期为5分钟。</p>
    </div>
    """
    send_email(email, subject, body)
    
    return JSONResponse({"success": True, "message": "验证码已发送"})

