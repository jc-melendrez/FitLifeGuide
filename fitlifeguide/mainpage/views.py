from django.shortcuts import redirect, render

from tools.activity import get_today_context
from videos.views import videos_views

from .repositories import landing_counts, search_posts, search_workouts


def home(request):
    query = request.GET.get('q')
    if query:
        workouts = []
        if request.user.is_authenticated:
            workouts = search_workouts(request.user.id, query, limit=5)
        videos = videos_views(request, search_query=query, max_results=6)
        return render(request, 'mainpage/search_results.html', {
            'query': query,
            'posts': search_posts(query, limit=5),
            'workouts': workouts,
            'videos': videos,
        })

    if not request.user.is_authenticated:
        return redirect('welcome')

    return render(request, 'mainpage/home.html', get_today_context(request.user))


def welcome(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'mainpage/landingpage.html', landing_counts())


def about(request):
    return render(request, 'mainpage/about.html')


def contact(request):
    return render(request, 'mainpage/contact.html')
