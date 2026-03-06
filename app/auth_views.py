"""
Authentication Views for Email OTP-based authentication
"""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import FormView, ListView, TemplateView

from .auth_service import AuthenticationService, OTPService, RateLimitError
from .forms import AddressForm, EmailOTPRequestForm, OTPVerificationForm, UserProfileForm
from .models import Address, Order
from .services import CartService


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class OTPLoginView(View):
    """Handle OTP login - both email request and OTP verification"""
    template_name = 'auth/otp_login.html'
    
    def get(self, request):
        # Check if user is already authenticated
        if request.user.is_authenticated:
            return redirect(self.get_success_url())
        
        # Get next URL for redirect after login
        next_url = request.GET.get('next', '/')
        
        # Clear any existing OTP session data on fresh page load
        # This ensures users always start with email input
        if 'clear' in request.GET or not request.session.get('otp_email'):
            request.session.pop('otp_email', None)
            request.session.pop('otp_next', None)
        
        context = {
            'email_form': EmailOTPRequestForm(),
            'next': next_url,
            'show_otp_input': False,  # Always show email input on GET
        }
        return render(request, self.template_name, context)
    
    def post(self, request):
        action = request.POST.get('action', 'request_otp')
        next_url = request.POST.get('next', '/')
        
        if action == 'request_otp':
            return self.handle_otp_request(request, next_url)
        elif action == 'verify_otp':
            return self.handle_otp_verification(request, next_url)
        else:
            messages.error(request, 'Invalid action.')
            return redirect('auth:login')
    
    def handle_otp_request(self, request, next_url):
        """Handle OTP request"""
        form = EmailOTPRequestForm(request.POST)
        
        if not form.is_valid():
            messages.error(request, 'Please enter a valid email address.')
            return render(request, self.template_name, {
                'email_form': form,
                'next': next_url,
            })
        
        email = form.cleaned_data['email']
        ip_address = get_client_ip(request)
        
        try:
            # Create and send OTP
            otp_request, plain_otp = OTPService.create_otp(email, ip_address)
            
            # Send OTP via email
            if OTPService.send_otp_email(email, plain_otp):
                # Store email in session for verification step
                request.session['otp_email'] = email
                request.session['otp_next'] = next_url
                
                messages.success(request, f'OTP sent to {email}. Please check your inbox.')
                
                # Return to same page showing OTP input
                context = {
                    'email_form': EmailOTPRequestForm(initial={'email': email}),
                    'otp_form': OTPVerificationForm(initial={'email': email}),
                    'show_otp_input': True,
                    'email': email,
                    'next': next_url,
                }
                return render(request, self.template_name, context)
            else:
                messages.error(request, 'Failed to send OTP. Please try again.')
                
        except RateLimitError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, 'An error occurred. Please try again.')
            print(f"OTP request error: {e}")
        
        return render(request, self.template_name, {
            'email_form': form,
            'next': next_url,
        })
    
    def handle_otp_verification(self, request, next_url):
        """Handle OTP verification"""
        form = OTPVerificationForm(request.POST)
        
        if not form.is_valid():
            messages.error(request, 'Please enter a valid 4-digit OTP.')
            email = request.session.get('otp_email', '')
            context = {
                'email_form': EmailOTPRequestForm(initial={'email': email}),
                'otp_form': form,
                'show_otp_input': True,
                'email': email,
                'next': next_url,
            }
            return render(request, self.template_name, context)
        
        email = form.cleaned_data['email']
        otp = form.cleaned_data['otp']
        
        # Verify OTP
        success, message, otp_request = OTPService.verify_otp(email, otp)
        
        if success:
            # Get or create user
            user, created = AuthenticationService.get_or_create_user(email)
            
            # Log user in
            login(request, user)
            
            # Clear OTP session data
            request.session.pop('otp_email', None)
            request.session.pop('otp_next', None)
            
            # Merge session cart into user cart (and abandon session cart)
            CartService.merge_carts(user, request.session.session_key)
            CartService.merge_session_wishlist_to_user(request, user)

            messages.success(request, 'Login successful!')
            
            # Redirect to next URL or default
            if next_url == '/cart/add/':
                return redirect('/')
            return redirect(next_url or '/')
        else:
            messages.error(request, message)
            
            context = {
                'email_form': EmailOTPRequestForm(initial={'email': email}),
                'otp_form': OTPVerificationForm(initial={'email': email}),
                'show_otp_input': True,
                'email': email,
                'next': next_url,
            }
            return render(request, self.template_name, context)
    
    def get_success_url(self):
        """Get redirect URL after login"""
        return self.request.GET.get('next', '/')


