"""``python -m scripts.x``로 실행한다. 서비스가 Django 모델을 쓰므로 먼저 초기화한다."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
