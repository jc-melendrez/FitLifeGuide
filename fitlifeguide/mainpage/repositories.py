from community.repositories import list_posts
from fitlifeguide.domain import exercise_text
from fitlifeguide.firestore import count_query, get_db
from tools.repositories import list_workouts_by_user


def search_posts(query, limit=5):
    needle = query.lower()
    matches = [
        post for post in list_posts()
        if post.published and (
            needle in post.title.lower() or needle in post.content.lower()
        )
    ]
    return matches[:limit]


def search_workouts(uid, query, limit=5):
    needle = query.lower()
    matches = [
        workout for workout in list_workouts_by_user(uid)
        if needle in workout.title.lower() or needle in exercise_text(workout.exercises).lower()
    ]
    return matches[:limit]


def landing_counts():
    db = get_db()
    return {
        'total_workouts': count_query(db.collection('workouts')),
        'total_meals': count_query(db.collection('meals')),
        'total_members': count_query(db.collection('users')),
    }
