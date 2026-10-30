from django import forms


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
    exercises = forms.CharField(required=False, widget=forms.Textarea(attrs={
        'rows': 4,
        'placeholder': 'List your exercises here (e.g., 3x10 Push-ups, 4x12 Squats...)',
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
