"""
书搜搜 - 交换借阅模块
负责：发布图书、浏览可借列表、联系借书、挂需求、AI匹配
"""

from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
import json
import time
from pydantic import BaseModel

from jinja2 import Environment, FileSystemLoader, ChoiceLoader
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as DBSession
from datetime import datetime

from ...utils import get_current_user
from ...database.models import ExchangeBook, ExchangeMessage, ExchangeRequest, RequestMatch, User

router = APIRouter(prefix="/exchange", tags=["exchange"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
exchange_templates = os.path.join(BASE_DIR, "modules", "exchange", "templates")
global_templates = os.path.join(BASE_DIR, "templates")

loader = ChoiceLoader([
    FileSystemLoader(exchange_templates),
    FileSystemLoader(global_templates)
])
env = Environment(loader=loader, cache_size=0)
templates = Jinja2Templates(env=env)


# 全局引擎
_db_path = os.path.join(BASE_DIR, "database", "database.db")
_db_engine = create_engine(f"sqlite:///{_db_path}", connect_args={"check_same_thread": False})

def get_db():
    return DBSession(_db_engine)


def require_login(request: Request):
    """检查登录"""
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return user


# ============================================
# AI匹配函数
# ============================================
def ai_match_check(request_description, book_name, book_author, book_requirements):
    """让AI判断一本书是否匹配用户的需求"""
    prompt = f"""你是一个图书匹配助手。判断下面这本书是否匹配用户的需求。
    
用户需求：{request_description}

图书信息：
- 书名：{book_name}
- 作者：{book_author or "未知"}
- 借阅要求：{book_requirements or "无"}

请判断这本书是否可能满足用户的需求。考虑以下因素：
1. 书籍主题是否匹配需求
2. 借阅要求是否符合用户期望（比如用户能接受涂画、标记等）
3. 整体匹配度

请只输出以下格式：
MATCH: yes 或 no
REASON: 简要说明匹配理由（一句话，中文）"""

    try:
        import requests as http_req
        from ...config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 200
        }
        resp = http_req.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        resp_json = resp.json()
        response = resp_json["choices"][0]["message"]["content"]
        
        is_match = "MATCH: YES" in response.upper()
        reason = ""
        for line in response.split("\n"):
            if line.startswith("REASON:"):
                reason = line.replace("REASON:", "").strip()
                break
        
        return is_match, reason
    except Exception as e:
        print(f"[RequestMatch] AI调用失败: {e}")
        return False, ""


def run_match_check():
    """定时扫描：检查所有活跃需求 vs 所有可借图书"""
    print(f"\n[RequestMatch] 开始匹配扫描... ({datetime.now().strftime('%H:%M:%S')})")
    
    with get_db() as session:
        # 获取所有活跃需求
        requests = session.query(ExchangeRequest).filter(
            ExchangeRequest.is_active == True
        ).all()
        
        # 获取所有可借图书
        books = session.query(ExchangeBook).filter(
            ExchangeBook.status == "available"
        ).all()
        
        matched_count = 0
        for req in requests:
            for book in books:
                # 跳过已经匹配过的组合
                existing = session.query(RequestMatch).filter(
                    RequestMatch.request_id == req.id,
                    RequestMatch.book_id == book.id
                ).first()
                if existing:
                    continue
                
                # 跳过自己的书
                if req.user_id == book.owner_id:
                    continue
                
                # AI判断是否匹配
                is_match, reason = ai_match_check(
                    req.description,
                    book.book_name,
                    book.author or "",
                    book.requirements or ""
                )
                
                if is_match and reason:
                    match = RequestMatch(
                        request_id=req.id,
                        book_id=book.id,
                        match_reason=reason
                    )
                    session.add(match)
                    matched_count += 1
                    
                    # 通知用户
                    user = session.query(User).filter(User.id == req.user_id).first()
                    if user:
                        print(f"[RequestMatch] 匹配成功! 用户: {user.username}, "
                              f"需求: {req.description[:30]}..., "
                              f"书籍: {book.book_name}, "
                              f"理由: {reason}")
                        # 打印邮件通知（后续接入真实邮箱）
                        from ...mailer import send_email
                        subject = f"书搜搜 - 你挂的需求有匹配的图书啦！"
                        body = f"""
                        <h2>书搜搜 BookSearch</h2>
                        <p>你好 {user.username}，</p>
                        <p>你挂的需求「{req.description[:50]}」有新书匹配！</p>
                        <p><strong>匹配书籍：</strong>{book.book_name}</p>
                        <p><strong>匹配理由：</strong>{reason}</p>
                        <p><a href="http://localhost:8000/exchange/{book.id}" 
                              style="background:#8B4513;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;">
                            查看图书详情</a></p>
                        """
                        send_email(user.email, subject, body)
        
        session.commit()
    
    print(f"[RequestMatch] 扫描完成，新增匹配: {matched_count}")


# ============================================
# 可借列表
# ============================================
@router.get("/", response_class=HTMLResponse)
async def exchange_index(request: Request):
    """可借书籍列表"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get("language", "zh")
    search_q = request.query_params.get("q", "")
    
    with get_db() as session:
        query = session.query(ExchangeBook).filter(ExchangeBook.status == "available").order_by(ExchangeBook.created_at.desc())
        
        if search_q:
            query = query.filter(
                (ExchangeBook.book_name.contains(search_q)) |
                (ExchangeBook.author.contains(search_q)) |
                (ExchangeBook.requirements.contains(search_q))
            )
        
        books = query.all()
        book_list = []
        for b in books:
            book_list.append({
                "id": b.id,
                "book_name": b.book_name,
                "author": b.author or "",
                "requirements": b.requirements or "",
                "expectations": b.expectations or "",
                "owner": b.owner.username if b.owner else "匿名",
                "owner_id": b.owner_id,
                "created_at": b.created_at.strftime("%Y-%m-%d") if b.created_at else ""
            })
    
    # 获取用户的活跃需求
    with get_db() as session:
        my_requests = session.query(ExchangeRequest).filter(
            ExchangeRequest.user_id == current_user.id,
            ExchangeRequest.is_active == True
        ).count()
        
        # 获取用户的匹配通知数
        my_matches = session.query(RequestMatch).join(
            ExchangeRequest, RequestMatch.request_id == ExchangeRequest.id
        ).filter(
            ExchangeRequest.user_id == current_user.id,
            RequestMatch.is_notified == False
        ).count()
    
    return templates.TemplateResponse(request, "exchange_index.html", {
        "language": lang,
        "current_user": current_user,
        "books": book_list,
        "search_q": search_q,
        "my_requests": my_requests,
        "my_matches": my_matches
    })


# ============================================
# 发布图书
# ============================================
@router.get("/new", response_class=HTMLResponse)
async def new_exchange_page(request: Request):
    """发布图书页面"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get("language", "zh")
    
    return templates.TemplateResponse(request, "new_exchange.html", {
        "language": lang,
        "current_user": current_user
    })


@router.post("/new")
async def new_exchange(
    request: Request,
    book_name: str = Form(...),
    author: str = Form(""),
    requirements: str = Form(""),
    expectations: str = Form("")
):
    """提交发布图书"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        book = ExchangeBook(
            owner_id=current_user.id,
            book_name=book_name,
            author=author,
            requirements=requirements,
            expectations=expectations,
            status="available"
        )
        session.add(book)
        session.commit()
    
    return RedirectResponse(url="/exchange/", status_code=303)


# ============================================
# 挂需求
# ============================================
@router.get("/request/new", response_class=HTMLResponse)
async def new_request_page(request: Request):
    """挂需求页面"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get("language", "zh")
    
    return templates.TemplateResponse(request, "new_request.html", {
        "language": lang,
        "current_user": current_user
    })


@router.post("/request/new")
async def new_request(
    request: Request,
    description: str = Form(...)
):
    """提交需求并自动匹配"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        req = ExchangeRequest(
            user_id=current_user.id,
            description=description,
            is_active=True
        )
        session.add(req)
        session.commit()
        
        
    
    return RedirectResponse(url="/exchange/my-requests", status_code=303)


# ============================================
# 我的需求
# ============================================
@router.get("/my-requests", response_class=HTMLResponse)
async def my_requests_page(request: Request):
    """查看我的需求和匹配结果"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get("language", "zh")
    
    with get_db() as session:
        requests_list = session.query(ExchangeRequest).filter(
            ExchangeRequest.user_id == current_user.id
        ).order_by(ExchangeRequest.created_at.desc()).all()
        
        req_list = []
        for req in requests_list:
            # 查询这个需求的匹配结果
            matches = session.query(RequestMatch).filter(
                RequestMatch.request_id == req.id
            ).order_by(RequestMatch.created_at.desc()).all()
            
            match_list = []
            for m in matches:
                book = session.query(ExchangeBook).filter(ExchangeBook.id == m.book_id).first()
                if book:
                    match_list.append({
                        "book_name": book.book_name,
                        "author": book.author or "",
                        "book_id": book.id,
                        "reason": m.match_reason or "",
                        "created_at": m.created_at.strftime("%m-%d %H:%M") if m.created_at else ""
                    })
            
            req_list.append({
                "id": req.id,
                "description": req.description,
                "is_active": req.is_active,
                "created_at": req.created_at.strftime("%m-%d %H:%M") if req.created_at else "",
                "matches": match_list
            })
    
    return templates.TemplateResponse(request, "my_requests.html", {
        "language": lang,
        "current_user": current_user,
        "requests": req_list
    })


# ============================================
# 匹配所有活跃需求
# ============================================
@router.post("/match-all")
async def match_all_requests(request: Request):
    """匹配当前用户的所有活跃需求"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    run_match_check()
    
    return RedirectResponse(url="/exchange/my-requests", status_code=303)


# ============================================
# 关闭需求
# ============================================
@router.post("/request/{req_id}/close")
async def close_request(request: Request, req_id: int):
    """关闭需求"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        req = session.query(ExchangeRequest).filter(
            ExchangeRequest.id == req_id,
            ExchangeRequest.user_id == current_user.id
        ).first()
        if req:
            req.is_active = False
            session.commit()
    
    return RedirectResponse(url="/exchange/my-requests", status_code=303)


