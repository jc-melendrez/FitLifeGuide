from django.shortcuts import render, redirect
from django.db.models import Q
from django.contrib.auth.models import User
from community.models import BlogPost
from tools.models import MealPlanner, WorkoutPlanner
from videos.views import videos_views

def home(request):
    query = request.GET.get('q')
    if query:
        # Search in blog posts
        posts = BlogPost.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query),
            published=True
        ).select_related('author')[:5]

        # Search only the signed-in user's workouts
        workouts = WorkoutPlanner.objects.none()
        if request.user.is_authenticated:
            workouts = WorkoutPlanner.objects.filter(
                Q(title__icontains=query) |
                Q(exercises__icontains=query),
                user=request.user,
            ).order_by('-date')[:5]

        # Get video results
        videos = videos_views(request, search_query=query, max_results=6)

        return render(request, 'mainpage/search_results.html', {
            'query': query,
            'posts': posts,
            'workouts': workouts,
            'videos': videos,
        })

    return render(request, 'mainpage/home.html')

def welcome(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'mainpage/landingpage.html', {
        'total_workouts': WorkoutPlanner.objects.count(),
        'total_meals': MealPlanner.objects.count(),
        'total_members': User.objects.count(),
    })

def about(request):
    return render(request, 'mainpage/about.html')

def contact(request):
    return render(request, 'mainpage/contact.html')
