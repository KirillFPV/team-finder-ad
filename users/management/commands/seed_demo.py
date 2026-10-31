import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from projects.models import Project
from users.models import Skill, User


class Command(BaseCommand):
    help = "Создаёт демонстрационных пользователей и проекты, не меняя существующие пароли."

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get("DEMO_PASSWORD")
        if not password or len(password) < 8:
            raise CommandError("Задайте DEMO_PASSWORD длиной не менее 8 символов.")
        examples = [
            (
                "anna@example.com",
                "Анна",
                "Иванова",
                ["Python", "Django"],
                "Планировщик путешествий",
                "Помогаем путешественникам составлять маршруты.",
            ),
            (
                "ivan@example.com",
                "Иван",
                "Петров",
                ["JavaScript", "React"],
                "Книжный клуб",
                "Сервис для обсуждения книг и поиска единомышленников.",
            ),
            (
                "maria@example.com",
                "Мария",
                "Смирнова",
                ["Python", "PostgreSQL", "C++"],
                "Городские события",
                "Карта интересных событий и мероприятий города.",
            ),
        ]
        for email, name, surname, skills, title, description in examples:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "name": name,
                    "surname": surname,
                    "about": "Ищу команду для интересного pet-проекта.",
                },
            )
            if created:
                user.set_password(password)
                user.save(update_fields=["password"])
            for skill_name in skills:
                skill, _ = Skill.objects.get_or_create(
                    name__iexact=skill_name, defaults={"name": skill_name}
                )
                user.skills.add(skill)
            project, _ = Project.objects.get_or_create(
                owner=user,
                name=title,
                defaults={"description": description},
            )
            project.participants.add(user)
        self.stdout.write(self.style.SUCCESS("Демоданные готовы: 3 пользователя и 3 проекта."))
