"""
ASGI config for config project.

Django와 MCP를 한 서버로 띄운다. 실행은 ``uvicorn config.asgi:application``.
Django는 lifespan과 ASGI 앱 마운트를 지원하지 않아서 바깥에 Starlette를 둔다.
"""

import os
from contextlib import asynccontextmanager

from django.conf import settings as django_settings
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
from django.core.asgi import get_asgi_application
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Mount

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_app = get_asgi_application()
if django_settings.DEBUG:
    django_app = ASGIStaticFilesHandler(django_app)

# MCP 코드는 Django 모델을 쓰므로 앱 초기화가 끝난 뒤에 불러온다.
from config.app_settings import get_settings
from library import mcp_server as collection_server


@asynccontextmanager
async def lifespan(app):
    server = collection_server.new_transport()
    async with server.session_manager.run():
        yield


application = Starlette(
    routes=[
        Mount('/mcp', collection_server.mcp_app),
        Mount('/', django_app),
    ],
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=get_settings().cors_origin_list,
            allow_origin_regex=r'http://(localhost|127\.0\.0\.1)(:\d+)?',
            allow_credentials=False,
            allow_methods=['GET', 'POST', 'PUT', 'DELETE'],
            allow_headers=[
                'Authorization',
                'Content-Type',
                'MCP-Protocol-Version',
                'Mcp-Session-Id',
            ],
            expose_headers=['Mcp-Session-Id'],
        ),
    ],
    lifespan=lifespan,
)
