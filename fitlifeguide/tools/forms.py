from django import forms
from django.forms import formset_factory


class ExerciseForm(forms.Form):
    name = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Exercise name',
        'aria-label': 'Exercise name',
    }))
    sets = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Sets',
        'aria-label': 'Sets',
    }))
    reps = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Reps',
        'aria-label': 'Reps',
    }))


ExerciseFormSet = formset_factory(ExerciseForm, extra=1, can_delete=True)


class MealPlannerForm(forms.Form):
    food_items = forms.CharField(widget=forms.Textarea(attrs={
        'rows': 3,
        'placeholder': 'Enter food items, one per line',
    }))
    calories = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Enter calories (optional)',
    }))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 2,
        'placeholder': 'Any additional notes (optional)',
    }))


class WorkoutPlanForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date',
    }))
    title = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter workout title',
    }))
    duration_minutes = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Duration in minutes',
    }))
    goal = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'What do you want to achieve? (e.g., Build strength, Improve cardio)',
    }))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 3,
        'placeholder': 'Additional notes, reminders, or instructions...',
    }))
