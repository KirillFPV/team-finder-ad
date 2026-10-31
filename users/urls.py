from django.urls import path

from . import views

app_name = "users"
urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.sign_in, name="login"),
    path("logout/", views.sign_out, name="logout"),
    path("list/", views.participants, name="list"),
    path("edit-profile/", views.edit_profile, name="edit"),
    path("change-password/", views.change_password, name="change_password"),
    path("skills/", views.skills, name="skills"),
    path("<int:pk>/", views.profile, name="detail"),
    path("<int:pk>/skills/add/", views.add_skill, name="add_skill"),
    path("<int:pk>/skills/<int:skill_id>/remove/", views.remove_skill, name="remove_skill"),
]