# ============================================
# 手动触发匹配扫描
# ============================================
# ============================================
# AI生成借阅规则
# ============================================
class BookRuleRequest(BaseModel):
    book_name: str
    author: str = ""


@router.post("/ai-generate-rules")
async def ai_generate_rules(req: BookRuleRequest):
    """AI根据书名和作者生成借阅要求和期望"""
    prompt = f"""你是一位图书借阅规则助手。根据书名和作者信息，生成合理的中文借阅要求和期望说明。

书名：{req.book_name}
作者：{req.author or "未知"}

请生成：
1. 借阅要求：对借阅者的要求（如归还期限、书本保护等），2-3句话
2. 期望说明：希望借阅者注意的事项，2-3句话

请以JSON格式返回：
{{"requirements": "借阅要求的内容", "expectations": "期望说明的内容"}}

只返回JSON，不要其他任何内容。"""

    try:
        import requests as http_req
        from ...config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": DEEPSEEK_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 300
        }
        resp = http_req.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=30)
        resp_json = resp.json()
        response = resp_json["choices"][0]["message"]["content"]
        
        # 提取JSON
        import re
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "requirements": result.get("requirements", ""),
                "expectations": result.get("expectations", "")
            }
    except Exception as e:
        print(f"[AI Rules] 生成失败: {e}")
    
    return {"requirements": "", "expectations": ""}


