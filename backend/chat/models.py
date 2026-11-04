"""저장된 대화. 3차 TiDB 테이블을 그대로 쓰므로 Django가 스키마를 바꾸지 않는다."""

from django.db import models

from accounts.models import User
from catalog.models import Artwork


class ChatRole(models.TextChoices):
    USER = "user"
    ASSISTANT = "assistant"


class ChatSession(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.DO_NOTHING)
    artwork = models.ForeignKey(Artwork, models.DO_NOTHING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'chat_sessions'
        unique_together = (('user', 'artwork'),)


class ChatMessage(models.Model):
    id = models.BigAutoField(primary_key=True)
    session = models.ForeignKey(ChatSession, models.DO_NOTHING)
    role = models.CharField(max_length=20)
    content = models.TextField()
    refused = models.BooleanField(default=False)
    sources = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'chat_messages'
