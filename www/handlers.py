

from coroweb import get, post

from models import User, Comment, Blog, next_id


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
