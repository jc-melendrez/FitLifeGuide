from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('auth/firebase/', views.firebase_callback, name='firebase_callback'),
    path('auth/send-link/', views.send_sign_in_link, name='send_sign_in_link'),
    path('auth/complete-profile/', views.complete_profile, name='complete_profile'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.profile, name='edit_profile'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
    path('update-status/', views.update_status, name='update_status'),
]
