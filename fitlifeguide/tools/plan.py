from collections import defaultdict
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from .models import MealPlan, MealPlanner, WeekDay, WorkoutPlan, WorkoutPlanner


MEAL_ORDER = ('breakfast', 'lunch', 'dinner', 'snack')
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

    workouts = list(
        WorkoutPlanner.objects.filter(
            user=user,
            date__range=(week_start, week_end),
        ).order_by('date', 'id')
    )
    meals = list(
        MealPlanner.objects.filter(
            user=user,
            date__range=(week_start, week_end),
        ).order_by('date', 'meal_type')
    )

    workouts_by_date = {}
    for workout in workouts:
        workouts_by_date.setdefault(workout.date, workout)

    meals_by_date = defaultdict(dict)
    for meal in meals:
        meals_by_date[meal.date][meal.meal_type] = meal

    meal_labels = dict(MealPlanner.MEAL_TYPE_CHOICES)
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        workout = workouts_by_date.get(day)
        day_meals = meals_by_date.get(day, {})
        meal_rows = [
            {
                'type': meal_type,
                'label': meal_labels[meal_type],
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

    community_meals = list(
        MealPlanner.objects.exclude(user=user)
        .select_related('user')
        .order_by('-date')[:3]
    )
    community_workouts = list(
        WorkoutPlanner.objects.exclude(user=user)
        .select_related('user')
        .order_by('-date')[:3]
    )

    return {
        'week_start': week_start,
        'week_end': week_end,
        'week_number': week_start.isocalendar().week,
        'prev_week': week_start - timedelta(days=7),
        'next_week': week_start + timedelta(days=7),
        'view': view,
        'today_in_week': today_in_week,
        'days': days,
        'community_meals': community_meals,
        'community_workouts': community_workouts,
    }


@transaction.atomic
def copy_previous_week(user, target_week_start):
    source_start = target_week_start - timedelta(days=7)
    source_end = source_start + timedelta(days=6)
    meal_plan, _ = MealPlan.objects.get_or_create(user=user)
    workout_plan, _ = WorkoutPlan.objects.get_or_create(user=user)
    copied_meals = 0
    copied_workouts = 0

    source_meals = MealPlanner.objects.filter(
        user=user,
        date__range=(source_start, source_end),
    )
    for meal in source_meals:
        target_date = meal.date + timedelta(days=7)
        _, created = MealPlanner.objects.get_or_create(
            user=user,
            date=target_date,
            meal_type=meal.meal_type,
            defaults={
                'meal_plan': meal_plan,
                'week_start': target_week_start,
                'day_of_week': WeekDay.choices[target_date.weekday()][0],
                'food_items': meal.food_items,
                'calories': meal.calories,
                'notes': meal.notes,
                'status': 'planned',
            },
        )
        if created:
            copied_meals += 1

    source_workouts = WorkoutPlanner.objects.filter(
        user=user,
        date__range=(source_start, source_end),
    )
    for workout in source_workouts:
        target_date = workout.date + timedelta(days=7)
        if WorkoutPlanner.objects.filter(user=user, date=target_date).exists():
            continue
        WorkoutPlanner.objects.create(
            user=user,
            workout_plan=workout_plan,
            date=target_date,
            week_start=target_week_start,
            day_of_week=WeekDay.choices[target_date.weekday()][0],
            title=workout.title,
            exercises=workout.exercises,
            duration_minutes=workout.duration_minutes,
            goal=workout.goal,
            notes=workout.notes,
            status='planned',
        )
        copied_workouts += 1

    return copied_meals, copied_workouts
