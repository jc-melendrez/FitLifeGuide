from django import forms
from django.forms import formset_factory

from fitlifeguide.domain import (
    EXERCISE_NUMERIC_FIELDS,
    EXERCISE_TYPES,
    MAX_EXERCISES,
)


class ExerciseForm(forms.Form):
    name = forms.CharField(
        required=False,
        max_length=80,
        widget=forms.TextInput(attrs={
            'placeholder': 'Exercise name',
            'aria-label': 'Exercise name',
            'autocomplete': 'off',
            'role': 'combobox',
            'aria-autocomplete': 'list',
            'aria-expanded': 'false',
            'data-field': 'name',
        }),
    )
    type = forms.ChoiceField(
        required=False,
        choices=EXERCISE_TYPES,
        initial='strength',
        widget=forms.Select(attrs={
            'aria-label': 'Exercise type',
            'data-field': 'type',
        }),
    )
    order = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'data-field': 'order'}),
    )
    sets = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Sets',
            'aria-label': 'Sets',
            'data-field': 'sets',
        }),
    )
    reps = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Reps',
            'aria-label': 'Reps',
            'data-field': 'reps',
        }),
    )
    weight_kg = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=6,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'min': 0,
            'step': '0.5',
            'inputmode': 'decimal',
            'placeholder': 'Weight (kg)',
            'aria-label': 'Weight in kilograms',
            'data-field': 'weight_kg',
        }),
    )
    seconds = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Seconds',
            'aria-label': 'Seconds per set',
            'data-field': 'seconds',
        }),
    )
    minutes = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'min': 1,
            'inputmode': 'numeric',
            'placeholder': 'Minutes',
            'aria-label': 'Minutes',
            'data-field': 'minutes',
        }),
    )
    distance_km = forms.DecimalField(
        required=False,
        min_value=0,
        max_digits=7,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'min': 0,
            'step': '0.1',
            'inputmode': 'decimal',
            'placeholder': 'Distance (km)',
            'aria-label': 'Distance in kilometers',
            'data-field': 'distance_km',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name_id = self['name'].auto_id
        self.fields['name'].widget.attrs['aria-controls'] = f'{name_id}-suggest'

    def clean(self):
        cleaned = super().clean()
        name = (cleaned.get('name') or '').strip()
        cleaned['name'] = name
        exercise_type = cleaned.get('type') or 'strength'
        cleaned['type'] = exercise_type
        has_numbers = any(
            cleaned.get(field) is not None
            for field in EXERCISE_NUMERIC_FIELDS
        )
        if not name and not has_numbers:
            cleaned['is_blank'] = True
            return cleaned
        if not name:
            self.add_error('name', 'Enter an exercise name.')
        if exercise_type == 'strength':
            if cleaned.get('sets') is None:
                self.add_error('sets', 'Sets must be 1 or more.')
            if cleaned.get('reps') is None:
                self.add_error('reps', 'Reps must be 1 or more.')
        elif exercise_type == 'timed':
            if cleaned.get('sets') is None:
                self.add_error('sets', 'Sets must be 1 or more.')
            if cleaned.get('seconds') is None:
                self.add_error('seconds', 'Seconds must be 1 or more.')
        elif exercise_type == 'cardio':
            if cleaned.get('minutes') is None:
                self.add_error('minutes', 'Minutes must be 1 or more.')
        return cleaned


ExerciseFormSet = formset_factory(
    ExerciseForm,
    extra=0,
    can_delete=True,
    max_num=MAX_EXERCISES,
    validate_max=True,
)


class CustomExerciseForm(forms.Form):
    name = forms.CharField(max_length=80, strip=True)
    type = forms.ChoiceField(choices=EXERCISE_TYPES, initial='strength')

    def clean_name(self):
        name = self.cleaned_data['name'].strip()
        if not name:
            raise forms.ValidationError('Enter an exercise name.')
        return name


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
