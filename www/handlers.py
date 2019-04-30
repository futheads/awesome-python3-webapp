import re
import hashlib
import time
import json
import logging

from aiohttp import web
from coroweb import get, post
from apis import APIValueError, APIPermissionError, Page

from models import User, Comment, Blog, next_id
from config import configs

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def user2cookie(user, max_age):
    """
    Generate cookie str by user
    :param user:
    :param max_age:
    :return:
    """
    expires = str(int(time.time() + max_age))
    s = "%s-%s-%s-%s" % (user.id, user.passwd, expires, _COOKIE_KEY)
    _list = [user.id, expires, hashlib.sha1(s.encode("utf-8")).hexdigest()]
    return "-".join(_list)


async def cookie2user(cookie_str):
    """
    Parse cookie and load user if cookie is valid
    :param cookie_str:
    :return:
    """
    if not cookie_str:
        return None
    try:
        _list = cookie_str.split("-")
        if len(_list) != 3:
            return None
        uid, expires, sha1 = _list
        if int(expires) < time.time():
            return None
        user = await User.findall(uid)
        if user is None:
            return None
        s = "%s-%s-%s-%s" % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode("utf-8")).hexdigest():
            logging.info("invalid sha1")
            return None
        user.passwd = "******"
        return user
    except Exception as e:
        logging.exception(e)
        return None


@post("/api/users")
async def api_register_user(*, email, name, passwd):
    if not name or not name.strip():
        raise APIValueError("name")
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError("email")
    if not passwd or not _RE_SHA1.match(passwd):
        raise APIValueError("passwd")
    users = await User.findall("email=?", [email])
    if len(users) > 0:
        raise APIValueError("register:failed", "email", "Email is already in use.")
    uid = next_id()
    sha1_passwd = "%s:%s" % (uid, passwd)
    user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode("utf-8")).hexdigest(),
                image="http://www.gravatar.com/avatar/%s?d=mm&s=120" % hashlib.md5(email.encode("utf-8")).hexdigest())
    await user.save()
    # make session cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "******"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


@post("/api/authenticate")
async def authenticate(*, email, passwd):
    if not email:
        raise ValueError("email", "Invalid email")
    if not passwd:
        raise APIValueError("passwd", "Invalid passwd")
    users = await User.findall("email=?", [email])
    if len(users) == 0:
        raise  APIValueError("email", "Email not exist.")
    user = users[0]
    # check passwd
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode("utf-8"))
    sha1.update(b":")
    sha1.update(passwd.encode("utf-8"))
    if user.passwd != sha1.hexdigest():
        raise APIValueError("passwd", "Invalid passwd.")
    # authenticate ok, set cookie
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    user.passwd = "******"
    r.content_type = "application/json"
    r.body = json.dumps(user, ensure_ascii=False).encode("utf-8")
    return r


def text2html(text):
    lines = map(lambda s: "<p>%s</p>" % s.replace("&", "&amp;").replace("<", "&alt").replace(">", "&gt;"),
                filter(lambda s: s.strip() != "", text.split("\n")))
    return "".join(lines)


@get("/blog/{id}")
async def get_blog(id):
    blog = await Blog.find(id)
    comments = await Comment.findall("blog_id=?", [id], order_by="create_at desc")
    for c in comments:
        c.html_comment = text2html(c.content)
    # blog.html_content = markdown(blog.content)
    return {
        "__template__": "blog.html",
        "blog": blog,
        "comments": comments
    }


@get("/manage/blogs/create")
def manage_create_blog():
    return {
        "__template__": "manage_blog_edit.html",
        "id": "",
        "action": "/api/blogs"
    }


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


@get("/api/blogs/{id}")
async def api_get_blog(*, id):
    blog = await Blog.find(id)
    return blog


@post("/api/blogs")
async def api_create_blog(request, *, name, summary, content):
    check_admin(request)
    if not name or not name.strip():
        raise APIValueError("name", "name cannot be empty")
    if not summary or not summary.strip():
        raise APIValueError("summay", "summary cannot be empty.")
    if not content or not content.strip():
        raise APIValueError("content", "content cannot be empty")
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image, name=name.strip())
    blog.save()
    return blog


@get("/api/blogs")
async def api_blogs(*, page="1"):
    page_index = get_page_index(page)
    num = await Blog.findNumber("count(id)")
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findall(order_by="create_at desc", limit=(p.offset, p.limit))
    return dict(page=p, blogs=blogs)


@get("/")
async def index():
    users = await User.findall()
    return {
        "users": users,
        "__template__": "templates.html"
    }


@get("/api/users")
async def get_users():
    users = await User.findall(order_by="created_at desc")
    for u in users:
        u.passwd = "******"
    return dict(users=users)
