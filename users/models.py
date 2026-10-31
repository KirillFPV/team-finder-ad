from io import BytesIO
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.files.base import ContentFile
from django.db import models
from django.db.models.functions import Lower
from PIL import Image, ImageDraw, ImageFont

from team_finder.validators import normalize_phone, validate_github_url


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email обязателен.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if not extra_fields["is_staff"] or not extra_fields["is_superuser"]:
            raise ValueError("Суперпользователь должен иметь is_staff и is_superuser.")
        return self.create_user(email, password, **extra_fields)


class Skill(models.Model):
    name = models.CharField("Название", max_length=124, unique=True)

    class Meta:
        ordering = [Lower("name"), "pk"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_skill_name_ci"),
            models.CheckConstraint(condition=~models.Q(name=""), name="skill_name_not_empty"),
        ]
        verbose_name = "навык"
        verbose_name_plural = "навыки"

    def __str__(self):
        return self.name


class User(AbstractUser):
    username = None
    first_name = None
    last_name = None
    email = models.EmailField("Email", unique=True)
    name = models.CharField("Имя", max_length=124)
    surname = models.CharField("Фамилия", max_length=124)
    avatar = models.ImageField("Аватар", upload_to="avatars/")
    phone = models.CharField("Телефон", max_length=12, null=True, blank=True, unique=True)
    github_url = models.URLField("GitHub", blank=True, validators=[validate_github_url])
    about = models.TextField("О себе", max_length=256, blank=True)
    skills = models.ManyToManyField(Skill, related_name="users", blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "surname"]
    objects = UserManager()

    class Meta:
        ordering = ["-date_joined", "-pk"]
        indexes = [models.Index(fields=["-date_joined", "-id"])]
        constraints = [models.UniqueConstraint(Lower("email"), name="unique_user_email_ci")]
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"

    def __str__(self):
        return f"{self.name} {self.surname} ({self.email})"

    def get_full_name(self):
        return f"{self.name} {self.surname}".strip()

    def get_short_name(self):
        return self.name

    def clean(self):
        super().clean()
        self.email = self.email.strip().lower()
        self.phone = normalize_phone(self.phone)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        self.phone = normalize_phone(self.phone)
        if not self.avatar:
            image = Image.new("RGB", (240, 240), "#dce7ee")
            font = ImageFont.truetype(
                str(settings.BASE_DIR / "static/fonts/Neue_Haas_Grotesk_Display_Pro_75_Bold.otf"),
                120,
            )
            ImageDraw.Draw(image).text(
                (120, 120),
                (self.name.strip()[:1] or "?").upper(),
                fill="#243746",
                font=font,
                anchor="mm",
            )
            content = BytesIO()
            image.save(content, format="PNG")
            self.avatar.save(f"{uuid4().hex}.png", ContentFile(content.getvalue()), save=False)
        super().save(*args, **kwargs)
