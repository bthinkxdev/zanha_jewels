from django import forms
from django.core.validators import EmailValidator, RegexValidator
from django.contrib.auth.models import User

from .models import Address, ContactMessage, NewsletterSubscription, Review


class CartAddForm(forms.Form):
    product_id = forms.IntegerField(min_value=1)
    variant_id = forms.IntegerField(min_value=1, help_text="Variant ID (required)")
    quantity = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("variant_id"):
            return cleaned
        raise forms.ValidationError("Please select a variant.")


class CartUpdateForm(forms.Form):
    item_id = forms.IntegerField(min_value=1)
    quantity = forms.IntegerField(min_value=0)


class CheckoutForm(forms.Form):
    # Address selection
    selected_address = forms.IntegerField(required=False, widget=forms.HiddenInput())
    use_new_address = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())
    
    # Contact and address fields
    full_name = forms.CharField(max_length=120, required=False)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=20, required=False)
    address_line = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Address")
    city = forms.CharField(max_length=80, required=False)
    state = forms.CharField(max_length=80, required=False)
    pincode = forms.CharField(max_length=10, required=False)
    
    # Payment (COD and Razorpay only; WhatsApp removed)
    payment = forms.ChoiceField(
        choices=[("cod", "Cash on Delivery"), ("razorpay", "Online Payment")],
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields["payment"].initial = "cod"
        for field in self.fields.values():
            if isinstance(field.widget, (forms.RadioSelect, forms.HiddenInput)):
                continue
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-input".strip()
    
    def clean(self):
        try:
            cleaned_data = super().clean()
            selected_address = cleaned_data.get('selected_address')
            use_new_address = cleaned_data.get('use_new_address')
            is_guest = not self.user

            # Guest: must use new address and email is required
            if is_guest:
                use_new_address = True
                cleaned_data['use_new_address'] = True
                selected_address = None

            # If using existing address (authenticated only)
            if selected_address and not use_new_address and self.user:
                try:
                    address = Address.objects.get(pk=selected_address, user=self.user, is_snapshot=False)
                    # Populate form data from selected address
                    cleaned_data['full_name'] = address.full_name
                    cleaned_data['phone'] = address.phone
                    cleaned_data['email'] = address.email
                    cleaned_data['address_line'] = address.address_line
                    cleaned_data['city'] = address.city
                    cleaned_data['state'] = address.state
                    cleaned_data['pincode'] = address.pincode
                except Address.DoesNotExist:
                    raise forms.ValidationError("Selected address not found.")
                except Exception as e:
                    raise forms.ValidationError("Failed to retrieve address. Please try again.")
            else:
                # If not using existing address and no saved addresses, require new address
                if not use_new_address and not selected_address:
                    try:
                        # Check if user has any saved addresses
                        if self.user and Address.objects.filter(user=self.user, is_snapshot=False).exists():
                            raise forms.ValidationError("Please select an address or add a new one.")
                        else:
                            # No saved addresses, require new address
                            use_new_address = True
                            cleaned_data['use_new_address'] = True
                    except Exception as e:
                        raise forms.ValidationError("Failed to retrieve addresses. Please try again.")
                
                # Validate new address fields
                if use_new_address:
                    required_fields = ['full_name', 'phone', 'address_line', 'city', 'state', 'pincode']
                    if is_guest:
                        required_fields = ['full_name', 'email', 'phone', 'address_line', 'city', 'state', 'pincode']
                    for field in required_fields:
                        if not cleaned_data.get(field):
                            self.add_error(field, 'This field is required.')
                    
                    # Validate phone number if provided
                    if cleaned_data.get('phone'):
                        self._validate_phone(cleaned_data.get('phone'))
                    
                    # Validate pincode if provided
                    if cleaned_data.get('pincode'):
                        self._validate_pincode(cleaned_data.get('pincode'))
            
            return cleaned_data
        except forms.ValidationError:
            raise
        except Exception as e:
            raise forms.ValidationError("An error occurred. Please try again.")
    
    def _validate_phone(self, phone):
        """Validate phone number"""
        if not phone:
            self.add_error('phone', 'Phone number is required.')
            return
        
        phone = phone.strip()
        # Remove common separators and country code
        cleaned_phone = phone.replace('+91', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        
        # Check if it's all digits
        if not cleaned_phone.isdigit():
            self.add_error('phone', 'Phone number should contain only digits (and optional +91 prefix).')
            return
        
        # Check length - should be 10 digits for India
        if len(cleaned_phone) != 10:
            self.add_error('phone', 'Phone number must be exactly 10 digits.')
            return
        
        # Check if first digit is 6, 7, 8, or 9 (valid for Indian mobile numbers)
        if cleaned_phone[0] not in ['6', '7', '8', '9']:
            self.add_error('phone', 'Phone number should start with 6, 7, 8, or 9.')
    
    def _validate_pincode(self, pincode):
        """Validate pincode"""
        if not pincode:
            self.add_error('pincode', 'PIN code is required.')
            return
        
        pincode = pincode.strip()
        # Remove spaces and dashes
        cleaned_pincode = pincode.replace('-', '').replace(' ', '')
        
        # Check if it's all digits
        if not cleaned_pincode.isdigit():
            self.add_error('pincode', 'PIN code should contain only digits.')
            return
        
        # Check length - should be 6 digits for India
        if len(cleaned_pincode) != 6:
            self.add_error('pincode', 'PIN code must be exactly 6 digits.')
            return
        
        # Check if pincode doesn't start with 0 (Indian pincodes don't start with 0)
        if cleaned_pincode[0] == '0':
            self.add_error('pincode', 'PIN code cannot start with 0.')


class ContactForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ["name", "email", "subject", "message"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-input".strip()


class NewsletterForm(forms.ModelForm):
    class Meta:
        model = NewsletterSubscription
        fields = ["email"]


class EmailOTPRequestForm(forms.Form):
    """Form for requesting OTP via email"""
    email = forms.EmailField(
        max_length=254,
        required=True,
        validators=[EmailValidator()],
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email',
            'autofocus': True,
        })
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email', '').lower().strip()
        return email


class OTPVerificationForm(forms.Form):
    """Form for verifying OTP"""
    email = forms.EmailField(widget=forms.HiddenInput())
    otp = forms.CharField(
        max_length=4,
        min_length=4,
        required=True,
        validators=[
            RegexValidator(
                regex=r'^\d{4}$',
                message='OTP must be exactly 4 digits',
            )
        ],
        widget=forms.TextInput(attrs={
            'class': 'form-input otp-input',
            'placeholder': '0000',
            'maxlength': '4',
            'pattern': '[0-9]{4}',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
        })
    )
    
    def clean_otp(self):
        otp = self.cleaned_data.get('otp', '').strip()
        if not otp.isdigit():
            raise forms.ValidationError('OTP must contain only digits')
        return otp


class UserProfileForm(forms.Form):
    """Form for updating user profile"""
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'First Name',
        })
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Last Name',
        })
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Phone Number (10 digits)',
            'inputmode': 'tel',
            'pattern': r'[0-9+\s\-()]*',
            'data-only-numbers': 'true',
            'autocomplete': 'tel',
        })
    )
    
    def clean_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('phone', '').strip()
        
        # If phone is empty, it's optional so return
        if not phone:
            return phone
        
        # Remove common separators and country code
        cleaned_phone = phone.replace('+91', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        
        # Check if it's all digits
        if not cleaned_phone.isdigit():
            raise forms.ValidationError('Phone number should contain only digits (and optional +91 prefix).')
        
        # Check length - should be 10 digits for India
        if len(cleaned_phone) != 10:
            raise forms.ValidationError('Phone number must be exactly 10 digits.')
        
        # Check if first digit is 6, 7, 8, or 9 (valid for Indian mobile numbers)
        if cleaned_phone[0] not in ['6', '7', '8', '9']:
            raise forms.ValidationError('Phone number should start with 6, 7, 8, or 9.')
        
        return phone


class AddressForm(forms.ModelForm):
    """Form for adding/editing shipping addresses"""
    class Meta:
        model = Address
        fields = ['full_name', 'phone', 'address_line', 'city', 'state', 'pincode', 'is_default']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Full Name',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Phone Number (10 digits)',
                'inputmode': 'tel',
                'pattern': r'[0-9+\s\-()]*',
                'maxlength': '15',
                'data-only-numbers': 'true',
                'autocomplete': 'tel',
            }),
            'address_line': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Street Address',
                'rows': 3,
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City',
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'State',
            }),
            'pincode': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'PIN Code (6 digits)',
                'inputmode': 'numeric',
                'pattern': r'[0-9\s\-]*',
                'maxlength': '8',
                'data-only-numbers': 'true',
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'form-checkbox',
            }),
        }
    
    def clean_phone(self):
        """Validate phone number"""
        phone = self.cleaned_data.get('phone', '').strip()
        
        if not phone:
            raise forms.ValidationError('Phone number is required.')
        
        # Remove common separators and country code
        cleaned_phone = phone.replace('+91', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '')
        
        # Check if it's all digits
        if not cleaned_phone.isdigit():
            raise forms.ValidationError('Phone number should contain only digits (and optional +91 prefix).')
        
        # Check length - should be 10 digits for India
        if len(cleaned_phone) != 10:
            raise forms.ValidationError('Phone number must be exactly 10 digits.')
        
        # Check if first digit is 6, 7, 8, or 9 (valid for Indian mobile numbers)
        if cleaned_phone[0] not in ['6', '7', '8', '9']:
            raise forms.ValidationError('Phone number should start with 6, 7, 8, or 9.')
        
        return phone
    
    def clean_pincode(self):
        """Validate pincode"""
        pincode = self.cleaned_data.get('pincode', '').strip()
        
        if not pincode:
            raise forms.ValidationError('PIN code is required.')
        
        # Remove spaces and dashes
        cleaned_pincode = pincode.replace('-', '').replace(' ', '')
        
        # Check if it's all digits
        if not cleaned_pincode.isdigit():
            raise forms.ValidationError('PIN code should contain only digits.')
        
        # Check length - should be 6 digits for India
        if len(cleaned_pincode) != 6:
            raise forms.ValidationError('PIN code must be exactly 6 digits.')
        
        # Check if pincode doesn't start with 0 (Indian pincodes don't start with 0)
        if cleaned_pincode[0] == '0':
            raise forms.ValidationError('PIN code cannot start with 0.')
        
        return pincode


class ReviewForm(forms.ModelForm):
    """
    User-facing review form.

    Business rules enforced here:
    - Rating is required and must be between 1–5.
    - Title and comment are optional.
    """

    class Meta:
        model = Review
        fields = ["rating", "title", "comment"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Basic styling hooks for frontend
        self.fields["rating"].widget = forms.RadioSelect(
            choices=[(i, f"{i} Star" if i == 1 else f"{i} Stars") for i in range(1, 6)]
        )
        self.fields["title"].required = False
        self.fields["comment"].required = False
        for name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} form-input".strip()

    def clean_rating(self):
        rating = self.cleaned_data.get("rating")
        if rating is None:
            raise forms.ValidationError("Please select a rating.")
        try:
            rating_int = int(rating)
        except (TypeError, ValueError):
            raise forms.ValidationError("Invalid rating value.")
        if rating_int < 1 or rating_int > 5:
            raise forms.ValidationError("Rating must be between 1 and 5 stars.")
        return rating_int

