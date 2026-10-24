from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
from .models import MealPlan, MealPlanner, WeekDay, WorkoutPlan, WorkoutPlanner
from .forms import MealPlannerForm, WorkoutPlanForm

# Create your views here.

@login_required
def meal_planner(request):
    # Get or create meal plan for the user
    meal_plan, created = MealPlan.objects.get_or_create(user=request.user)
    
    # Get the requested week or default to current week
    requested_week = request.GET.get('week')
    direction = request.GET.get('direction')
    
    if requested_week:
        try:
            week_start = datetime.strptime(requested_week, '%Y-%m-%d').date()
            if direction == 'next':
                week_start += timedelta(days=7)
            elif direction == 'prev':
                week_start -= timedelta(days=7)
        except ValueError:
            week_start = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
    else:
        # Get the current date and week start
        week_start = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
    
    # Calculate week end
    week_end = week_start + timedelta(days=6)
    
    # Get all meals for the selected week
    meals = MealPlanner.objects.filter(
        user=request.user,
        week_start=week_start
    ).order_by('date', 'meal_type')
    
    # Create a structured week plan
    week_plan = {}
    for day in WeekDay.choices:
        day_code, day_name = day
        week_plan[day_code] = {
            'date': week_start + timedelta(days=WeekDay.values.index(day_code)),
            'meals': {
                'breakfast': None,
                'lunch': None,
                'dinner': None,
                'snack': None
            }
        }
    
    # Fill in the meals
    for meal in meals:
        week_plan[meal.day_of_week]['meals'][meal.meal_type] = meal
    
    # Get other users' meals (limited to latest 10)
    other_meals = MealPlanner.objects.exclude(user=request.user).order_by('-date')[:10]
    
    context = {
        'meal_plan': meal_plan,
        'week_plan': week_plan,
        'week_start': week_start,
        'week_end': week_end,
        'other_meals': other_meals,
    }
    
    return render(request, 'tools/meal_planner.html', context)

@login_required
def add_meal(request, date=None, meal_type=None):
    # Get date and meal type from URL parameters
    date = request.GET.get('date')
    meal_type = request.GET.get('meal_type')
    
    if not date or not meal_type:
        messages.error(request, 'Date and meal type are required.')
        return redirect('tools:meal_planner')
    
    try:
        meal_date = datetime.strptime(date, '%Y-%m-%d').date()
        day_name = WeekDay.choices[meal_date.weekday()][1]  # Get full day name
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect('tools:meal_planner')
    
    if request.method == 'POST':
        form = MealPlannerForm(request.POST)
        if form.is_valid():
            meal = form.save(commit=False)
            meal.user = request.user
            meal.meal_plan = MealPlan.objects.get(user=request.user)
            meal.date = meal_date
            meal.meal_type = meal_type
            meal.week_start = meal_date - timedelta(days=meal_date.weekday())
            meal.day_of_week = WeekDay.choices[meal_date.weekday()][0]
            meal.save()
            messages.success(request, 'Meal added successfully!')
            return redirect('tools:meal_planner')
    else:
        form = MealPlannerForm()
    
    context = {
        'form': form,
        'date': meal_date,
        'day_name': day_name,
        'meal_type': meal_type.title(),
    }
    
    return render(request, 'tools/add_meal.html', {'form': form, 'date': meal_date, 'day_name': day_name, 'meal_type': meal_type.title()})

@login_required
def edit_meal(request, meal_id):
    meal = get_object_or_404(MealPlanner, id=meal_id, user=request.user)
    day_name = WeekDay.choices[meal.date.weekday()][1]
    
    if request.method == 'POST':
        form = MealPlannerForm(request.POST, instance=meal)
        if form.is_valid():
            form.save()
            messages.success(request, 'Meal updated successfully!')
            return redirect('tools:meal_planner')
    else:
        form = MealPlannerForm(instance=meal)
    
    return render(request, 'tools/add_meal.html', {
        'form': form, 
        'meal': meal,
        'date': meal.date,
        'day_name': day_name,
        'meal_type': meal.meal_type.title()
    })

@login_required
def delete_meal(request, meal_id):
    meal = get_object_or_404(MealPlanner, id=meal_id, user=request.user)
    if request.method == 'POST':
        meal.delete()
        messages.success(request, 'Meal deleted successfully!')
    return redirect('tools:meal_planner')

@login_required
def update_meal_status(request, meal_id):
    meal = get_object_or_404(MealPlanner, id=meal_id, user=request.user)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(MealPlanner.STATUS_CHOICES):
            meal.status = status
            meal.save()
            messages.success(request, f'Meal marked as {status}!')
    return redirect('tools:meal_planner')