@router.post("/match-scan")
async def trigger_match_scan():
    """手动触发匹配扫描（页面上的按钮）"""
    run_match_check()
    return RedirectResponse(url="/exchange/", status_code=303)


# ============================================
# 图书详情 & 站内评论区
# ============================================
@router.get("/{book_id}", response_class=HTMLResponse)
async def exchange_detail(request: Request, book_id: int):
    """图书详情 + 站内评论区"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get("language", "zh")
    
    with get_db() as session:
        book = session.query(ExchangeBook).filter(ExchangeBook.id == book_id).first()
        if not book:
            msg = "图书不存在" if lang == "zh" else "Book not found"
            return HTMLResponse(msg, status_code=404)
        
        messages = session.query(ExchangeMessage).filter(
            ExchangeMessage.book_id == book_id
        ).order_by(ExchangeMessage.created_at.asc()).all()
        
        msg_list = []
        for m in messages:
            msg_list.append({
                "id": m.id,
                "content": m.content,
                "sender": m.sender.username if m.sender else "匿名",
                "sender_id": m.sender_id,
                "created_at": m.created_at.strftime("%Y-%m-%d %H:%M") if m.created_at else ""
            })
        
        book_data = {
            "id": book.id,
            "book_name": book.book_name,
            "author": book.author or "",
            "requirements": book.requirements or "",
            "expectations": book.expectations or "",
            "owner": book.owner.username if book.owner else "匿名",
            "owner_id": book.owner_id,
            "status": book.status,
            "created_at": book.created_at.strftime("%Y-%m-%d") if book.created_at else ""
        }
    
    return templates.TemplateResponse(request, "exchange_detail.html", {
        "language": lang,
        "current_user": current_user,
        "book": book_data,
        "messages": msg_list
    })


# ============================================
# 发送消息
# ============================================
@router.post("/{book_id}/message")
async def send_message(
    request: Request,
    book_id: int,
    content: str = Form(...)
):
    """发送站内消息"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        book = session.query(ExchangeBook).filter(ExchangeBook.id == book_id).first()
        if not book:
            return RedirectResponse(url="/exchange/", status_code=303)
        
        receiver_id = book.owner_id
        
        message = ExchangeMessage(
            book_id=book_id,
            sender_id=current_user.id,
            receiver_id=receiver_id,
            content=content
        )
        session.add(message)
        session.commit()
        
        try:
            owner = session.query(User).filter(User.id == receiver_id).first()
            if owner and owner.email:
                from ...mailer import send_message_notification
                book_url = f"http://localhost:8000/exchange/{book_id}"
                send_message_notification(
                    to_email=owner.email,
                    receiver_name=owner.username,
                    sender_name=current_user.username,
                    book_name=book.book_name,
                    message_content=content,
                    book_url=book_url
                )
        except Exception as e:
            print(f"发送邮件通知失败: {e}")
    
    return RedirectResponse(url=f"/exchange/{book_id}", status_code=303)


