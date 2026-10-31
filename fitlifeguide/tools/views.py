from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from fitlifeguide.domain import MEAL_STATUS, MEAL_TYPES, WEEKDAYS, label_for

from .activity import WEEKLY_WORKOUT_GOAL, get_activity_stats
from .forms import MealPlannerForm, WorkoutPlanForm
from .plan import PLAN_VIEWS, copy_previous_week, get_plan_context, parse_week
from .repositories import (
    MEAL_ORDER,
    add_meal as create_meal,
    add_workout as create_workout,
    community_meals,
    community_workouts,
    delete_meal as remove_meal,
    delete_workout as remove_workout,
    get_meal,
    get_workout,
    list_meals_between,
    list_workouts_between,
    set_meal_status,
    set_workout_status,
    skip_today as mark_today_missed,
    update_meal,
    update_workout,
)


def _next_url(request):
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        {request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return None


@login_required
def plan(request):
    week_start = parse_week(request.GET.get('week'))
    view = request.GET.get('view', 'both')
    return render(request, 'tools/plan.html', get_plan_context(request.user, week_start, view))


@login_required
@require_POST
def copy_last_week(request):
    week_start = parse_week(request.POST.get('week'))
    view = request.POST.get('view', 'both')
    if view not in PLAN_VIEWS:
        view = 'both'
    copied_meals, copied_workouts = copy_previous_week(request.user, week_start)
    if copied_meals or copied_workouts:
        messages.success(
            request,
            f'Copied from last week: {copied_meals} meals, {copied_workouts} workouts.',
        )
    else:
        messages.info(request, 'Nothing new to copy from last week.')
    return redirect(f"{reverse('tools:plan')}?week={week_start:%Y-%m-%d}&view={view}")


def _week_start_from_request(request):
    week_start = parse_week(request.GET.get('week'))
    direction = request.GET.get('direction')
    if direction == 'next':
        week_start += timedelta(days=7)
    elif direction == 'prev':
        week_start -= timedelta(days=7)
    return week_start


@login_required
def meal_planner(request):
    week_start = _week_start_from_request(request)
    week_end = week_start + timedelta(days=6)
    meals = list_meals_between(request.user.id, week_start, week_end)
    week_plan = {}
    for index, (day_code, day_name) in enumerate(WEEKDAYS):
        week_plan[day_code] = {
            'date': week_start + timedelta(days=index),
            'meals': {meal_type: None for meal_type in MEAL_ORDER},
        }
    for meal in meals:
        if meal.day_of_week in week_plan and meal.meal_type in MEAL_ORDER:
            week_plan[meal.day_of_week]['meals'][meal.meal_type] = meal

    return render(request, 'tools/meal_planner.html', {
        'meal_plan': {'name': 'My Meal Plan'},
        'week_plan': week_plan,
        'week_start': week_start,
        'week_end': week_end,
        'other_meals': community_meals(request.user.id, limit=3),
    })


@login_required
def add_meal(request, date=None, meal_type=None):
    date = request.GET.get('date')
    meal_type = request.GET.get('meal_type')
    if not date or not meal_type:
        messages.error(request, 'Date and meal type are required.')
        return redirect('tools:meal_planner')

    try:
        meal_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('tools:meal_planner')

    next_url = _next_url(request)
    if request.method == 'POST':
        form = MealPlannerForm(request.POST)
        if form.is_valid():
            create_meal(
                request.user,
                meal_date,
                meal_type,
                form.cleaned_data['food_items'],
                form.cleaned_data.get('calories'),
                form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Meal added successfully!')
            return redirect(next_url or 'tools:meal_planner')
    else:
        form = MealPlannerForm()

    return render(request, 'tools/add_meal.html', {
        'form': form,
        'date': meal_date,
        'day_name': WEEKDAYS[meal_date.weekday()][1],
        'meal_type': label_for(MEAL_TYPES, meal_type),
        'next': next_url or '',
    })


@login_required
def edit_meal(request, meal_id):
    meal = get_meal(meal_id, request.user.id)
    if not meal:
        raise Http404('Meal not found')
    next_url = _next_url(request)

    if request.method == 'POST':
        form = MealPlannerForm(request.POST)
        if form.is_valid():
            update_meal(
                meal,
                form.cleaned_data['food_items'],
                form.cleaned_data.get('calories'),
                form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Meal updated successfully!')
            return redirect(next_url or 'tools:meal_planner')
    else:
        form = MealPlannerForm(initial={
            'food_items': meal.food_items,
            'calories': meal.calories,
            'notes': meal.notes,
        })

    return render(request, 'tools/add_meal.html', {
        'form': form,
        'meal': meal,
        'date': meal.date,
        'day_name': WEEKDAYS[meal.date.weekday()][1],
        'meal_type': meal.get_meal_type_display,
        'next': next_url or '',
    })


@login_required
def delete_meal(request, meal_id):
    meal = get_meal(meal_id, request.user.id)
    if not meal:
        raise Http404('Meal not found')
    if request.method == 'POST':
        remove_meal(meal.id)
        messages.success(request, 'Meal deleted successfully!')
    return redirect('tools:meal_planner')


@login_required
def update_meal_status(request, meal_id):
    meal = get_meal(meal_id, request.user.id)
    if not meal:
        raise Http404('Meal not found')
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(MEAL_STATUS):
            set_meal_status(meal.id, status)
            messages.success(request, f'Meal marked as {status}!')
    return redirect('tools:meal_planner')


@login_required
def workout_hub(request):
    week_start = _week_start_from_request(request)
    week_end = week_start + timedelta(days=6)
    user_workouts = list_workouts_between(request.user.id, week_start, week_end)
    workouts_by_date = {workout.date: workout for workout in user_workouts}
    week_plan = {}
    for index, (_, day_name) in enumerate(WEEKDAYS):
        current_date = week_start + timedelta(days=index)
        week_plan[day_name] = {
            'date': current_date,
            'workout': workouts_by_date.get(current_date),
        }

    return render(request, 'tools/workout_hub.html', {
        'week_plan': week_plan,
        'other_workouts': community_workouts(request.user.id, limit=3),
        'week_start': week_start,
        'week_end': week_end,
    })


@login_required
def add_workout(request):
    date_str = request.GET.get('date')
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()
    except ValueError:
        selected_date = timezone.localdate()

    next_url = _next_url(request)
    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST)
        if form.is_valid():
            create_workout(
                request.user,
                form.cleaned_data['date'],
                form.cleaned_data['title'],
                form.cleaned_data.get('exercises', ''),
                form.cleaned_data.get('duration_minutes'),
                form.cleaned_data.get('goal', ''),
                form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Workout added successfully!')
            return redirect(next_url or 'tools:workout_hub')
    else:
        form = WorkoutPlanForm(initial={'date': selected_date})

    return render(request, 'tools/add_workout.html', {
        'form': form,
        'selected_date': selected_date,
        'next': next_url or '',
    })


@login_required
def edit_workout(request, workout_id):
    workout = get_workout(workout_id, request.user.id)
    if not workout:
        raise Http404('Workout not found')
    next_url = _next_url(request)

    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST)
        if form.is_valid():
            update_workout(
                workout,
                form.cleaned_data['date'],
                form.cleaned_data['title'],
                form.cleaned_data.get('exercises', ''),
                form.cleaned_data.get('duration_minutes'),
                form.cleaned_data.get('goal', ''),
                form.cleaned_data.get('notes', ''),
            )
            messages.success(request, 'Workout updated successfully!')
            return redirect(next_url or 'tools:workout_hub')
    else:
        form = WorkoutPlanForm(initial={
            'date': workout.date,
            'title': workout.title,
            'exercises': workout.exercises,
            'duration_minutes': workout.duration_minutes,
            'goal': workout.goal,
            'notes': workout.notes,
        })

    return render(request, 'tools/edit_workout.html', {
        'form': form,
        'workout': workout,
        'next': next_url or '',
    })


@login_required
def delete_workout(request, workout_id):
    workout = get_workout(workout_id, request.user.id)
    if not workout:
        raise Http404('Workout not found')
    if request.method == 'POST':
        remove_workout(workout.id)
        messages.success(request, 'Workout deleted successfully!')
    return redirect('tools:workout_hub')


@login_required
def update_workout_status(request, workout_id):
    workout = get_workout(workout_id, request.user.id)
    if not workout:
        raise Http404('Workout not found')
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in ('planned', 'completed', 'missed'):
            set_workout_status(workout.id, status)
            messages.success(request, f'Workout marked as {status}!')
            if status == 'completed':
                return redirect('tools:workout_complete', workout_id=workout.id)
    return redirect('tools:workout_hub')


@login_required
def workout_complete(request, workout_id):
    workout = get_workout(workout_id, request.user.id)
    if not workout:
        raise Http404('Workout not found')
    day = workout.date or timezone.localdate()
    week_start = workout.week_start or (day - timedelta(days=day.weekday()))
    week_end = week_start + timedelta(days=6)
    workouts = list_workouts_between(request.user.id, week_start, week_end)
    next_workout = next(
        (item for item in workouts if item.date > day and item.status == 'planned'),
        None,
    )
    return render(request, 'tools/workout_complete.html', {
        'workout': workout,
        'week_workouts': sum(1 for item in workouts if item.status == 'completed'),
        'week_goal': WEEKLY_WORKOUT_GOAL,
        'next_workout': next_workout,
        **get_activity_stats(request.user, day),
    })


@login_required
def skip_today(request):
    if request.method == 'POST':
        updated = mark_today_missed(request.user.id)
        if updated:
            messages.success(request, 'Today marked as missed.')
        else:
            messages.info(request, 'No planned workout for today.')
    return redirect('home')
