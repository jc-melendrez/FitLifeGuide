import json
import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from firebase_admin import auth as firebase_auth
from firebase_admin import exceptions as firebase_exceptions

from fitlifeguide.domain import PROFILE_STATUS, label_for
from fitlifeguide.firestore import ensure_initialized
from fitlifeguide.storage import delete_image, upload_image

from .firebase_auth import FirebaseAuthError, verify_firebase_id_token
from .forms import (
    CompleteProfileForm,
    CustomLoginForm,
    EmailLinkForm,
    OTPForm,
    ProfileUpdateForm,
    UserUpdateForm,
)
from .repositories import (
    consume_link_request,
    create_link_request,
    create_otp,
    delete_otp,
    get_link_request,
    get_otp,
    get_user,
    get_user_by_email,
    get_user_by_firebase_uid,
    grant_link_request,
    link_firebase_uid,
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


def _firebase_config():
    return {
        'apiKey': settings.FIREBASE_API_KEY,
        'authDomain': settings.FIREBASE_AUTH_DOMAIN,
        'projectId': settings.FIREBASE_PROJECT_ID,
        'appId': settings.FIREBASE_APP_ID,
    }


def _auth_context(request, **extra):
    config = _firebase_config()
    context = {
        'firebase_config': config,
        'firebase_configured': all(config.values()),
        'send_link_url': reverse('send_sign_in_link'),
        'link_status_url': reverse('link_status'),
        'handoff_url': reverse('handoff_login'),
        'callback_url': request.build_absolute_uri(reverse('firebase_callback')),
        'complete_profile_url': request.build_absolute_uri(reverse('complete_profile')),
        'home_url': reverse('home'),
    }
    context.update(extra)
    return context


def _json_payload(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _firebase_error(exc):
    return JsonResponse(
        {'status': 'error', 'message': str(exc)},
        status=getattr(exc, 'status_code', 400),
    )


def _login_firebase_user(request, user):
    user.backend = settings.AUTHENTICATION_BACKENDS[0]
    auth_login(request, user)


def _firebase_user_from_token(payload):
    firebase_uid = payload['uid']
    user = get_user_by_firebase_uid(firebase_uid)
    if user:
        return user

    user = get_user_by_email(payload['email'])
    if user:
        return link_firebase_uid(user.id, firebase_uid)
    return None


@never_cache
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(
        request,
        'users/login.html',
        _auth_context(request, form=EmailLinkForm()),
    )


@never_cache
def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    return render(
        request,
        'users/register.html',
        _auth_context(request, form=EmailLinkForm(), signup=True),
    )


@never_cache
@require_http_methods(['POST'])
def send_sign_in_link(request):
    payload = _json_payload(request)
    if payload is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)

    email = (payload.get('email') or '').strip()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'status': 'error', 'message': 'Enter a valid email address.'}, status=400)

    ensure_initialized()
    rid = secrets.token_urlsafe(32)
    create_link_request(rid, email)
    callback_url = request.build_absolute_uri(reverse('firebase_callback'))
    action_code_settings = firebase_auth.ActionCodeSettings(
        url=f'{callback_url}?rid={rid}',
        handle_code_in_app=True,
    )
    try:
        link = firebase_auth.generate_sign_in_with_email_link(email, action_code_settings)
    except firebase_exceptions.FirebaseError as exc:
        logger.warning('Sign-in link generation failed for %s: %s', email, exc)
        return JsonResponse({
            'status': 'error',
            'message': str(exc) or 'Could not create the sign-in link. Please try again later.',
        }, status=502)

    html_content = render_to_string('users/magic_link_email.html', {'sign_in_url': link, 'email': email})
    text_content = (
        'Tap the link below to sign in to FitLifeGuide. '
        f'It works only once and is meant for {email}.\n\n{link}\n\n'
        'If you did not request this email, you can safely ignore it.'
    )
    msg = EmailMultiAlternatives(
        'Your FitLifeGuide sign-in link',
        text_content,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    msg.attach_alternative(html_content, 'text/html')
    try:
        msg.send()
    except Exception:
        logger.exception('Sign-in link email failed for %s', email)
        return JsonResponse({
            'status': 'error',
            'message': 'Could not send the email. Please try again in a moment.',
        }, status=502)

    return JsonResponse({'status': 'ok', 'rid': rid})


@never_cache
@require_http_methods(['GET', 'POST'])
def firebase_callback(request):
    if request.method == 'GET':
        return render(
            request,
            'users/firebase_callback.html',
            _auth_context(request, form=CompleteProfileForm()),
        )

    payload = _json_payload(request)
    if payload is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)

    try:
        verified = verify_firebase_id_token(payload.get('idToken'))
        user = _firebase_user_from_token(verified)
    except FirebaseAuthError as exc:
        return _firebase_error(exc)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=409)

    rid = (payload.get('rid') or '').strip()
    if rid:
        try:
            grant_link_request(rid, verified['uid'], verified['email'])
        except Exception:
            logger.warning('Link handoff grant failed for rid %s', rid, exc_info=True)

    if not user:
        return JsonResponse({
            'status': 'needs_profile',
            'email': verified['email'],
        })

    if not user.is_active:
        return JsonResponse(
            {'status': 'error', 'message': 'This account is inactive.'},
            status=403,
        )

    _login_firebase_user(request, user)
    return JsonResponse({'status': 'ok', 'redirect': reverse('home')})


