import json
from urllib.parse import urlencode

from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models.functions import Lower
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from team_finder.http import json_post

from .forms import LoginForm, ProfileForm, RegisterForm
from .models import Skill, User


@require_http_methods(["GET", "POST"])
def register(request):
    form = RegisterForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("users:login")
    return render(request, "users/register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def sign_in(request):
    form = LoginForm(request, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        login(request, form.user)
        return redirect("projects:list")
    return render(request, "users/login.html", {"form": form})


@require_POST
def sign_out(request):
    logout(request)
    return redirect("projects:list")


@require_GET
def participants(request):
    active_skill = request.GET.get("skill", "")
    users = User.objects.all()
    if active_skill:
        users = users.filter(skills__name=active_skill)
    page = Paginator(users, 12).get_page(request.GET.get("page"))
    return render(
        request,
        "users/participants.html",
        {
            "participants": page.object_list,
            "page_obj": page,
            "all_skills": Skill.objects.values_list("name", flat=True),
            "active_skill": active_skill,
            "query_prefix": urlencode({"skill": active_skill}) + "&" if active_skill else "",
        },
    )


@require_GET
@ensure_csrf_cookie
def profile(request, pk):
    user = get_object_or_404(
        User.objects.prefetch_related("skills", "owned_projects__participants"), pk=pk
    )
    return render(request, "users/user-details.html", {"user": user})


@login_required
@require_http_methods(["GET", "POST"])
def edit_profile(request):
    form = ProfileForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("users:detail", pk=request.user.pk)
    return render(request, "users/edit_profile.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def change_password(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        return redirect("users:detail", pk=user.pk)
    return render(request, "users/change_password.html", {"form": form})


@require_GET
def skills(request):
    query = request.GET.get("q", "").strip()
    matches = Skill.objects.filter(name__istartswith=query).order_by(Lower("name"), "pk")[:10]
    return JsonResponse(list(matches.values("id", "name")), safe=False)


@json_post
def add_skill(request, pk):
    if request.user.pk != pk:
        return JsonResponse({"error": "Можно изменять только свой профиль."}, status=403)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Некорректный JSON."}, status=400)
    if not isinstance(data, dict) or (("skill_id" in data) == ("name" in data)):
        return JsonResponse({"error": "Передайте skill_id либо name."}, status=400)
    created = False
    if "skill_id" in data:
        skill_id = data["skill_id"]
        if (
            isinstance(skill_id, bool)
            or not isinstance(skill_id, int)
            or not 1 <= skill_id <= 2**63 - 1
        ):
            return JsonResponse({"error": "Некорректный skill_id."}, status=400)
        skill = Skill.objects.filter(pk=skill_id).first()
        if skill is None:
            return JsonResponse({"error": "Навык не найден."}, status=404)
    else:
        name = data["name"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 124:
            return JsonResponse(
                {"error": "Название должно содержать от 1 до 124 символов."}, status=400
            )
        name = name.strip()
        # The database constraint also protects concurrent case-insensitive creation.
        try:
            with transaction.atomic():
                skill, created = Skill.objects.get_or_create(
                    name__iexact=name, defaults={"name": name}
                )
        except IntegrityError:
            skill = Skill.objects.get(name__iexact=name)
    with transaction.atomic():
        User.objects.select_for_update().get(pk=pk)
        added = not request.user.skills.filter(pk=skill.pk).exists()
        request.user.skills.add(skill)
    return JsonResponse(
        {
            "skill_id": skill.pk,
            "id": skill.pk,
            "name": skill.name,
            "created": created,
            "added": added,
        }
    )


@json_post
def remove_skill(request, pk, skill_id):
    if request.user.pk != pk:
        return JsonResponse({"error": "Можно изменять только свой профиль."}, status=403)
    if not request.user.skills.filter(pk=skill_id).exists():
        return JsonResponse({"error": "Навык не найден в профиле."}, status=404)
    request.user.skills.remove(skill_id)
    return JsonResponse({"status": "ok", "removed": True})
