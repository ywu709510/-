"""
书搜搜 - 邮件发送模块
负责：发送验证邮件、通知邮件
============================================
后续对接真实邮箱：
   1. 在 config.py 中填写 MAIL_USERNAME / MAIL_PASSWORD
   2. 修改 _print_email 为 _send_real_email
============================================
"""

def _print_email(to_email, subject, body):
    """开发阶段，邮件内容打印到控制台"""
    import re
    # 移除HTML标签，纯文本显示
    text = re.sub(r'<[^>]+>', '', body)
    text = text.replace('&nbsp;', ' ').strip()
    
    print("\n" + "=" * 60)
    print(f"[Mail] To: {to_email}")
    print(f"[Mail] Subject: {subject}")
    print(f"[Mail] Body:")
    print(text)
    print("=" * 60 + "\n")


import smtplib
from email.mime.text import MIMEText
from ..config import MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_FROM

def send_email(to_email: str, subject: str, body: str):
    """发送邮件（QQ邮箱SMTP）"""
    try:
        msg = MIMEText(body, "html", "utf-8")
        msg["Subject"] = subject
        msg["From"] = MAIL_FROM
        msg["To"] = to_email
        
        server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
        server.starttls()
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.sendmail(MAIL_FROM, to_email, msg.as_string())
        server.quit()
        print(f"[Mail] 已发送 -> {to_email} | {subject}")
    except Exception as e:
        print(f"[Mail] 发送失败 -> {to_email}: {e}")
        # 失败时打印到控制台
        _print_email(to_email, subject, body)


def send_verification_email(to_email: str, username: str, verify_link: str):
    """发送邮箱验证邮件"""
    subject = "书搜搜 - 验证您的邮箱 / BookSearch - Verify Your Email"
    body = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#8B4513;">书搜搜 BookSearch</h2>
        <p>你好 <strong>{username}</strong>，</p>
        <p>感谢你注册书搜搜！请点击下方链接验证你的邮箱：</p>
        <p>Thank you for registering! Please click below to verify your email:</p>
        <p style="text-align:center;margin:25px 0;">
            <a href="{verify_link}" 
               style="background:#8B4513;color:#fff;padding:12px 30px;border-radius:8px;text-decoration:none;font-size:16px;">
                Verify Email - 验证邮箱
            </a>
        </p>
        <p>如果按钮无法点击，请复制以下链接到浏览器：</p>
        <p style="color:#666;font-size:12px;">{verify_link}</p>
        <p style="color:#999;font-size:12px;">如果这不是你注册的，请忽略此邮件。</p>
        <p style="color:#999;font-size:12px;">If you did not register, please ignore this email.</p>
    </div>
    """
    send_email(to_email, subject, body)



def send_forum_comment_notification(to_email, receiver_name, sender_name, book_name, comment_content, post_url):
    """发送论坛评论通知"""
    subject = "书搜搜 - %s 评论了你的帖子「%s」" % (sender_name, book_name)
    body = """
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#8B4513;">书搜搜 BookSearch</h2>
        <p>你好 <strong>%s</strong>，</p>
        <p>用户 <strong>%s</strong> 评论了你的帖子「%s」：</p>
        <div style="background:#f5f0eb;padding:15px;border-radius:8px;margin:15px 0;border-left:4px solid #8B4513;">
            %s
        </div>
        <p style="text-align:center;margin:25px 0;">
            <a href="%s" 
               style="background:#8B4513;color:#fff;padding:12px 30px;border-radius:8px;text-decoration:none;font-size:16px;">
                View Post - 查看帖子
            </a>
        </p>
    </div>
    """ % (receiver_name, sender_name, book_name, comment_content, post_url)
    send_email(to_email, subject, body)

def send_message_notification(to_email: str, receiver_name: str, sender_name: str, book_name: str, message_content: str, book_url: str):
    """发送站内消息提醒"""
    subject = f"书搜搜 - {sender_name} 对「{book_name}」发了一条消息"
    body = f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;">
        <h2 style="color:#8B4513;">书搜搜 BookSearch</h2>
        <p>你好 <strong>{receiver_name}</strong>，</p>
        <p>用户 <strong>{sender_name}</strong> 对您发布的图书「{book_name}」发了一条消息：</p>
        <div style="background:#f5f0eb;padding:15px;border-radius:8px;margin:15px 0;border-left:4px solid #8B4513;">
            {message_content}
        </div>
        <p style="text-align:center;margin:25px 0;">
            <a href="{book_url}" 
               style="background:#8B4513;color:#fff;padding:12px 30px;border-radius:8px;text-decoration:none;font-size:16px;">
                View Message - 查看消息
            </a>
        </p>
    </div>
    """
    send_email(to_email, subject, body)