@login_required
def workout_hub(request):
    # Get or create workout plan for the user
    workout_plan, created = WorkoutPlan.objects.get_or_create(user=request.user)
    
    # Get the requested week or default to current week
    requested_week = request.GET.get('week')
    direction = request.GET.get('direction')
    
    if requested_week:
        try:
            week_start = datetime.strptime(requested_week, '%Y-%m-%d').date()
            if direction == 'next':
                week_start += timedelta(days=7)
            elif direction == 'prev':
                week_start -= timedelta(days=7)
        except ValueError:
            week_start = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
    else:
        # Get the current date and week start
        week_start = timezone.now().date() - timedelta(days=timezone.now().date().weekday())
    
    # Calculate week end
    week_end = week_start + timedelta(days=6)
    
    # Get user's workouts for the selected week
    user_workouts = WorkoutPlanner.objects.filter(
        user=request.user,
        week_start=week_start
    ).order_by('date')
    
    # Create a structured week plan
    week_plan = {}
    for day in WeekDay.choices:
        day_code, day_name = day
        current_date = week_start + timedelta(days=WeekDay.values.index(day_code))
        week_plan[day_name] = {
            'date': current_date,
            'workout': None
        }
    
    # Fill in the workouts
    for workout in user_workouts:
        week_plan[WeekDay(workout.day_of_week).label]['workout'] = workout
    
    # Get other users' public workouts (limited to latest 10)
    other_workouts = WorkoutPlanner.objects.exclude(user=request.user).order_by('-date')[:10]
    
    context = {
        'workout_plan': workout_plan,
        'week_plan': week_plan,
        'user_workouts': user_workouts,
        'other_workouts': other_workouts,
        'week_start': week_start,
        'week_end': week_end,
    }
    
    return render(request, 'tools/workout_hub.html', context)

@login_required
def add_workout(request):
    # Get date from URL parameters or use current date
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.now().date()
    else:
        selected_date = timezone.now().date()

    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST)
        if form.is_valid():
            workout = form.save(commit=False)
            workout.user = request.user
            workout.workout_plan = WorkoutPlan.objects.get(user=request.user)
            
            # Use the selected date to set week_start and day_of_week
            workout_date = form.cleaned_data['date']
            workout.date = workout_date
            workout.week_start = workout_date - timedelta(days=workout_date.weekday())
            workout.day_of_week = WeekDay.choices[workout_date.weekday()][0]
            
            workout.save()
            messages.success(request, 'Workout added successfully!')
            return redirect('tools:workout_hub')
    else:
        form = WorkoutPlanForm(initial={'date': selected_date})
    
    return render(request, 'tools/add_workout.html', {
        'form': form,
        'selected_date': selected_date
    })

@login_required
def edit_workout(request, workout_id):
    workout = get_object_or_404(WorkoutPlanner, id=workout_id, user=request.user)
    
    if request.method == 'POST':
        form = WorkoutPlanForm(request.POST, instance=workout)
        if form.is_valid():
            workout = form.save(commit=False)
            # Update week_start and day_of_week if date changes
            workout_date = form.cleaned_data['date']
            workout.week_start = workout_date - timedelta(days=workout_date.weekday())
            workout.day_of_week = WeekDay.choices[workout_date.weekday()][0]
            workout.save()
            messages.success(request, 'Workout updated successfully!')
            return redirect('tools:workout_hub')
    else:
        form = WorkoutPlanForm(instance=workout)
    
    return render(request, 'tools/edit_workout.html', {
        'form': form,
        'workout': workout
    })

@login_required
def delete_workout(request, workout_id):
    workout = get_object_or_404(WorkoutPlanner, id=workout_id, user=request.user)
    if request.method == 'POST':
        workout.delete()
        messages.success(request, 'Workout deleted successfully!')
    return redirect('tools:workout_hub')

@login_required
def update_workout_status(request, workout_id):
    workout = get_object_or_404(WorkoutPlanner, id=workout_id, user=request.user)
    if request.method == 'POST':
        status = request.POST.get('status')
        if status in dict(WorkoutPlanner.STATUS_CHOICES):
            workout.status = status
            workout.save()
            messages.success(request, f'Workout marked as {status}!')
    return redirect('tools:workout_hub')


@login_required
def skip_today(request):
    if request.method == 'POST':
        updated = WorkoutPlanner.objects.filter(
            user=request.user,
            date=timezone.localdate(),
            status='planned',
        ).update(status='missed')
        if updated:
            messages.success(request, 'Today marked as missed.')
        else:
            messages.info(request, 'No planned workout for today.')
    return redirect('home')
