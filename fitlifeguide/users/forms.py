from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from fitlifeguide.domain import PROFILE_STATUS

from .repositories import create_user, get_user_by_email, get_user_by_username

GOAL_CHOICES = (
    ('build_muscle', 'Build muscle'),
    ('lose_fat', 'Lose fat'),
    ('stay_active', 'Stay active'),
    ('run_further', 'Run further'),
)
DAY_CHOICES = tuple((str(n), str(n)) for n in (2, 3, 4, 5, 6))


class UserRegisterForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email',
    }))
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username',
        'autofocus': True,
    }))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password',
    }))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Confirm Password',
    }))
    goal = forms.ChoiceField(choices=GOAL_CHOICES, required=False, initial='build_muscle', widget=forms.RadioSelect)
    days_per_week = forms.ChoiceField(choices=DAY_CHOICES, required=False, initial='4', widget=forms.RadioSelect)

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if get_user_by_username(username):
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if get_user_by_email(email):
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', 'The two password fields did not match.')
        if password1:
            try:
                validate_password(password1)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return cleaned

    def save(self):
        days = self.cleaned_data.get('days_per_week')
        return create_user(
            self.cleaned_data['username'],
            self.cleaned_data['email'],
            self.cleaned_data['password1'],
            goal=self.cleaned_data.get('goal', ''),
            days_per_week=int(days) if days else None,
        )


class EmailLinkForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={
        'class': 'form-control',
        'placeholder': 'Email',
        'autocomplete': 'email',
    }))


class CompleteProfileForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username',
        'autofocus': True,
        'autocomplete': 'username',
    }))
    goal = forms.ChoiceField(
        choices=GOAL_CHOICES,
        required=False,
        initial='build_muscle',
        widget=forms.RadioSelect,
    )
    days_per_week = forms.ChoiceField(
        choices=DAY_CHOICES,
        required=False,
        initial='4',
        widget=forms.RadioSelect,
    )
    location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
    )
    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short bio'}),
    )
    birth_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if get_user_by_username(username):
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, firebase_uid, email):
        days = self.cleaned_data.get('days_per_week')
        return create_user(
            self.cleaned_data['username'],
            email,
            None,
            goal=self.cleaned_data.get('goal', ''),
            days_per_week=int(days) if days else None,
            firebase_uid=firebase_uid,
            profile_data={
                'location': self.cleaned_data.get('location', ''),
                'bio': self.cleaned_data.get('bio', ''),
                'birth_date': self.cleaned_data.get('birth_date'),
            },
        )


class UserUpdateForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user and not self.is_bound:
            self.initial.update({'username': user.username, 'email': user.email})

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        existing = get_user_by_username(username)
        if existing and existing.id != self.user.id:
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        existing = get_user_by_email(email)
        if existing and existing.id != self.user.id:
            raise forms.ValidationError('An account with this email already exists.')
        return email


class ProfileUpdateForm(forms.Form):
    location = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    bio = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}))
    birth_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))
    avatar = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'data-preview': 'avatar-preview',
        }),
    )
    cover_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'data-preview': 'cover-preview',
        }),
    )
    status = forms.ChoiceField(
        choices=PROFILE_STATUS,
        required=True,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, profile=None, **kwargs):
        super().__init__(*args, **kwargs)
        if profile and not self.is_bound:
            self.initial.update({
                'location': profile.location,
                'bio': profile.bio,
                'birth_date': profile.birth_date,
                'status': profile.status,
            })


class CustomLoginForm(forms.Form):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Username',
        'autofocus': True,
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Password',
    }))

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get('username')
        password = cleaned.get('password')
        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    'Please enter a correct username and password. Note that both fields may be case-sensitive.'
                )
            if not self.user_cache.is_active:
                raise forms.ValidationError('This account is inactive.')
        return cleaned

    def get_user(self):
        return self.user_cache


class OTPForm(forms.Form):
    otp = forms.CharField(label='Enter OTP', max_length=6, widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': 'Enter 6-digit code',
        'inputmode': 'numeric',
        'autocomplete': 'one-time-code',
        'autofocus': True,
    }))
