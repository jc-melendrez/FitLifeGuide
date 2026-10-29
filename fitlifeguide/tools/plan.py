from collections import defaultdict
from datetime import datetime, timedelta

from django.utils import timezone

from fitlifeguide.domain import MEAL_TYPES, label_for

from .repositories import (
    MEAL_ORDER,
    community_meals,
    community_workouts,
    copy_previous_week as copy_week,
    list_meals_between,
    list_workouts_between,
)

PLAN_VIEWS = ('both', 'meals', 'workouts')


def parse_week(value=None):
    if value:
        try:
            day = datetime.strptime(value, '%Y-%m-%d').date()
        except (TypeError, ValueError):
            day = timezone.localdate()
    else:
        day = timezone.localdate()
    return day - timedelta(days=day.weekday())


def get_plan_context(user, week_start, view='both'):
    if view not in PLAN_VIEWS:
        view = 'both'

    week_end = week_start + timedelta(days=6)
    today = timezone.localdate()
    today_in_week = week_start <= today <= week_end

    workouts = list_workouts_between(user.id, week_start, week_end)
    meals = list_meals_between(user.id, week_start, week_end)

    workouts_by_date = {}
    for workout in workouts:
        workouts_by_date.setdefault(workout.date, workout)

    meals_by_date = defaultdict(dict)
    for meal in meals:
        meals_by_date[meal.date][meal.meal_type] = meal

    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        workout = workouts_by_date.get(day)
        day_meals = meals_by_date.get(day, {})
        meal_rows = [
            {
                'type': meal_type,
                'label': label_for(MEAL_TYPES, meal_type),
                'meal': day_meals.get(meal_type),
            }
            for meal_type in MEAL_ORDER
        ]
        has_entries = bool(workout or day_meals)
        has_done = bool(
            (workout and workout.status == 'completed')
            or any(meal.status == 'eaten' for meal in day_meals.values())
        )
        if day == today:
            status = 'Today'
        elif day < today:
            if has_done:
                status = 'Done'
            elif has_entries:
                status = 'Missed'
            else:
                status = 'Rest'
        else:
            status = 'Planned' if has_entries else 'Rest'

        if workout is None:
            workout_status = 'Rest'
        elif workout.status == 'completed':
            workout_status = 'Done'
        elif workout.status == 'missed' or day < today:
            workout_status = 'Missed'
        else:
            workout_status = 'Planned'

        days.append({
            'date': day,
            'label': day.strftime('%a'),
            'workout': workout,
            'meals': meal_rows,
            'status': status,
            'workout_status': workout_status,
            'expanded': today_in_week and day == today,
            'is_today': day == today,
        })

    return {
        'week_start': week_start,
        'week_end': week_end,
        'week_number': week_start.isocalendar().week,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
        'view': view,
        'today_in_week': today_in_week,
        'days': days,
        'community_meals': community_meals(user.id, limit=3),
        'community_workouts': community_workouts(user.id, limit=3),
    }


def copy_previous_week(user, target_week_start):
    return copy_week(user, target_week_start)
