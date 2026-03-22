import secrets

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def generate_token():
    return secrets.token_urlsafe(32)  # 43 URL-safe chars, cryptographically random


class Survey(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Question(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.text[:80]


class AccessToken(models.Model):
    survey = models.ForeignKey(Survey, on_delete=models.CASCADE, related_name='tokens')
    token = models.CharField(max_length=64, unique=True, default=generate_token)
    used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.survey} — {self.token[:12]}…"


SCALE_CHOICES = [(i, str(i)) for i in range(1, 6)]


class Response(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='responses')
    access_token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name='responses')
    value = models.IntegerField(
        choices=SCALE_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('question', 'access_token')]

    def __str__(self):
        return f"Response({self.question_id}, token={self.access_token_id}, value={self.value})"
