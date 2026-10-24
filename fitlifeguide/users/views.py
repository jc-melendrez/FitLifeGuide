from django.shortcuts import render,redirect
from django.contrib.auth import authenticate, login
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.views import LoginView
from .forms import CustomLoginForm
from django.contrib.auth.decorators import login_required
from community.models import BlogPost
from tools.models import MealPlanner, WorkoutPlanner
from videos.models import VideoHistory
from .models import Profile, EmailOTP
from django.http import JsonResponse
from django.urls import reverse
from django.core.mail import send_mail
import secrets
from django.conf import settings
from django.utils import timezone
from django.http import HttpResponseBadRequest
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

from .forms import OTPForm









def register(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})





@login_required
def profile(request):
    # Get or create profile for the user
    profile = Profile.get_or_create_profile(request.user)
    
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('profile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=profile)

    if request.path == reverse('profile'):
        template = 'users/profile.html'
        posts = BlogPost.objects.filter(author=request.user)
        meals = MealPlanner.objects.filter(user=request.user).order_by('-date')
        workouts = WorkoutPlanner.objects.filter(user=request.user).order_by('-date')
        video_history = VideoHistory.objects.filter(user=request.user)
        
        context = {
            'posts': posts[:5],
            'meals': meals[:7],
            'workouts': workouts[:7],
            'video_history': video_history[:9],
            'post_count': posts.count(),
            'meal_count': meals.count(),
            'workout_count': workouts.count(),
            'video_count': video_history.count(),
        }
    else:
        template = 'users/edit_profile.html'
        context = {}

    context.update({
        'u_form': u_form,
        'p_form': p_form,
    })

    return render(request, template, context)





from django.shortcuts import redirect
from django.core.mail import send_mail
from django.contrib.auth.views import LoginView

def send_otp_email(user, otp):
    """Helper function to send OTP email with HTML template"""
    context = {
        'user': user,
        'otp': otp
    }
    
    # Render HTML content
    html_content = render_to_string('users/otp_email.html', context)
    # Create plain text content (fallback)
    text_content = f'Your OTP for FitLifeGuide login is: {otp}\nThis code will expire in 5 minutes.'
    
    # Create email
    subject = 'Your FitLifeGuide Login Code'
    from_email = 'noreply@fitlifeguide.com'
    to_email = user.email
    
    msg = EmailMultiAlternatives(subject, text_content, from_email, [to_email])
    msg.attach_alternative(html_content, "text/html")
    msg.send()

class CustomLoginView(LoginView):
    authentication_form = CustomLoginForm
    template_name = 'users/login.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        user = form.get_user()
        self.request.session['pre_2fa_user_id'] = user.id

        # Generate and store OTP
        otp = str(secrets.randbelow(900000) + 100000)
        EmailOTP.objects.update_or_create(
            user=user,
            defaults={'code': otp, 'created_at': timezone.now()}
        )

        # Send OTP email using the new template
        send_otp_email(user, otp)

        return redirect('verify_otp')





def logout(request):
    return render(request,'mainpage/about.html')
    

def verify_otp(request):
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return redirect('login')
    
    user = User.objects.get(id=user_id)
    
    if request.method == 'POST':
        form = OTPForm(request.POST)
        if form.is_valid():
            input_otp = form.cleaned_data['otp']
            try:
                email_otp = EmailOTP.objects.get(user=user)
                
                if email_otp.is_expired():
                    form.add_error('otp', 'OTP has expired. Please request a new one.')
                elif input_otp == email_otp.code:
                    login(request, user)
                    # Clean up session and OTP
                    del request.session['pre_2fa_user_id']
                    email_otp.delete()
                    return redirect('home')
                else:
                    form.add_error('otp', 'Invalid OTP. Please try again.')
            except EmailOTP.DoesNotExist:
                form.add_error('otp', 'No valid OTP found. Please request a new one.')
    else:
        form = OTPForm()

    return render(request, 'users/verify_otp.html', {'form': form})

def resend_otp(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Invalid request method')
    
    user_id = request.session.get('pre_2fa_user_id')
    if not user_id:
        return HttpResponseBadRequest('No pending OTP verification')
    
    user = User.objects.get(id=user_id)
    
    # Generate new OTP
    otp = str(secrets.randbelow(900000) + 100000)
    EmailOTP.objects.update_or_create(
        user=user,
        defaults={'code': otp, 'created_at': timezone.now()}
    )

    # Send OTP email using the new template
    send_otp_email(user, otp)
    
    return JsonResponse({'message': 'New OTP sent successfully'})

@login_required
def update_status(request):
    if request.method == 'POST':
        new_status = request.POST.get('status')
        profile = Profile.get_or_create_profile(request.user)
        if new_status in dict(Profile.STATUS_CHOICES):
            profile.status = new_status
            profile.save()
            return JsonResponse({
                'success': True,
                'status': new_status,
                'status_text': dict(Profile.STATUS_CHOICES)[new_status]
            })
    return JsonResponse({'success': False}, status=400)
