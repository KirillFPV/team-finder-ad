import json
import os
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from projects.models import Project
from users.forms import ProfileForm
from users.models import Skill

User = get_user_model()


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class TeamFinderTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.media = TemporaryDirectory()
        cls.media_override = override_settings(MEDIA_ROOT=cls.media.name)
        cls.media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls.media_override.disable()
        cls.media.cleanup()

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            "owner@example.com", "Strong-pass-826", name="Анна", surname="Иванова"
        )
        cls.other = User.objects.create_user(
            "other@example.com", "Strong-pass-826", name="Иван", surname="Петров"
        )
        cls.project = Project.objects.create(name="Проект", owner=cls.owner)
        cls.project.participants.add(cls.owner)
        cls.skill = Skill.objects.create(name="Python")
        cls.owner.skills.add(cls.skill)

    def post_json(self, url, data):
        return self.client.post(url, json.dumps(data), content_type="application/json")

    def skill_url(self, user=None):
        return reverse("users:add_skill", args=[(user or self.owner).pk])

    def test_public_pages_render_for_guest(self):
        for url in [
            reverse("projects:list"),
            reverse("projects:detail", args=[self.project.pk]),
            reverse("users:list"),
            reverse("users:detail", args=[self.owner.pk]),
            reverse("users:login"),
            reverse("users:register"),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertRedirects(self.client.get("/"), reverse("projects:list"))
        self.assertRedirects(self.client.get("/project/list/"), reverse("projects:list"))

    def test_avatar_is_generated_and_password_is_hashed(self):
        self.assertNotEqual(self.owner.password, "Strong-pass-826")
        self.assertTrue(self.owner.check_password("Strong-pass-826"))
        with Image.open(self.owner.avatar.path) as image:
            self.assertEqual(image.size, (240, 240))

    def test_empty_auth_forms_report_required_fields(self):
        for url in [reverse("users:register"), reverse("users:login")]:
            response = self.client.post(url, {})
            self.assertTrue(response.context["form"].errors)

    def test_oversized_skill_id_is_rejected(self):
        self.client.force_login(self.owner)
        response = self.post_json(self.skill_url(), {"skill_id": 10**100})
        self.assertEqual(response.status_code, 400)

    def test_register_redirects_and_normalizes_email(self):
        response = self.client.post(
            reverse("users:register"),
            {
                "name": "Ольга",
                "surname": "Сидорова",
                "email": "NEW@EXAMPLE.COM",
                "password": "A-good-secret-123",
            },
        )
        self.assertRedirects(response, reverse("users:login"))
        user = User.objects.get(email="new@example.com")
        self.assertTrue(user.check_password("A-good-secret-123"))

    def test_register_rejects_duplicate_email_and_weak_password(self):
        for email, password in [
            ("OWNER@example.com", "Strong-pass-826"),
            ("new@example.com", "123"),
        ]:
            response = self.client.post(
                reverse("users:register"),
                {
                    "name": "Анна",
                    "surname": "Иванова",
                    "email": email,
                    "password": password,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(User.objects.count(), 2)

    def test_login_uses_email_and_rejects_inactive(self):
        url = reverse("users:login")
        self.assertRedirects(
            self.client.post(
                url,
                {
                    "email": "OWNER@EXAMPLE.COM",
                    "password": "Strong-pass-826",
                },
            ),
            reverse("projects:list"),
        )
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.client.logout()
        response = self.client.post(
            url,
            {
                "email": self.owner.email,
                "password": "Strong-pass-826",
            },
        )
        self.assertContains(response, "Неверный имейл или пароль")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_protected_forms_redirect_guests(self):
        for url in [
            reverse("users:edit"),
            reverse("users:change_password"),
            reverse("projects:create"),
            reverse("projects:edit", args=[self.project.pk]),
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_profile_changes_only_current_user_and_uploads_avatar(self):
        self.client.force_login(self.owner)
        with open(self.other.avatar.path, "rb") as stream:
            avatar = SimpleUploadedFile("photo.png", stream.read(), content_type="image/png")
        response = self.client.post(
            reverse("users:edit"),
            {
                "name": "Новое имя",
                "surname": self.owner.surname,
                "email": "updated@example.com",
                "phone": "89991234567",
                "github_url": "https://github.com/example",
                "about": "О себе",
                "avatar": avatar,
                "id": self.other.pk,
            },
        )
        self.assertRedirects(response, reverse("users:detail", args=[self.owner.pk]))
        self.owner.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.owner.phone, "+79991234567")
        self.assertEqual(self.owner.email, "updated@example.com")
        self.assertNotEqual(self.other.name, "Новое имя")

    def profile_data(self, **changes):
        data = {"name": self.owner.name, "surname": self.owner.surname, "email": self.owner.email}
        data.update(changes)
        return data

    def test_phone_normalization_unique_and_format_validation(self):
        self.other.phone = "+79991234567"
        self.other.save()
        for phone in ["89991234567", "+79991234567", "+1-555", "79991234567", "8abcdefghij"]:
            with self.subTest(phone=phone):
                form = ProfileForm(self.profile_data(phone=phone), instance=self.owner)
                self.assertFalse(form.is_valid())
                self.assertIn("phone", form.errors)
        form = ProfileForm(self.profile_data(phone="89991234568"), instance=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["phone"], "+79991234568")

    def test_github_domain_is_validated(self):
        for url in [
            "https://github.com.evil.example/user",
            "https://evil.example/github.com",
            "javascript:alert(1)",
            "https://github.com@evil.example/user",
        ]:
            with self.subTest(url=url):
                form = ProfileForm(self.profile_data(github_url=url), instance=self.owner)
                self.assertFalse(form.is_valid())
                self.assertIn("github_url", form.errors)

    def test_password_change_retains_session_and_logout_requires_post(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("users:change_password"),
            {
                "old_password": "Strong-pass-826",
                "new_password1": "Changed-secret-987",
                "new_password2": "Changed-secret-987",
            },
        )
        self.assertRedirects(response, reverse("users:detail", args=[self.owner.pk]))
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("Changed-secret-987"))
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(self.client.get(reverse("users:logout")).status_code, 405)
        self.client.post(reverse("users:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_create_project_sets_owner_and_membership(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "Новый проект",
                "description": "Описание",
                "status": "open",
                "owner": self.other.pk,
            },
        )
        project = Project.objects.get(name="Новый проект")
        self.assertRedirects(response, reverse("projects:detail", args=[project.pk]))
        self.assertEqual(project.owner, self.owner)
        self.assertIn(self.owner, project.participants.all())

    def test_project_form_validation_and_ownership(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "Проверка",
                "status": "invalid",
                "github_url": "https://example.com",
            },
        )
        self.assertTrue(response.context["form"].errors)
        edit_url = reverse("projects:edit", args=[self.project.pk])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(edit_url).status_code, 403)
        self.assertEqual(self.client.post(edit_url, {"name": "Подмена"}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertRedirects(
            self.client.post(
                edit_url,
                {
                    "name": "Изменён",
                    "description": "",
                    "status": "closed",
                },
            ),
            reverse("projects:detail", args=[self.project.pk]),
        )

    def test_complete_project_permissions_and_repeat(self):
        url = reverse("projects:complete", args=[self.project.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2):
            self.assertEqual(self.client.post(url).json()["project_status"], "closed")
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, "closed")

    def test_toggle_participation_and_closed_project(self):
        url = reverse("projects:toggle_participate", args=[self.project.pk])
        self.assertEqual(self.client.post(url).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(url).status_code, 400)
        self.client.force_login(self.other)
        self.assertTrue(self.client.post(url).json()["participant"])
        self.project.status = "closed"
        self.project.save()
        self.assertFalse(self.client.post(url).json()["participant"])
        self.assertEqual(self.client.post(url).status_code, 400)

    def test_skill_add_existing_new_and_repeat(self):
        self.client.force_login(self.owner)
        result = self.post_json(self.skill_url(), {"skill_id": self.skill.pk}).json()
        self.assertFalse(result["added"])
        self.assertFalse(result["created"])
        result = self.post_json(self.skill_url(), {"name": "  Django  "}).json()
        self.assertTrue(result["created"])
        self.assertTrue(result["added"])
        self.assertEqual(result["id"], result["skill_id"])
        self.assertEqual(result["name"], "Django")
        result = self.post_json(self.skill_url(), {"name": "dJANGO"}).json()
        self.assertFalse(result["created"])
        self.assertFalse(result["added"])
        self.assertEqual(Skill.objects.count(), 2)

    def test_skill_add_validates_payload(self):
        self.client.force_login(self.owner)
        for data in [
            {},
            [],
            None,
            {"name": ""},
            {"name": " "},
            {"name": "x" * 125},
            {"name": 123},
            {"skill_id": True},
            {"skill_id": -1},
            {"skill_id": "a"},
            {"skill_id": self.skill.pk, "name": "Python"},
        ]:
            with self.subTest(data=data):
                self.assertEqual(self.post_json(self.skill_url(), data).status_code, 400)
        self.assertEqual(self.post_json(self.skill_url(), {"skill_id": 99999}).status_code, 404)
        response = self.client.post(self.skill_url(), "{broken", content_type="application/json")
        self.assertEqual(response.status_code, 400)

    def test_skill_permissions_methods_and_removal_preserves_dictionary(self):
        remove = reverse("users:remove_skill", args=[self.owner.pk, self.skill.pk])
        self.assertEqual(self.post_json(self.skill_url(), {"name": "Django"}).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.post_json(self.skill_url(), {"name": "Django"}).status_code, 403)
        self.assertEqual(self.client.post(remove).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.skill_url()).status_code, 405)
        self.assertEqual(self.client.get(remove).status_code, 405)
        self.assertEqual(self.client.post(remove).status_code, 200)
        self.assertEqual(self.client.post(remove).status_code, 404)
        self.assertTrue(Skill.objects.filter(pk=self.skill.pk).exists())
        self.assertFalse(self.owner.skills.exists())

    def test_skill_autocomplete_prefix_order_limit(self):
        Skill.objects.bulk_create([Skill(name=f"Py{index:02}") for index in range(12)])
        Skill.objects.create(name="Not Python")
        result = self.client.get(reverse("users:skills"), {"q": "py"}).json()
        self.assertEqual(len(result), 10)
        self.assertEqual([skill["name"] for skill in result], [f"Py{i:02}" for i in range(10)])
        self.assertEqual(self.client.get(reverse("users:skills"), {"q": "missing"}).json(), [])

    def test_skill_filter_is_exact_and_urls_encode_special_characters(self):
        self.other.skills.add(Skill.objects.create(name="Pythonista"))
        response = self.client.get(reverse("users:list"), {"skill": "Python"})
        self.assertEqual(list(response.context["page_obj"]), [self.owner])
        self.assertEqual(response.context["active_skill"], "Python")
        special = Skill.objects.create(name="C++ & C#")
        self.owner.skills.add(special)
        response = self.client.get(reverse("users:list"), {"skill": special.name})
        self.assertContains(response, "?skill=C%2B%2B%20%26%20C%23")
        self.assertEqual(response.context["query_prefix"], urlencode({"skill": special.name}) + "&")

    def test_pagination_and_ordering_with_filter(self):
        users = []
        for index in range(13):
            user = User.objects.create_user(
                f"test{index}@example.com",
                name="Имя",
                surname="Фамилия",
                avatar="avatars/existing.png",
            )
            user.skills.add(self.skill)
            users.append(user)
        response = self.client.get(reverse("users:list"), {"skill": "Python"})
        self.assertEqual(len(response.context["page_obj"]), 12)
        self.assertEqual(response.context["page_obj"][0], users[-1])
        response = self.client.get(reverse("users:list"), {"skill": "Python", "page": 2})
        self.assertEqual(len(response.context["page_obj"]), 2)
        self.assertContains(response, "?skill=Python&amp;page=1")
        Project.objects.bulk_create(
            [Project(name=f"Проект {i}", owner=self.owner) for i in range(13)]
        )
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(len(response.context["page_obj"]), 12)
        self.assertEqual(response.context["page_obj"][0].name, "Проект 12")
        self.assertEqual(
            len(self.client.get(reverse("projects:list"), {"page": 2}).context["page_obj"]), 2
        )

    def test_ajax_csrf_cookie_and_enforcement(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        response = client.get(reverse("users:detail", args=[self.owner.pk]))
        token = response.cookies["csrftoken"].value
        self.assertEqual(client.post(self.skill_url(), {"name": "Django"}).status_code, 403)
        response = client.post(
            self.skill_url(),
            json.dumps({"name": "Django"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("projects:detail", args=[self.project.pk]))
        self.assertIn("csrftoken", response.cookies)

    def test_skill_and_email_uniqueness_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Skill.objects.create(name="pYtHoN")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.other.pk).update(email="OWNER@EXAMPLE.COM")

    def test_missing_objects_return_404(self):
        for url in ["/users/99999/", "/projects/99999/"]:
            self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post("/projects/99999/complete/").status_code, 404)
        self.assertEqual(self.client.post("/projects/99999/toggle-participate/").status_code, 404)

    def test_guest_and_other_profile_cannot_see_skill_controls(self):
        url = reverse("users:detail", args=[self.owner.pk])
        self.assertNotContains(self.client.get(url), 'id="add-skill-btn"')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(url), 'id="add-skill-btn"')
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(url), 'id="add-skill-btn"')

    def test_seed_demo_is_repeatable(self):
        with patch.dict(os.environ, {"DEMO_PASSWORD": "Demo-secret-826"}):
            call_command("seed_demo", verbosity=0)
            call_command("seed_demo", verbosity=0)
        self.assertEqual(User.objects.count(), 5)
        self.assertEqual(Project.objects.count(), 4)
        for user in User.objects.filter(
            email__in=[
                "anna@example.com",
                "ivan@example.com",
                "maria@example.com",
            ]
        ):
            self.assertTrue(user.check_password("Demo-secret-826"))
            self.assertTrue(user.owned_projects.exists())

    def test_superuser_admin_pages_and_user_creation(self):
        admin = User.objects.create_superuser(
            "admin@example.com", "Strong-pass-826", name="Админ", surname="Сайта"
        )
        self.client.force_login(admin)
        for url in [
            "/admin/",
            "/admin/users/user/",
            "/admin/users/user/add/",
            f"/admin/users/user/{self.owner.pk}/change/",
            "/admin/projects/project/",
        ]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(
            "/admin/users/user/add/",
            {
                "email": "added@example.com",
                "name": "Имя",
                "surname": "Фамилия",
                "password1": "Strong-pass-826",
                "password2": "Strong-pass-826",
                "usable_password": "true",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.get(email="added@example.com").has_usable_password())