# ============================================
# 下架图书
# ============================================
@router.post("/{book_id}/close")
async def close_exchange(request: Request, book_id: int):
    """下架图书"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        book = session.query(ExchangeBook).filter(
            ExchangeBook.id == book_id,
            ExchangeBook.owner_id == current_user.id
        ).first()
        
        if book:
            book.status = "closed"
            session.commit()
    
    return RedirectResponse(url="/exchange/", status_code=303)




# ============================================
# 删除需求
# ============================================
@router.post("/request/{request_id}/delete")
async def delete_request(request: Request, request_id: int):
    """删除需求（包括关联的匹配记录）"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        req = session.query(ExchangeRequest).filter(
            ExchangeRequest.id == request_id,
            ExchangeRequest.user_id == current_user.id
        ).first()
        
        if req:
            session.query(RequestMatch).filter(
                RequestMatch.request_id == request_id
            ).delete()
            session.delete(req)
            session.commit()
            print(f"[Delete] 用户 {current_user.username} 删除了需求 #{request_id}")
    
    return RedirectResponse(url="/exchange/my-requests", status_code=303)


# ============================================
# 重新开启需求
# ============================================
@router.post("/request/{request_id}/reopen")
async def reopen_request(request: Request, request_id: int):
    """重新开启已关闭的需求"""
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    with get_db() as session:
        req = session.query(ExchangeRequest).filter(
            ExchangeRequest.id == request_id,
            ExchangeRequest.user_id == current_user.id
        ).first()
        
        if req:
            req.is_active = True
            session.commit()
            print(f"[Reopen] 用户 {current_user.username} 重新开启了需求 #{request_id}")
    
    return RedirectResponse(url="/exchange/my-requests", status_code=303)
