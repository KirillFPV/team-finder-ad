from django.urls import path

from . import views

app_name = "projects"
urlpatterns = [
    path("list/", views.project_list, name="list"),
    path("create-project/", views.project_form, name="create"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/edit/", views.project_form, name="edit"),
    path("<int:pk>/complete/", views.complete, name="complete"),
    path("<int:pk>/toggle-participate/", views.toggle_participate, name="toggle_participate"),
]
