from django.urls import path

from . import views

urlpatterns = [
    path('posts/', views.posts_view, name='posts'),
    path('posts/create/', views.create_post_view, name='create_post'),
    path('posts/<slug:slug>/', views.post_detail_view, name='post_detail'),
    path('posts/<slug:slug>/delete/', views.delete_post_view, name='delete_post'),
    path('posts/<slug:slug>/like/', views.like_post_view, name='like_post'),

    path('forum/', views.forum_list_view, name='forum_list'),
    path('forum/<slug:slug>/', views.forum_threads_view, name='forum_threads'),
    path('forum/<slug:slug>/create/', views.thread_create_view, name='thread_create'),
    path('thread/<slug:slug>/', views.thread_detail_view, name='thread_detail'),
    path('thread/<slug:slug>/delete/', views.delete_thread_view, name='delete_thread'),
    path('thread/<slug:slug>/like/', views.like_thread_view, name='like_thread'),
    path('forum-post/<str:post_id>/delete/', views.delete_forum_post_view, name='delete_forum_post'),
    path('forum-post/<str:post_id>/like/', views.like_forum_post_view, name='like_forum_post'),

    path('forum-post/<str:post_id>/comment/', views.add_comment_view, name='add_comment'),
    path('forum-comment/<str:comment_id>/delete/', views.delete_comment_view, name='delete_comment'),
    path('forum-comment/<str:comment_id>/like/', views.like_comment_view, name='like_comment'),
]
