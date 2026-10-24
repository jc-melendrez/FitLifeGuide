from django.shortcuts import render, redirect
from django.db.models import Q
from community.models import BlogPost
from tools.models import WorkoutPlanner
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

        # Search in workouts
        workouts = WorkoutPlanner.objects.filter(
            Q(title__icontains=query) |
            Q(exercises__icontains=query)
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
        return redirect('home')  # or use the name of the URL pattern
    return render(request, 'mainpage/landingpage.html')

def about(request):
    return render(request, 'mainpage/about.html')

def contact(request):
    return render(request, 'mainpage/contact.html')
