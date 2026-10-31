from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["name", "owner__email"]
    autocomplete_fields = ["owner", "participants"]
