# from django.shortcuts import render
# from django.conf import settings
# import requests

# def videos_views(request):
#     url = 'https://www.googleapis.com/youtube/v3/search'
#     video_url = 'https://www.googleapis.com/youtube/v3/videos'


#     search_params = {
#         'part' : 'snippet',
#         'q' : 'workout videos',
#         'key' : settings.YOUTUBE_DATA_API_KEY,
#         'type' : 'video',
#         'maxResults' : 15
#     }

#     video_ids = []
#     r = requests.get(url, params=search_params)

#     results = r.json()['items']

#     for result in results:
#         video_ids.append(result['id']['videoId'])

#     video_params = {
#         'part' : 'snippet,contentDetails',
#         'key' : settings.YOUTUBE_DATA_API_KEY,
#         'id' : ','.join(video_ids)
#     }
    
#     r = requests.get(video_url, params=video_params)
    
#     results = r.json()['items']

#     for result in results:
#         # print(result['title'])
#         print(result['id'])
#         print(result['contentDetails']['duration'])
#         print(result['thumbnails']['high']['url'])



#     return render(request, 'videos/videos.html')




from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .repositories import add_video_history
import requests
import isodate
import datetime

def format_duration(iso_duration):
    try:
        duration = isodate.parse_duration(iso_duration)
        total_seconds = int(duration.total_seconds())
        return str(datetime.timedelta(seconds=total_seconds))
    except Exception:
        return "N/A"

def videos_views(request, search_query=None, max_results=15):
    search_url = 'https://www.googleapis.com/youtube/v3/search'
    video_url = 'https://www.googleapis.com/youtube/v3/videos'

    # If there's a search query, combine it with fitness terms
    if search_query:
        search_terms = f"{search_query} workout"
    else:
        search_terms = "workout fitness exercise tutorial"

    search_params = {
        'part': 'snippet',
        'q': search_terms,
        'key': settings.YOUTUBE_DATA_API_KEY,
        'type': 'video',
        'maxResults': max_results,
        'relevanceLanguage': 'en',  # English results
        'order': 'relevance',  # Most relevant results first
    }

    try:
        search_response = requests.get(search_url, params=search_params)
        
        # Debug: Check the API response
        if not search_response.ok:
            error_msg = f"YouTube API Error: {search_response.status_code} - {search_response.text}"
            if search_query:
                return []
            return render(request, 'videos/videos.html', {'videos': [], 'error': error_msg})

        search_results = search_response.json().get('items', [])
        
        if not search_results:
            if search_query:
                return []
            return render(request, 'videos/videos.html', {'videos': [], 'error': 'No videos found'})

        video_ids = [result['id']['videoId'] for result in search_results]

        video_params = {
            'part': 'snippet,contentDetails,statistics',
            'key': settings.YOUTUBE_DATA_API_KEY,
            'id': ','.join(video_ids)
        }

        video_response = requests.get(video_url, params=video_params)
        
        # Debug: Check the video details API response
        if not video_response.ok:
            error_msg = f"YouTube Video API Error: {video_response.status_code} - {video_response.text}"
            if search_query:
                return []
            return render(request, 'videos/videos.html', {'videos': [], 'error': error_msg})

        video_results = video_response.json().get('items', [])

        videos = []
        for result in video_results:
            snippet = result.get('snippet', {})
            content_details = result.get('contentDetails', {})
            statistics = result.get('statistics', {})

            try:
                duration = isodate.parse_duration(content_details.get('duration', 'PT0S'))
                # Skip videos longer than 2 hours
                if duration.total_seconds() > 7200:
                    continue
            except:
                continue

            # Skip videos with extremely low view counts (likely spam)
            try:
                view_count = int(statistics.get('viewCount', 0))
                if view_count < 100:  # Lowered threshold
                    continue
            except:
                view_count = 0

            # Check if title contains workout-related terms
            title = snippet.get('title', '').lower()
            description = snippet.get('description', '').lower()
            relevant_terms = ['workout', 'exercise', 'fitness', 'training', 'gym', 'cardio', 
                            'strength', 'hiit', 'yoga', 'bodyweight', 'stretching', 
                            'muscle', 'weight', 'body', 'health', 'sport']
            
            # Make relevance check less strict - only check title
            is_relevant = any(term in title for term in relevant_terms)
            if not is_relevant and not search_query:  # Only apply relevance check for non-search results
                continue

            readable_duration = format_duration(content_details.get('duration'))

            video = {
                'id': result.get('id'),
                'title': snippet.get('title'),
                'thumbnail': snippet.get('thumbnails', {}).get('high', {}).get('url'),
                'duration': readable_duration,
                'channel_title': snippet.get('channelTitle'),
                'view_count': f"{view_count:,}",
                'description': snippet.get('description', '')[:200]  # Limit description length
            }
            videos.append(video)

        if search_query:
            return videos[:max_results]  # Ensure we don't return more than requested
        return render(request, 'videos/videos.html', {'videos': videos})

    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if search_query:
            return []
        return render(request, 'videos/videos.html', {'videos': [], 'error': error_msg})

@login_required
def track_video_click(request, video_id):
    if request.method == 'POST':
        # Get video details from the hidden form fields
        title = request.POST.get('title')
        thumbnail_url = request.POST.get('thumbnail')
        channel_title = request.POST.get('channel_title')
        duration = request.POST.get('duration')

        add_video_history(
            request.user,
            video_id,
            title,
            thumbnail_url,
            channel_title,
            duration,
        )

        # Redirect to YouTube video
        return redirect(f'https://www.youtube.com/watch?v={video_id}')
    
    return redirect('videos')