class OTPLoginAjaxView(View):
    """Handle AJAX OTP requests"""
    
    @method_decorator(csrf_protect)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        action = request.POST.get('action', 'request_otp')
        
        if action == 'request_otp':
            return self.handle_otp_request(request)
        elif action == 'verify_otp':
            return self.handle_otp_verification(request)
        else:
            return JsonResponse({'success': False, 'error': 'Invalid action'}, status=400)
    
    def handle_otp_request(self, request):
        """Handle AJAX OTP request"""
        form = EmailOTPRequestForm(request.POST)
        
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid email address.',
            }, status=400)
        
        email = form.cleaned_data['email']
        ip_address = get_client_ip(request)
        
        try:
            otp_request, plain_otp = OTPService.create_otp(email, ip_address)
            
            if OTPService.send_otp_email(email, plain_otp):
                request.session['otp_email'] = email
                return JsonResponse({
                    'success': True,
                    'message': f'OTP sent to {email}',
                    'email': email,
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Failed to send OTP. Please try again.',
                }, status=500)
                
        except RateLimitError as e:
            cooldown = OTPService.get_cooldown_remaining(email)
            return JsonResponse({
                'success': False,
                'error': str(e),
                'cooldown': cooldown,
            }, status=429)
        except Exception as e:
            print(f"OTP request error: {e}")
            return JsonResponse({
                'success': False,
                'error': 'An error occurred. Please try again.',
            }, status=500)
    
    def handle_otp_verification(self, request):
        """Handle AJAX OTP verification"""
        form = OTPVerificationForm(request.POST)
        
        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'error': 'Please enter a valid 4-digit OTP.',
            }, status=400)
        
        email = form.cleaned_data['email']
        otp = form.cleaned_data['otp']
        
        success, message, otp_request = OTPService.verify_otp(email, otp)
        
        if success:
            user, created = AuthenticationService.get_or_create_user(email)
            login(request, user)
            
            CartService.merge_carts(user, request.session.session_key)
            CartService.merge_session_wishlist_to_user(request, user)

            request.session.pop('otp_email', None)
            
            next_url = request.POST.get('next', '/')
            
            return JsonResponse({
                'success': True,
                'message': 'Login successful!',
                'redirect': next_url,
            })
        else:
            return JsonResponse({
                'success': False,
                'error': message,
            }, status=400)
    
class LogoutView(View):
    """Handle user logout"""
    
    def get(self, request):
        return self.post(request)
    
    def post(self, request):
        logout(request)
        messages.success(request, 'You have been logged out successfully.')
        return redirect('store:home')


class AccountDashboardView(LoginRequiredMixin, TemplateView):
    """User account dashboard"""
    template_name = 'auth/account_dashboard.html'
    login_url = 'auth:login'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get user's recent orders
        recent_orders = Order.objects.filter(user=user).select_related('address')[:5]
        
        # Get user's addresses
        addresses = Address.objects.filter(user=user, is_snapshot=False).order_by('-is_default', '-created_at')
        
        # Safe profile access (UserProfile may not exist for all users)
        user_phone = ''
        try:
            if hasattr(user, 'profile') and user.profile:
                user_phone = getattr(user.profile, 'phone', '') or ''
        except Exception:
            pass
        
        context.update({
            'recent_orders': recent_orders,
            'addresses': addresses,
            'active_page': 'account',
            'user_phone': user_phone,
        })
        return context


class ProfileView(LoginRequiredMixin, FormView):
    """User profile management"""
    template_name = 'auth/profile.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('auth:profile')
    login_url = 'auth:login'
    
    def get_initial(self):
        initial = super().get_initial()
        user = self.request.user
        initial.update({
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone': getattr(user.profile, 'phone', '') if hasattr(user, 'profile') else '',
        })
        return initial
    
    def form_valid(self, form):
        AuthenticationService.update_user_profile(
            self.request.user,
            first_name=form.cleaned_data['first_name'],
            last_name=form.cleaned_data['last_name'],
            phone=form.cleaned_data['phone'],
        )
        messages.success(self.request, 'Profile updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'account'
        return context


class AddressListView(LoginRequiredMixin, ListView):
    """List user's addresses"""
    template_name = 'auth/address_list.html'
    context_object_name = 'addresses'
    login_url = 'auth:login'
    
    def get_queryset(self):
        return Address.objects.filter(
            user=self.request.user,
            is_snapshot=False
        ).order_by('-is_default', '-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'account'
        return context


class AddressCreateView(LoginRequiredMixin, FormView):
    """Create new address"""
    template_name = 'auth/address_form.html'
    form_class = AddressForm
    success_url = reverse_lazy('auth:address_list')
    login_url = 'auth:login'
    
    def form_valid(self, form):
        address = form.save(commit=False)
        address.user = self.request.user
        address.is_snapshot = False
        
        # If this is set as default, unset other defaults
        if address.is_default:
            Address.objects.filter(user=self.request.user, is_snapshot=False).update(is_default=False)
        
        address.save()
        messages.success(self.request, 'Address added successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'account'
        context['form_title'] = 'Add New Address'
        return context


class AddressUpdateView(LoginRequiredMixin, FormView):
    """Update existing address"""
    template_name = 'auth/address_form.html'
    form_class = AddressForm
    success_url = reverse_lazy('auth:address_list')
    login_url = 'auth:login'
    
    def dispatch(self, request, *args, **kwargs):
        self.address = get_object_or_404(
            Address,
            pk=kwargs.get('pk'),
            user=request.user,
            is_snapshot=False
        )
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['instance'] = self.address
        return kwargs
    
    def form_valid(self, form):
        address = form.save(commit=False)
        
        # If this is set as default, unset other defaults
        if address.is_default:
            Address.objects.filter(user=self.request.user, is_snapshot=False).exclude(pk=address.pk).update(is_default=False)
        
        address.save()
        messages.success(self.request, 'Address updated successfully.')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['active_page'] = 'account'
        context['form_title'] = 'Edit Address'
        context['address'] = self.address
        return context


class AddressDeleteView(LoginRequiredMixin, View):
    """Delete address"""
    login_url = 'auth:login'
    
    def post(self, request, pk):
        address = get_object_or_404(
            Address,
            pk=pk,
            user=request.user,
            is_snapshot=False
        )
        address.delete()
        messages.success(request, 'Address deleted successfully.')
        return redirect('auth:address_list')

