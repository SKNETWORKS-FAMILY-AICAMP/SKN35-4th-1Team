"""서비스가 Django 모델을 쓰므로 테스트 수집 전에 Django를 초기화한다."""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
