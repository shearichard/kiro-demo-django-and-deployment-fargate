from django.urls import path

from . import views

app_name = "survey"

urlpatterns = [
    path("<str:token>/", views.survey_view, name="survey"),
    path("<str:token>/done/", views.confirmation_view, name="confirmation"),
    path("<str:token>/results/", views.results_view, name="results"),
]
