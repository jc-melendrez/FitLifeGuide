from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import logging
import random
from django.db.models.signals import post_save
from django.dispatch import receiver
from PIL import Image
import os
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

class EmailOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=5)

    def __str__(self):
        return f"{self.user.username} - {self.code}"

class Profile(models.Model):
    STATUS_CHOICES = [
        ('run', 'Run'),
        ('lift', 'Lift'),
        ('rest', 'Rest'),
        ('cook', 'Cook'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    location = models.CharField(max_length=100, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='profile_pics', default='profile_pics/default-avatar.png')
    cover_image = models.ImageField(upload_to='cover_pics', default='cover_pics/default-cover.jpg')
    status = models.CharField(max_length=4, choices=STATUS_CHOICES, default='rest')
    status_updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        # Create default avatar if it doesn't exist
        if not self.avatar:
            self.create_default_avatar()
        
        super().save(*args, **kwargs)

        # Process profile picture
        if self.avatar and os.path.exists(self.avatar.path):
            img = Image.open(self.avatar.path)
            if img.height > 300 or img.width > 300:
                output_size = (300, 300)
                img.thumbnail(output_size)
                img.save(self.avatar.path)

        # Process cover image
        if self.cover_image and os.path.exists(self.cover_image.path):
            img = Image.open(self.cover_image.path)
            if img.height > 800 or img.width > 2000:  # Larger size for cover image
                # Calculate aspect ratio to maintain it while resizing
                aspect_ratio = img.width / img.height
                new_width = min(2000, img.width)
                new_height = int(new_width / aspect_ratio)
                output_size = (new_width, new_height)
                img.thumbnail(output_size)
                img.save(self.cover_image.path)

    def create_default_avatar(self):
        from django.conf import settings
        import os
        from PIL import Image, ImageDraw, ImageFont
        
        # Create directory if it doesn't exist
        avatar_dir = os.path.join(settings.MEDIA_ROOT, 'profile_pics')
        os.makedirs(avatar_dir, exist_ok=True)
        
        # Path for default avatar
        default_avatar_path = os.path.join(avatar_dir, 'default-avatar.png')
        
        if not os.path.exists(default_avatar_path):
            # Create a new image with a gradient background
            img = Image.new('RGB', (300, 300), color='#1a1d20')
            draw = ImageDraw.Draw(img)
            
            # Draw a circle
            draw.ellipse([50, 50, 250, 250], fill='#2c3034')
            
            # Draw a simple avatar silhouette
            draw.ellipse([125, 100, 175, 150], fill='#0dcaf0')  # Head
            draw.rectangle([135, 150, 165, 220], fill='#0dcaf0')  # Body
            
            # Save the image
            img.save(default_avatar_path, 'PNG')

    @classmethod
    def get_or_create_profile(cls, user):
        profile, created = cls.objects.get_or_create(user=user)
        if created:
            profile.create_default_avatar()
        return profile

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        # Create profile
        profile = Profile.objects.create(user=instance)
        profile.create_default_avatar()

        # Send welcome email
        if not instance.email:
            return
        subject = 'Welcome to FitLifeGuide!'
        html_content = render_to_string('users/welcome_email.html', {'username': instance.username})
        text_content = f'Hi {instance.username},\n\nThank you for registering with FitLifeGuide. We\'re excited to help you reach your fitness goals.\n\nIf you have any questions, feel free to reply to this email.\n\n– The FitLifeGuide Team'

        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [instance.email]
        )
        msg.attach_alternative(html_content, "text/html")
        try:
            msg.send()
        except Exception:
            logger.exception("Welcome email failed for %s", instance.email)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    Profile.get_or_create_profile(instance)

# Create your models here.
