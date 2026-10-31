from datetime import timedelta

from django.utils import timezone

from fitlifeguide.domain import (
    MEAL_TYPES,
    WEEKDAYS,
    Author,
    Meal,
    Workout,
    normalize_exercises,
    parse_date,
)
from fitlifeguide.firestore import count_query, get_db

MEAL_ORDER = ('breakfast', 'lunch', 'dinner', 'snack')


def _now():
    return timezone.now()


def _meal_from_doc(doc):
    data = doc.to_dict() or {}
    return Meal(
        id=doc.id,
        date=parse_date(data.get('date')),
        week_start=parse_date(data.get('week_start')),
        day_of_week=data.get('day_of_week', ''),
        meal_type=data.get('meal_type', ''),
        food_items=data.get('food_items', ''),
        calories=data.get('calories'),
        status=data.get('status', 'planned'),
        notes=data.get('notes', ''),
        user=Author(
            id=data.get('user_id', ''),
            username=data.get('username', ''),
            avatar_url=data.get('avatar_url', ''),
        ) if data.get('username') else None,
    )


def _workout_from_doc(doc):
    data = doc.to_dict() or {}
    return Workout(
        id=doc.id,
        date=parse_date(data.get('date')),
        week_start=parse_date(data.get('week_start')),
        day_of_week=data.get('day_of_week', ''),
        title=data.get('title', ''),
        exercises=normalize_exercises(data.get('exercises')),
        duration_minutes=data.get('duration_minutes'),
        goal=data.get('goal', ''),
        status=data.get('status', 'planned'),
        notes=data.get('notes', ''),
        user=Author(
            id=data.get('user_id', ''),
            username=data.get('username', ''),
            avatar_url=data.get('avatar_url', ''),
        ) if data.get('username') else None,
    )


def _meal_sort_key(meal):
    order = MEAL_ORDER.index(meal.meal_type) if meal.meal_type in MEAL_ORDER else 99
    return (meal.date or timezone.localdate(), order)


def _workout_sort_key(workout):
    return (workout.date or timezone.localdate(), workout.id)


def list_meals_by_user(uid, limit=None):
    meals = [_meal_from_doc(doc) for doc in get_db().collection('meals').where('user_id', '==', uid).stream()]
    meals.sort(key=_meal_sort_key, reverse=True)
    return meals[:limit] if limit else meals


def list_workouts_by_user(uid, limit=None):
    workouts = [
        _workout_from_doc(doc)
        for doc in get_db().collection('workouts').where('user_id', '==', uid).stream()
    ]
    workouts.sort(key=_workout_sort_key, reverse=True)
    return workouts[:limit] if limit else workouts


def list_meals_between(uid, start, end):
    meals = [
        meal for meal in list_meals_by_user(uid)
        if meal.date and start <= meal.date <= end
    ]
    meals.sort(key=_meal_sort_key)
    return meals


def list_workouts_between(uid, start, end):
    workouts = [
        workout for workout in list_workouts_by_user(uid)
        if workout.date and start <= workout.date <= end
    ]
    workouts.sort(key=_workout_sort_key)
    return workouts


def count_meals_by_user(uid):
    return count_query(get_db().collection('meals').where('user_id', '==', uid))


def count_workouts_by_user(uid):
    return count_query(get_db().collection('workouts').where('user_id', '==', uid))


