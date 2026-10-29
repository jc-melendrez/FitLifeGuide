from django import forms

from tools.repositories import list_workouts_by_user


class BlogPostForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput(attrs={'placeholder': 'Session title'}))
    content = forms.CharField(widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'How did it go?'}))
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'accept': 'image/*'}),
    )
    workout = forms.ChoiceField(required=False, widget=forms.Select())
    published = forms.BooleanField(required=False, widget=forms.CheckboxInput())

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        workouts = list_workouts_by_user(user.id, limit=30) if user else []
        self.fields['workout'].choices = [('', 'No workout')] + [
            (workout.id, f'{workout.date} - {workout.title}') for workout in workouts
        ]


class ThreadForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput(attrs={
        'placeholder': 'Enter a descriptive title for your thread',
    }))
    content = forms.CharField(widget=forms.Textarea(attrs={
        'rows': 8,
        'placeholder': 'Write your thread content here...',
    }))


class BlogCommentForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'fl-input',
        'rows': 3,
        'placeholder': 'Write your comment here...',
    }))


class ForumCommentForm(forms.Form):
    content = forms.CharField(widget=forms.Textarea(attrs={
        'class': 'fl-input',
        'rows': 3,
        'placeholder': 'Write your reply here...',
    }))
    parent = forms.CharField(required=False, widget=forms.HiddenInput())
