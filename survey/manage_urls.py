from django.urls import path

from survey import manage_views

app_name = 'manage'

urlpatterns = [
    path('surveys/', manage_views.survey_list_view, name='survey_list'),
    path('surveys/new/', manage_views.survey_create_view, name='survey_create'),
    path('surveys/<int:pk>/', manage_views.survey_detail_view, name='survey_detail'),
    path('surveys/<int:pk>/questions/add/', manage_views.question_add_view, name='question_add'),
    path('surveys/<int:pk>/tokens/create/', manage_views.token_create_view, name='token_create'),
]
