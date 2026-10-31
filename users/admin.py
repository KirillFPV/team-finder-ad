from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AdminUserChangeForm, AdminUserCreationForm
from .models import Skill, User


@admin.register(User)
class TeamFinderUserAdmin(UserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    ordering = ["email"]
    list_display = ["email", "name", "surname", "is_active", "is_staff"]
    search_fields = ["email", "name", "surname"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Профиль",
            {"fields": ("name", "surname", "avatar", "phone", "about", "github_url", "skills")},
        ),
        (
            "Права",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Даты", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = ((None, {"fields": ("email", "name", "surname", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions", "skills")


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    search_fields = ["name"]
