"""회원. 3차 TiDB 테이블을 그대로 쓰므로 Django가 스키마를 바꾸지 않는다."""

import secrets

from django.db import models
from django.utils import timezone


def new_public_id() -> str:
    return secrets.token_urlsafe(9)


class User(models.Model):
    id = models.BigAutoField(primary_key=True)
    email = models.CharField(unique=True, max_length=255)
    nickname = models.CharField(max_length=50)
    firebase_uid = models.CharField(unique=True, max_length=128)
    public_id = models.CharField(unique=True, max_length=22, default=new_public_id)
    follow_list_public = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'users'

    def __str__(self):
        return self.nickname


class SocialAccount(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(User, models.DO_NOTHING)
    provider = models.CharField(max_length=30)
    provider_user_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = False
        db_table = 'social_accounts'
        unique_together = (('provider', 'provider_user_id'),)


class UserPreference(models.Model):
    user = models.OneToOneField(User, models.DO_NOTHING, primary_key=True)
    birth_year = models.SmallIntegerField(blank=True, null=True)
    birth_date = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=30, blank=True, null=True)
    tone = models.CharField(max_length=30, blank=True, null=True)
    explanation_level = models.CharField(max_length=30, blank=True, null=True)
    explanation_priorities = models.JSONField(blank=True, null=True)
    conversation_style = models.CharField(max_length=30, blank=True, null=True)
    onboarding_completed = models.BooleanField(default=False)
    taste_summary = models.TextField(blank=True, null=True)
    taste_fingerprint = models.CharField(max_length=64, blank=True, null=True)
    taste_generated_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'user_preferences'


class UserFollow(models.Model):
    pk = models.CompositePrimaryKey('follower_id', 'followee_id')
    follower = models.ForeignKey(User, models.DO_NOTHING)
    followee = models.ForeignKey(User, models.DO_NOTHING, related_name='follower_links')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        managed = False
        db_table = 'user_follows'
