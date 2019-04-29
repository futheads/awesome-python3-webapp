import logging; logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime
import orm
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from coroweb import add_routes, add_static


def index(request):
    return web.Response(body=b'<h1>Awesome</h1>')


def init_jinja2(app, **kwargs):
    logging.info("init jinja2...")
    options = dict(
        autoescape=kwargs.get("autoescape", True),
        block_start_string=kwargs.get("block_start_string", '{%'),
        block_end_string=kwargs.get("block_end_string", "%}"),
        variable_start_string=kwargs.get("variable_start_string", "{{"),
        variable_end_string=kwargs.get("variable_end_string", "}}"),
        auto_reload=kwargs.get("auto_reload", True)
    )
    path = kwargs.get("path", None)
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
    logging.info("set jinjia2 template path: %s" % path)
    env = Environment(loader=FileSystemLoader(path), **options)
    filters = kwargs.get("filters", None)
    if filters is not None:
        for name, f in filters.items():
            env.filters[name] = f
    app["__templating__"] = env


async def logger_factory(app, handler):
    async def logger(request):
        logging.info("Request: %s %s" % (request.method, request.path))
        return await handler(request)
    return logger


async def response_factory(app, handler):
    async def response(request):
        logging.info("Response handler...")
        r = await handler(request)
        if isinstance(r, web.StreamResponse):
            return r
        if isinstance(r, bytes):
            resp = web.Response(body=r)
            resp.content_type = "application/octet-stream"
            return resp
        if isinstance(r, str):
            if r.startswith("redirect:"):
                return web.HTTPFound(r[9:])
            resp = web.Response(body=r.encode("utf-8"))
            resp.content_type = "text/html;charset=utf-8"
            return resp
        if isinstance(r, dict):
            template = r.get("__template__")
            if template is None:
                resp = web.Response(body=json.dumps(r, ensure_ascii=False, default=lambda o: o.__dict__).encode("utf-8"))
                resp.content_type = "text/html;charset=utf-8"
                return resp
            else:
                resp = web.Response(body=app["__templating__"].get_template(template).render(**r).encode("utf-8"))
                resp.content_type = "text/html;charset=utf-8"
                return resp
        if isinstance(r, int) and 100 <= r < 600:
            return web.Response(r)
        if isinstance(r, tuple) and len(r) == 2:
            t, m = r
            if isinstance(t, int) and 100 <= t < 600:
                return web.Response(t, str(m))
        resp = web.Response(body=str(r).encode("utf-8"))
        resp.content_type = "text/plain;charset=utf-8"
        return resp
    return response


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u"1分钟前"
    if delta < 3600:
        return u"%s分钟前" % (delta // 60)
    if delta < 86400:
        return u"%s小时前" % (delta // 3600)
    if delta < 604800:
        return u"%s天前" % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u"%s年%s月%s日" % (dt.year, dt.month, dt.day)


async def init(loop):
    await orm.create_pool(loop=loop, host='127.0.0.1', port=3306, user='futhead', password='futhead', db='awesome')
    app = web.Application(loop=loop, middlewares=[
        logger_factory, response_factory
    ])
    init_jinja2(app, filters=dict(datetime=datetime_filter))
    add_routes(app, "handlers")
    add_static(app)
    srv = await loop.create_server(app.make_handler(), '127.0.0.1', 9000)
    logging.info('server started at http://127.0.0.1:9000...')
    return srv

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()