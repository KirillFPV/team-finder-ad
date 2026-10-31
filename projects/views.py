from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from team_finder.http import json_post

from .forms import ProjectForm
from .models import Project


@require_GET
def project_list(request):
    projects = Project.objects.select_related("owner").prefetch_related("participants")
    page = Paginator(projects, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "projects/project_list.html",
        {
            "projects": page.object_list,
            "page_obj": page,
            "query_prefix": "",
        },
    )


@require_GET
@ensure_csrf_cookie
def detail(request, pk):
    project = get_object_or_404(
        Project.objects.select_related("owner").prefetch_related("participants"), pk=pk
    )
    participating = request.user.is_authenticated and request.user in project.participants.all()
    return render(
        request,
        "projects/project-details.html",
        {
            "project": project,
            "participating": participating,
            "can_participate": project.status == Project.Status.OPEN or participating,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def project_form(request, pk=None):
    project = get_object_or_404(Project, pk=pk) if pk is not None else None
    if project and project.owner_id != request.user.pk:
        raise PermissionDenied
    form = ProjectForm(request.POST if request.method == "POST" else None, instance=project)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save(commit=False)
            if project is None:
                saved.owner = request.user
            saved.save()
            saved.participants.add(saved.owner)
        return redirect("projects:detail", pk=saved.pk)
    return render(request, "projects/create-project.html", {"form": form, "is_edit": bool(pk)})


@json_post
@transaction.atomic
def complete(request, pk):
    project = Project.objects.select_for_update().filter(pk=pk).first()
    if project is None:
        return JsonResponse({"error": "Проект не найден."}, status=404)
    if project.owner_id != request.user.pk:
        return JsonResponse({"error": "Только автор может завершить проект."}, status=403)
    project.status = Project.Status.CLOSED
    project.save(update_fields=["status"])
    return JsonResponse({"status": "ok", "project_status": "closed"})


@json_post
def toggle_participate(request, pk):
    with transaction.atomic():
        project = Project.objects.select_for_update().filter(pk=pk).first()
        if project is None:
            return JsonResponse({"error": "Проект не найден."}, status=404)
        if project.owner_id == request.user.pk:
            return JsonResponse({"error": "Автор остаётся участником проекта."}, status=400)
        participating = project.participants.filter(pk=request.user.pk).exists()
        if not participating and project.status == Project.Status.CLOSED:
            return JsonResponse({"error": "Проект уже закрыт."}, status=400)
        if participating:
            project.participants.remove(request.user)
        else:
            project.participants.add(request.user)
    return JsonResponse({"status": "ok", "participant": not participating})
