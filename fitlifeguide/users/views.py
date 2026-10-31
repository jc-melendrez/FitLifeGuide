import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import EmailMultiAlternatives
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse

from fitlifeguide.domain import PROFILE_STATUS, label_for
from fitlifeguide.storage import delete_image, upload_image

from .forms import CustomLoginForm, OTPForm, ProfileUpdateForm, UserRegisterForm, UserUpdateForm
from .repositories import (
    create_otp,
    delete_otp,
    get_otp,
    get_user,
    set_status,
    update_profile,
    update_user,
)

logger = logging.getLogger(__name__)


def send_otp_email(user, otp):
    html_content = render_to_string('users/otp_email.html', {'user': user, 'otp': otp})
    text_content = f'Your OTP for FitLifeGuide login is: {otp}\nThis code will expire in 5 minutes.'
    msg = EmailMultiAlternatives(
        'Your FitLifeGuide Login Code',
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    msg.attach_alternative(html_content, 'text/html')
    msg.send()


def send_welcome_email(user):
    if not user.email:
        return
    html_content = render_to_string('users/welcome_email.html', {'username': user.username})
    text_content = (
        f"Hi {user.username},\n\nThank you for registering with FitLifeGuide. "
        "We're excited to help you reach your fitness goals.\n\n"
        'If you have any questions, feel free to reply to this email.\n\n'
        '- The FitLifeGuide Team'
    )
    msg = EmailMultiAlternatives(
        'Welcome to FitLifeGuide!',
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
    )
    msg.attach_alternative(html_content, 'text/html')
    try:
        msg.send()
    except Exception:
        logger.exception('Welcome email failed for %s', user.email)


def register(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            send_welcome_email(user)
            messages.success(request, f'Account created for {user.username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})


@login_required
def profile(request):
    user = get_user(request.user.id) or request.user

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, user=user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, profile=user.profile)
        if u_form.is_valid() and p_form.is_valid():
            try:
                updated = update_user(
                    user,
                    u_form.cleaned_data['username'],
                    u_form.cleaned_data['email'],
                )
            except ValueError as exc:
                u_form.add_error(None, str(exc))
            else:
                avatar = p_form.cleaned_data.get('avatar')
                cover = p_form.cleaned_data.get('cover_image')
                avatar_url = user.profile.avatar_url
                cover_url = user.profile.cover_url
                try:
                    if avatar:
                        new_avatar = upload_image(avatar, 'avatars')
                        delete_image(avatar_url)
                        avatar_url = new_avatar
                    if cover:
                        new_cover = upload_image(cover, 'covers')
                        delete_image(cover_url)
                        cover_url = new_cover
                except ValueError as exc:
                    p_form.add_error(None, str(exc))
                else:
                    updated = update_profile(
                        user.id,
                        p_form.cleaned_data,
                        avatar_url=avatar_url,
                        cover_url=cover_url,
                    )
                    from community.repositories import refresh_author
                    refresh_author(updated.id, updated.username, updated.profile.avatar_url)
                    messages.success(request, 'Your profile has been updated!')
                    return redirect('profile')
    else:
        u_form = UserUpdateForm(user=user)
        p_form = ProfileUpdateForm(profile=user.profile)

    context = {'u_form': u_form, 'p_form': p_form}
    if request.path == reverse('profile'):
        from community.repositories import count_posts_by_author, list_posts_by_author
        from tools.activity import get_activity_stats
        from tools.repositories import (
            count_meals_by_user,
            count_workouts_by_user,
            list_meals_by_user,
            list_workouts_by_user,
        )
        from videos.repositories import count_videos, list_video_history

        context.update({
            'posts': list_posts_by_author(user.id, limit=5),
            'meals': list_meals_by_user(user.id, limit=7),
            'workouts': list_workouts_by_user(user.id, limit=7),
            'video_history': list_video_history(user.id, limit=9),
            'post_count': count_posts_by_author(user.id),
            'meal_count': count_meals_by_user(user.id),
            'workout_count': count_workouts_by_user(user.id),
            'video_count': count_videos(user.id),
            **get_activity_stats(user),
        })
        return render(request, 'users/profile.html', context)

    return render(request, 'users/edit_profile.html', context)


class CustomLoginView(LoginView):
    authentication_form = CustomLoginForm
    template_name = 'users/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        if request.GET.get('restart'):
            request.session.pop('pre_2fa_user_id', None)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pending = bool(self.request.session.get('pre_2fa_user_id'))
        context['otp_pending'] = pending
        if pending and 'otp_form' not in context:
            context['otp_form'] = OTPForm()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('step') == 'otp':
            return self._verify_otp_step(request)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        self.request.session['pre_2fa_user_id'] = user.id
        otp = create_otp(user.id)
        try:
            send_otp_email(user, otp)
        except Exception:
            logger.exception('OTP email failed for %s', user.email)
            messages.error(self.request, 'Could not send the login code. Please try again later.')
            return redirect('login')
        return self.render_to_response(
            self.get_context_data(otp_pending=True, otp_form=OTPForm())
        )

    def _verify_otp_step(self, request):
        user_id = request.session.get('pre_2fa_user_id')
        if not user_id:
            return redirect('login')

        user = get_user(user_id)
        if not user:
            request.session.pop('pre_2fa_user_id', None)
            return redirect('login')

        form = OTPForm(request.POST)
        if form.is_valid():
            record = get_otp(user.id)
            if not record:
                form.add_error('otp', 'OTP has expired. Please request a new one.')
            elif form.cleaned_data['otp'] != record.get('code'):
                form.add_error('otp', 'Invalid OTP. Please try again.')
            else:
                user.backend = settings.AUTHENTICATION_BACKENDS[0]
                login(request, user)
                request.session.pop('pre_2fa_user_id', None)
                delete_otp(user.id)
                return redirect('home')

        return self.render_to_response(
            self.get_context_data(otp_pending=True, otp_form=form)
        )


def verify_otp(request):
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('login')

    user = get_user(user_id)
    if not user:
        request.session.pop('pre_2fa_user_id', None)
        return redirect('login')

    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            record = get_otp(user.id)
            if not record:
                form.add_error('otp', 'OTP has expired. Please request a new one.')
            elif form.cleaned_data['otp'] != record.get('code'):
                form.add_error('otp', 'Invalid OTP. Please try again.')
            else:
                user.backend = settings.AUTHENTICATION_BACKENDS[0]
                login(request, user)
                request.session.pop('pre_2fa_user_id', None)
                delete_otp(user.id)
                return redirect('home')
    else:
        form = OTPForm()

    return render(request, 'users/verify_otp.html', {'form': form})


def resend_otp(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')

    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return HttpResponseBadRequest('No pending OTP verification')

    user = get_user(user_id)
    if not user:
        return HttpResponseBadRequest('No pending OTP verification')

    otp = create_otp(user.id)
    try:
        send_otp_email(user, otp)
    except Exception:
        logger.exception('Resend OTP failed for %s', user.email)
        return JsonResponse({'message': 'Could not send a new code'}, status=502)

    return JsonResponse({'message': 'New OTP sent successfully'})


@login_required
def update_status(request):
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(PROFILE_STATUS):
            set_status(request.user.id, new_status)
            return JsonResponse({
                'success': True,
                'status': new_status,
                'status_text': label_for(PROFILE_STATUS, new_status),
            })
    return JsonResponse({'success': False}, status=400)