def get_meal(meal_id, uid=None):
    snap = get_db().collection('meals').document(meal_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    if uid and data.get('user_id') != uid:
        return None
    return _meal_from_doc(snap)


def get_workout(workout_id, uid=None):
    snap = get_db().collection('workouts').document(workout_id).get()
    if not snap.exists:
        return None
    data = snap.to_dict() or {}
    if uid and data.get('user_id') != uid:
        return None
    return _workout_from_doc(snap)


def _day_code(value):
    return WEEKDAYS[value.weekday()][0]


def add_meal(user, meal_date, meal_type, food_items, calories=None, notes=''):
    db = get_db()
    doc_id = f'{user.id}_{meal_date.isoformat()}_{meal_type}'
    doc_ref = db.collection('meals').document(doc_id)
    doc_ref.set({
        'user_id': user.id,
        'username': user.username,
        'avatar_url': user.profile.avatar_url,
        'date': meal_date.isoformat(),
        'week_start': (meal_date - timedelta(days=meal_date.weekday())).isoformat(),
        'day_of_week': _day_code(meal_date),
        'meal_type': meal_type,
        'food_items': food_items,
        'calories': calories,
        'status': 'planned',
        'notes': notes,
        'updated_at': _now(),
    }, merge=True)
    return _meal_from_doc(doc_ref.get())


def update_meal(meal, food_items, calories=None, notes=''):
    doc_ref = get_db().collection('meals').document(meal.id)
    doc_ref.update({
        'food_items': food_items,
        'calories': calories,
        'notes': notes,
        'updated_at': _now(),
    })
    return _meal_from_doc(doc_ref.get())


def delete_meal(meal_id):
    get_db().collection('meals').document(meal_id).delete()


def set_meal_status(meal_id, status):
    get_db().collection('meals').document(meal_id).update({'status': status, 'updated_at': _now()})


def add_workout(user, workout_date, title, exercises=None, duration_minutes=None, goal='', notes=''):
    db = get_db()
    doc_ref = db.collection('workouts').document()
    doc_ref.set({
        'user_id': user.id,
        'username': user.username,
        'avatar_url': user.profile.avatar_url,
        'date': workout_date.isoformat(),
        'week_start': (workout_date - timedelta(days=workout_date.weekday())).isoformat(),
        'day_of_week': _day_code(workout_date),
        'title': title,
        'exercises': normalize_exercises(exercises),
        'duration_minutes': duration_minutes,
        'goal': goal,
        'status': 'planned',
        'notes': notes,
        'created_at': _now(),
        'updated_at': _now(),
    })
    return _workout_from_doc(doc_ref.get())


def update_workout(workout, workout_date, title, exercises=None, duration_minutes=None, goal='', notes=''):
    doc_ref = get_db().collection('workouts').document(workout.id)
    doc_ref.update({
        'date': workout_date.isoformat(),
        'week_start': (workout_date - timedelta(days=workout_date.weekday())).isoformat(),
        'day_of_week': _day_code(workout_date),
        'title': title,
        'exercises': normalize_exercises(exercises),
        'duration_minutes': duration_minutes,
        'goal': goal,
        'notes': notes,
        'updated_at': _now(),
    })
    return _workout_from_doc(doc_ref.get())


def delete_workout(workout_id):
    get_db().collection('workouts').document(workout_id).delete()


def set_workout_status(workout_id, status):
    get_db().collection('workouts').document(workout_id).update({'status': status, 'updated_at': _now()})


def skip_today(uid):
    today = timezone.localdate()
    updated = 0
    for doc in get_db().collection('workouts').where('user_id', '==', uid).stream():
        data = doc.to_dict() or {}
        if parse_date(data.get('date')) == today and data.get('status') == 'planned':
            doc.reference.update({'status': 'missed', 'updated_at': _now()})
            updated += 1
    return updated


def community_meals(exclude_uid, limit=3):
    meals = [
        _meal_from_doc(doc)
        for doc in get_db().collection('meals').stream()
        if (doc.to_dict() or {}).get('user_id') != exclude_uid
    ]
    meals.sort(key=_meal_sort_key, reverse=True)
    return meals[:limit]


def community_workouts(exclude_uid, limit=3):
    workouts = [
        _workout_from_doc(doc)
        for doc in get_db().collection('workouts').stream()
        if (doc.to_dict() or {}).get('user_id') != exclude_uid
    ]
    workouts.sort(key=_workout_sort_key, reverse=True)
    return workouts[:limit]


def copy_previous_week(user, target_week_start):
    source_start = target_week_start - timedelta(days=7)
    source_end = source_start + timedelta(days=6)
    copied_meals = 0
    copied_workouts = 0

    for meal in list_meals_between(user.id, source_start, source_end):
        target_date = meal.date + timedelta(days=7)
        target_id = f'{user.id}_{target_date.isoformat()}_{meal.meal_type}'
        target_ref = get_db().collection('meals').document(target_id)
        if target_ref.get().exists:
            continue
        add_meal(
            user,
            target_date,
            meal.meal_type,
            meal.food_items,
            meal.calories,
            meal.notes,
        )
        copied_meals += 1

    target_workouts = list_workouts_between(user.id, target_week_start, target_week_start + timedelta(days=6))
    target_dates = {workout.date for workout in target_workouts}
    for workout in list_workouts_between(user.id, source_start, source_end):
        target_date = workout.date + timedelta(days=7)
        if target_date in target_dates:
            continue
        add_workout(
            user,
            target_date,
            workout.title,
            workout.exercises,
            workout.duration_minutes,
            workout.goal,
            workout.notes,
        )
        target_dates.add(target_date)
        copied_workouts += 1

    return copied_meals, copied_workouts
