from datetime import timedelta

from django.utils import timezone

from videos.models import VideoHistory

from .models import MealPlanner, WorkoutPlanner


WEEKLY_WORKOUT_GOAL = 5
MEAL_ORDER = ('breakfast', 'lunch', 'dinner')


def _monday(day):
    return day - timedelta(days=day.weekday())


def _greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return 'Good morning'
    if hour < 18:
        return 'Good afternoon'
    return 'Good evening'


def get_today_context(user, day=None):
    day = day or timezone.localdate()
    week_start = _monday(day)
    week_end = week_start + timedelta(days=6)

    workout_list = list(
        WorkoutPlanner.objects.filter(
            user=user,
            date__range=(week_start, week_end),
        ).order_by('date', 'id')
    )
    meal_list = list(
        MealPlanner.objects.filter(
            user=user,
            date__range=(week_start, week_end),
        ).order_by('date', 'meal_type')
    )

    today_workout = next((workout for workout in workout_list if workout.date == day), None)
    today_meals = {meal.meal_type: meal for meal in meal_list if meal.date == day}

    meal_types = list(MEAL_ORDER)
    if 'snack' in today_meals:
        meal_types.append('snack')

    meal_labels = dict(MealPlanner.MEAL_TYPE_CHOICES)
    meal_rows = []
    for meal_type in meal_types:
        meal = today_meals.get(meal_type)
        meal_rows.append({
            'label': meal_labels[meal_type],
            'meal': meal,
            'status': meal.get_status_display() if meal else 'Not planned',
        })

    workouts_by_date = {}
    for workout in workout_list:
        workouts_by_date.setdefault(workout.date, workout)

    week_days = []
    for offset in range(7):
        current_day = week_start + timedelta(days=offset)
        week_days.append({
            'date': current_day,
            'label': current_day.strftime('%a'),
            'workout': workouts_by_date.get(current_day),
            'is_today': current_day == day,
        })

    completed_workouts = [
        workout for workout in workout_list if workout.status == 'completed'
    ]
    completed_dates = {workout.date for workout in completed_workouts}
    completed_dates.update(
        meal.date for meal in meal_list if meal.status == 'eaten'
    )

    streak = 0
    cursor = day
    while cursor in completed_dates:
        streak += 1
        cursor -= timedelta(days=1)

    circumference = 2 * 3.141592653589793 * 42
    ring_ratio = min(1, len(completed_workouts) / WEEKLY_WORKOUT_GOAL)

    return {
        'today': day,
        'week_number': day.isocalendar().week,
        'greeting': _greeting(),
        'today_workout': today_workout,
        'meal_rows': meal_rows,
        'week_days': week_days,
        'week_workouts': len(completed_workouts),
        'week_goal': WEEKLY_WORKOUT_GOAL,
        'streak': streak,
        'ring_dash': f'{circumference * ring_ratio:.1f} {circumference:.1f}',
        'resume_video': VideoHistory.objects.filter(user=user).first(),
    }