HANDOFF_SALT = 'users.link_handoff'
HANDOFF_MAX_AGE_SECONDS = 300


@never_cache
def link_status(request):
    rid = (request.GET.get('rid') or '').strip()
    record = get_link_request(rid)
    if not record:
        return JsonResponse({'status': 'invalid'})
    if record.get('status') != 'granted':
        return JsonResponse({'status': 'pending'})
    token = signing.dumps({
        'rid': rid,
        'uid': record.get('uid', ''),
        'email': record.get('email', ''),
    }, salt=HANDOFF_SALT)
    return JsonResponse({
        'status': 'ready',
        'token': token,
        'email': record.get('email', ''),
    })


@never_cache
@require_http_methods(['POST'])
def handoff_login(request):
    payload = _json_payload(request)
    if payload is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)

    try:
        data = signing.loads(
            payload.get('token') or '',
            salt=HANDOFF_SALT,
            max_age=HANDOFF_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return JsonResponse({
            'status': 'error',
            'message': 'This sign-in session has expired. Please request a new link.',
        }, status=400)

    consumed = consume_link_request(data.get('rid'))
    if not consumed:
        return JsonResponse({
            'status': 'error',
            'message': 'This sign-in was already used. Please request a new link.',
        }, status=400)

    user = get_user_by_firebase_uid(consumed.get('uid'))
    if not user:
        return JsonResponse({
            'status': 'needs_profile',
            'email': consumed.get('email', ''),
        })
    if not user.is_active:
        return JsonResponse({'status': 'error', 'message': 'This account is inactive.'}, status=403)

    _login_firebase_user(request, user)
    return JsonResponse({'status': 'ok', 'redirect': reverse('home')})


@require_POST
def complete_profile(request):
    payload = _json_payload(request)
    if payload is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'}, status=400)

    try:
        verified = verify_firebase_id_token(payload.get('idToken'))
        existing = get_user_by_firebase_uid(verified['uid'])
        if not existing:
            existing = get_user_by_email(verified['email'])
            if existing:
                existing = link_firebase_uid(existing.id, verified['uid'])
    except FirebaseAuthError as exc:
        return _firebase_error(exc)
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=409)

    if existing:
        if not existing.is_active:
            return JsonResponse(
                {'status': 'error', 'message': 'This account is inactive.'},
                status=403,
            )
        _login_firebase_user(request, existing)
        return JsonResponse({'status': 'ok', 'redirect': reverse('home')})

    form = CompleteProfileForm(payload)
    if not form.is_valid():
        return JsonResponse({
            'status': 'invalid',
            'errors': form.errors.get_json_data(),
        }, status=400)

    try:
        user = form.save(verified['uid'], verified['email'])
    except ValueError as exc:
        return JsonResponse({'status': 'error', 'message': str(exc)}, status=409)

    _login_firebase_user(request, user)
    return JsonResponse({'status': 'ok', 'redirect': reverse('home')})


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
                auth_login(request, user)
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
                auth_login(request, user)
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
