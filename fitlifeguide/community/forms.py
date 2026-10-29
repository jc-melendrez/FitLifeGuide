from django import forms

from tools.models import WorkoutPlanner

from .models import BlogPost, Thread, BlogComment, ForumComment, Forum


class BlogPostForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['workout'].queryset = (
            user.workouts.order_by('-date') if user else WorkoutPlanner.objects.none()
        )

    class Meta:
        model = BlogPost
        fields = ['title', 'content', 'image', 'workout', 'published']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Session title'}),
            'content': forms.Textarea(attrs={'rows': 6, 'placeholder': 'How did it go?'}),
            'image': forms.FileInput(attrs={'accept': 'image/*'}),
            'workout': forms.Select(),
            'published': forms.CheckboxInput(),
        }


class ThreadCreateForm(forms.ModelForm):
    forum = forms.ModelChoiceField(queryset=Forum.objects.all(), empty_label="Select a forum")

    class Meta:
        model = Thread
        fields = ['forum', 'title']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Thread Title'}),
            'forum': forms.Select(attrs={'class': 'form-select'}),
        }


class ThreadForm(forms.ModelForm):
    class Meta:
        model = Thread
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Enter a descriptive title for your thread'
            }),
            'content': forms.Textarea(attrs={
                'rows': 8,
                'placeholder': 'Write your thread content here...'
            }),
        }


class BlogCommentForm(forms.ModelForm):
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'fl-input',
                'rows': 3,
                'placeholder': 'Write your comment here...',
            }),
        }


class ForumCommentForm(forms.ModelForm):
    parent = forms.ModelChoiceField(
        queryset=ForumComment.objects.all(),
        required=False,
        widget=forms.HiddenInput()
    )

    class Meta:
        model = ForumComment
        fields = ['content', 'parent']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'fl-input',
                'rows': 3,
                'placeholder': 'Write your reply here...',
            }),
        }
