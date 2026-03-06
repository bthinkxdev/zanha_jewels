"""
Authentication Service for Email OTP-based authentication
Handles OTP generation, validation, email sending, and user management
"""

from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from .models import OTPRequest, UserProfile

User = get_user_model()


class OTPService:
    """Service for handling OTP operations"""
    
    OTP_EXPIRY_MINUTES = 10
    RATE_LIMIT_SECONDS = 60  # 1 minute between OTP requests
    MAX_ATTEMPTS = 5  # Maximum verification attempts per OTP
    
    @classmethod
    def get_rate_limit_key(cls, email):
        """Generate cache key for rate limiting"""
        return f"otp_rate_limit_{email.lower()}"
    
    @classmethod
    def get_attempt_key(cls, email):
        """Generate cache key for tracking verification attempts"""
        return f"otp_attempts_{email.lower()}"
    
    @classmethod
    def is_rate_limited(cls, email):
        """Check if email is rate limited"""
        key = cls.get_rate_limit_key(email)
        return cache.get(key) is not None
    
    @classmethod
    def set_rate_limit(cls, email):
        """Set rate limit for email"""
        key = cls.get_rate_limit_key(email)
        cache.set(key, True, cls.RATE_LIMIT_SECONDS)
    
    @classmethod
    def get_cooldown_remaining(cls, email):
        """Get remaining cooldown time in seconds"""
        key = cls.get_rate_limit_key(email)
        ttl = cache.ttl(key)
        return max(0, ttl) if ttl else 0
    
    @classmethod
    def invalidate_old_otps(cls, email):
        """Mark all previous OTPs for this email as used"""
        OTPRequest.objects.filter(
            email=email.lower(),
            is_used=False,
            expires_at__gt=timezone.now()
        ).update(is_used=True)
    
    @classmethod
    def create_otp(cls, email, ip_address=None):
        """
        Generate and store a new OTP for the given email
        Returns: (otp_request, plain_otp) tuple
        """
        email = email.lower().strip()
        
        # Check rate limiting
        if cls.is_rate_limited(email):
            remaining = cls.get_cooldown_remaining(email)
            raise RateLimitError(f"Please wait {remaining} seconds before requesting another OTP.")
        
        # Invalidate old OTPs
        cls.invalidate_old_otps(email)
        
        # Generate new OTP
        plain_otp = OTPRequest.generate_otp()
        otp_hash = OTPRequest.hash_otp(plain_otp)
        
        # Create OTP request
        otp_request = OTPRequest.objects.create(
            email=email,
            otp_hash=otp_hash,
            expires_at=timezone.now() + timedelta(minutes=cls.OTP_EXPIRY_MINUTES),
            ip_address=ip_address,
        )
        
        # Set rate limit
        cls.set_rate_limit(email)
        
        return otp_request, plain_otp
    
    @classmethod
    def send_otp_email(cls, email, otp):
        """Send OTP via email"""
        email = email.lower().strip()
        
        # Prepare email context
        context = {
            'otp': otp,
            'expiry_minutes': cls.OTP_EXPIRY_MINUTES,
            'site_name': 'Hello Gads',
            'support_email': settings.DEFAULT_FROM_EMAIL,
        }
        
        # Render email templates
        html_message = render_to_string('auth/otp_email.html', context)
        plain_message = render_to_string('auth/otp_email.txt', context)
        
        # Send email
        try:
            send_mail(
                subject='Your One-Time Login Code',
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            return True
        except Exception as e:
            print(f"Error sending OTP email: {e}")
            return False
    
    @classmethod
    def verify_otp(cls, email, otp):
        """
        Verify OTP for given email
        Returns: (success, message, otp_request or None)
        """
        email = email.lower().strip()
        
        # Get the latest valid OTP request
        try:
            otp_request = OTPRequest.objects.filter(
                email=email,
                is_used=False,
                expires_at__gt=timezone.now()
            ).latest('created_at')
        except OTPRequest.DoesNotExist:
            return False, "No valid OTP found. Please request a new one.", None
        
        # Check if OTP is expired
        if not otp_request.is_valid():
            return False, "OTP has expired. Please request a new one.", None
        
        # Check max attempts
        if otp_request.attempts >= cls.MAX_ATTEMPTS:
            otp_request.is_used = True
            otp_request.save(update_fields=['is_used'])
            return False, "Maximum verification attempts exceeded. Please request a new OTP.", None
        
        # Increment attempts
        otp_request.attempts += 1
        otp_request.save(update_fields=['attempts'])
        
        # Verify OTP
        if not otp_request.verify_otp(otp):
            remaining_attempts = cls.MAX_ATTEMPTS - otp_request.attempts
            if remaining_attempts > 0:
                return False, f"Invalid OTP. {remaining_attempts} attempts remaining.", None
            else:
                otp_request.is_used = True
                otp_request.save(update_fields=['is_used'])
                return False, "Invalid OTP. Maximum attempts exceeded.", None
        
        # OTP is valid
        otp_request.is_used = True
        otp_request.save(update_fields=['is_used'])
        
        return True, "OTP verified successfully.", otp_request


class AuthenticationService:
    """Service for handling user authentication and account management"""
    
    @classmethod
    def get_or_create_user(cls, email, name=None):
        """
        Get or create user by email
        Returns: (user, created)
        """
        email = email.lower().strip()
        
        # Try to get existing user
        try:
            user = User.objects.get(email=email)
            created = False
        except User.DoesNotExist:
            # Create new user
            username = email.split('@')[0] + str(timezone.now().timestamp()).replace('.', '')[:10]
            user = User.objects.create_user(
                username=username,
                email=email,
                first_name=name or '',
            )
            # Set unusable password (no password-based login)
            user.set_unusable_password()
            user.save()
            
            # Create user profile
            UserProfile.objects.get_or_create(user=user)
            created = True
        
        return user, created
    
    @classmethod
    def update_user_profile(cls, user, **kwargs):
        """Update user profile information"""
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Update user fields
        if 'first_name' in kwargs:
            user.first_name = kwargs['first_name']
        if 'last_name' in kwargs:
            user.last_name = kwargs['last_name']
        user.save()
        
        # Update profile fields
        if 'phone' in kwargs:
            profile.phone = kwargs['phone']
        profile.save()
        
        return profile


class RateLimitError(Exception):
    """Exception raised when rate limit is exceeded"""
    pass

