from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os
from jinja2 import Environment, FileSystemLoader, ChoiceLoader

from ...utils import get_db, get_current_user

router = APIRouter(prefix='/profile', tags=['profile'])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
profile_templates = os.path.join(BASE_DIR, 'modules', 'profile', 'templates')
global_templates = os.path.join(BASE_DIR, 'templates')

loader = ChoiceLoader([
    FileSystemLoader(profile_templates),
    FileSystemLoader(global_templates)
])
env = Environment(loader=loader, cache_size=0)
templates = Jinja2Templates(env=env)


def require_login(request: Request):
    current_user = get_current_user(request)
    if not current_user:
        return RedirectResponse(url='/auth/login', status_code=303)
    return current_user


@router.get('', response_class=HTMLResponse)
async def profile_page(request: Request):
    login_check = require_login(request)
    if isinstance(login_check, RedirectResponse):
        return login_check
    current_user = login_check
    
    lang = request.cookies.get('language', 'zh')
    
    from ...database.models import ExchangeBook, Post, Comment
    
    with get_db() as session:
        my_books = session.query(ExchangeBook).filter(
            ExchangeBook.owner_id == current_user.id
        ).order_by(ExchangeBook.created_at.desc()).all()
        
        my_posts = session.query(Post).filter(
            Post.user_id == current_user.id
        ).order_by(Post.created_at.desc()).all()
        
        unread_comments = {}
        for post in my_posts:
            has_new = session.query(Comment).filter(
                Comment.post_id == post.id,
                Comment.user_id != current_user.id
            ).first()
            if has_new:
                unread_comments[post.id] = True
    
    return templates.TemplateResponse(request, 'profile.html', {
        'language': lang,
        'current_user': current_user,
        'my_books': my_books,
        'my_posts': my_posts,
        'unread_comments': unread_comments
    })

