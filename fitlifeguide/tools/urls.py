from django.urls import path
from . import views

app_name = 'tools'

urlpatterns = [
    path('plan/', views.plan, name='plan'),
    path('plan/copy-last-week/', views.copy_last_week, name='copy_last_week'),
    path('meal-planner/', views.meal_planner, name='meal_planner'),
    path('meal-planner/add/', views.add_meal, name='add_meal'),
    path('meal-planner/edit/<str:meal_id>/', views.edit_meal, name='edit_meal'),
    path('meal-planner/delete/<str:meal_id>/', views.delete_meal, name='delete_meal'),
    path('meal-planner/update-status/<str:meal_id>/', views.update_meal_status, name='update_meal_status'),
    
    path('workout-hub/', views.workout_hub, name='workout_hub'),
    path('add-workout/', views.add_workout, name='add_workout'),
    path('edit-workout/<str:workout_id>/', views.edit_workout, name='edit_workout'),
    path('delete-workout/<str:workout_id>/', views.delete_workout, name='delete_workout'),
    path('update-workout-status/<str:workout_id>/', views.update_workout_status, name='update_workout_status'),
    path('workout/<str:workout_id>/', views.workout_detail, name='workout_detail'),
    path('workout/<str:workout_id>/complete/', views.workout_complete, name='workout_complete'),
    path('skip-today/', views.skip_today, name='skip_today'),
]
