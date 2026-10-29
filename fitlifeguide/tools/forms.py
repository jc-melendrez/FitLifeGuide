from django import forms


class MealPlannerForm(forms.Form):
    food_items = forms.CharField(widget=forms.Textarea(attrs={
        'rows': 3,
        'placeholder': 'Enter food items, one per line',
        'class': 'bg-dark text-light border-secondary',
    }))
    calories = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Enter calories (optional)',
        'class': 'bg-dark text-light border-secondary',
    }))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 2,
        'placeholder': 'Any additional notes (optional)',
        'class': 'bg-dark text-light border-secondary',
    }))


class WorkoutPlanForm(forms.Form):
    date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date',
        'class': 'bg-dark text-light border-secondary',
    }))
    title = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter workout title',
        'class': 'bg-dark text-light border-secondary',
    }))
    exercises = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 4,
        'placeholder': 'List your exercises here (e.g., 3x10 Push-ups, 4x12 Squats...)',
        'class': 'bg-dark text-light border-secondary',
    }))
    duration_minutes = forms.IntegerField(required=False, min_value=0, widget=forms.NumberInput(attrs={
        'placeholder': 'Duration in minutes',
        'class': 'bg-dark text-light border-secondary',
    }))
    goal = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'What do you want to achieve? (e.g., Build strength, Improve cardio)',
        'class': 'bg-dark text-light border-secondary',
    }))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 3,
        'placeholder': 'Additional notes, reminders, or instructions...',
        'class': 'bg-dark text-light border-secondary',
    }))
