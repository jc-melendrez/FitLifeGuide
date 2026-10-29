from django.urls import include, path

urlpatterns = [
    path('', include('mainpage.urls')),
    path('', include('users.urls')),
    path('', include('tools.urls')),
    path('', include('community.urls')),
    path('', include('videos.urls')),
]
