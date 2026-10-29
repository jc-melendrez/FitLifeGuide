from django.utils import timezone

from fitlifeguide.domain import VideoHistory, parse_datetime
from fitlifeguide.firestore import count_query, get_db


def _from_doc(doc):
    data = doc.to_dict() or {}
    return VideoHistory(
        id=doc.id,
        user_id=data.get('user_id', ''),
        video_id=data.get('video_id', ''),
        title=data.get('title', ''),
        thumbnail_url=data.get('thumbnail_url', ''),
        channel_title=data.get('channel_title', ''),
        duration=data.get('duration', ''),
        viewed_at=parse_datetime(data.get('viewed_at')) or timezone.now(),
    )


def add_video_history(user, video_id, title, thumbnail_url, channel_title, duration):
    doc_ref = get_db().collection('video_history').document()
    doc_ref.set({
        'user_id': user.id,
        'video_id': video_id,
        'title': title,
        'thumbnail_url': thumbnail_url,
        'channel_title': channel_title,
        'duration': duration,
        'viewed_at': timezone.now(),
    })
    return _from_doc(doc_ref.get())


def list_video_history(uid, limit=None):
    videos = [
        _from_doc(doc)
        for doc in get_db().collection('video_history').where('user_id', '==', uid).stream()
    ]
    videos.sort(key=lambda video: video.viewed_at, reverse=True)
    return videos[:limit] if limit else videos


def get_resume_video(uid):
    videos = list_video_history(uid, limit=1)
    return videos[0] if videos else None


def count_videos(uid):
    return count_query(get_db().collection('video_history').where('user_id', '==', uid))
