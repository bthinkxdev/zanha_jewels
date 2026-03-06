/**
 * OTP Login JavaScript
 * Handles email validation, OTP input, countdown timer, and AJAX requests
 */

document.addEventListener('DOMContentLoaded', function() {
    // Email validation
    const emailForm = document.getElementById('emailForm');
    const emailInput = document.querySelector('input[name="email"]');
    const sendOtpBtn = document.getElementById('sendOtpBtn');
    const emailError = document.getElementById('emailError');

    if (emailInput && sendOtpBtn) {
        // Real-time email validation
        emailInput.addEventListener('input', function() {
            const email = this.value.trim();
            const isValid = validateEmail(email);
            
            if (email.length > 0 && !isValid) {
                emailError.textContent = 'Please enter a valid email address';
                sendOtpBtn.disabled = true;
            } else {
                emailError.textContent = '';
                sendOtpBtn.disabled = email.length === 0;
            }
        });

        // Email form submission
        if (emailForm) {
            emailForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const email = emailInput.value.trim();
                if (!validateEmail(email)) {
                    emailError.textContent = 'Please enter a valid email address';
                    return;
                }

                // Show loading state
                setButtonLoading(sendOtpBtn, true);
                
                // Submit form
                this.submit();
            });
        }
    }

    // OTP Input handling
    const otpInputGroup = document.getElementById('otpInputGroup');
    const otpDigits = document.querySelectorAll('.otp-digit');
    const otpHidden = document.getElementById('otpHidden');
    const otpForm = document.getElementById('otpForm');
    const verifyOtpBtn = document.getElementById('verifyOtpBtn');
    const otpError = document.getElementById('otpError');

    if (otpDigits.length > 0) {
        // Auto-focus first input
        otpDigits[0].focus();

        // Handle OTP digit input
        otpDigits.forEach((input, index) => {
            input.addEventListener('input', function(e) {
                const value = this.value;
                
                // Only allow digits
                this.value = value.replace(/[^0-9]/g, '');
                
                if (this.value.length === 1) {
                    // Move to next input
                    if (index < otpDigits.length - 1) {
                        otpDigits[index + 1].focus();
                    }
                }
                
                // Update hidden input
                updateOtpValue();
                
                // Clear error
                otpError.textContent = '';
            });

            input.addEventListener('keydown', function(e) {
                // Handle backspace
                if (e.key === 'Backspace' && this.value === '' && index > 0) {
                    otpDigits[index - 1].focus();
                }
                
                // Handle arrow keys
                if (e.key === 'ArrowLeft' && index > 0) {
                    otpDigits[index - 1].focus();
                }
                if (e.key === 'ArrowRight' && index < otpDigits.length - 1) {
                    otpDigits[index + 1].focus();
                }
            });

            // Handle paste
            input.addEventListener('paste', function(e) {
                e.preventDefault();
                const pastedData = e.clipboardData.getData('text').replace(/[^0-9]/g, '');
                
                if (pastedData.length === 4) {
                    otpDigits.forEach((digit, i) => {
                        digit.value = pastedData[i] || '';
                    });
                    updateOtpValue();
                    otpDigits[3].focus();
                }
            });
        });

        // Update hidden OTP input
        function updateOtpValue() {
            const otp = Array.from(otpDigits).map(input => input.value).join('');
            if (otpHidden) {
                otpHidden.value = otp;
            }
            
            // Enable/disable verify button
            if (verifyOtpBtn) {
                verifyOtpBtn.disabled = otp.length !== 4;
            }
        }

        // OTP form submission
        if (otpForm) {
            otpForm.addEventListener('submit', function(e) {
                const otp = otpHidden.value;
                
                if (otp.length !== 4) {
                    e.preventDefault();
                    otpError.textContent = 'Please enter a valid 4-digit OTP';
                    return;
                }

                // Show loading state
                setButtonLoading(verifyOtpBtn, true);
            });
        }
    }

    // Countdown timer for resend OTP
    const resendOtpBtn = document.getElementById('resendOtpBtn');
    const countdownSpan = document.getElementById('countdown');
    
    if (resendOtpBtn && countdownSpan) {
        let countdown = 60;
        
        const timer = setInterval(function() {
            countdown--;
            countdownSpan.textContent = countdown;
            
            if (countdown <= 0) {
                clearInterval(timer);
                resendOtpBtn.disabled = false;
                resendOtpBtn.innerHTML = 'Resend OTP';
            }
        }, 1000);

        // Handle resend OTP
        resendOtpBtn.addEventListener('click', function() {
            var nextInput = document.querySelector('input[name="next"]');
            var nextUrl = (nextInput && nextInput.value) ? nextInput.value : '/';
            var baseUrl = (typeof window.AUTH_LOGIN_URL === 'string' && window.AUTH_LOGIN_URL) ? window.AUTH_LOGIN_URL : '/auth/login/';
            var sep = baseUrl.indexOf('?') >= 0 ? '&' : '?';
            window.location.href = baseUrl + sep + 'next=' + encodeURIComponent(nextUrl);
        });
    }

    // Change email button
    const changeEmailBtn = document.getElementById('changeEmailBtn');
    if (changeEmailBtn) {
        changeEmailBtn.addEventListener('click', function() {
            // Show email step and hide OTP step
            const emailStep = document.getElementById('emailStep');
            const otpStep = document.getElementById('otpStep');
            
            if (emailStep && otpStep) {
                emailStep.style.display = 'block';
                otpStep.style.display = 'none';
                
                // Clear OTP inputs
                otpDigits.forEach(input => input.value = '');
                if (otpHidden) otpHidden.value = '';
                
                // Focus on email input
                if (emailInput) emailInput.focus();
            } else {
                // Fallback: reload page
                const nextUrl = document.querySelector('input[name="next"]')?.value || '/';
                window.location.href = `${window.location.pathname}?next=${encodeURIComponent(nextUrl)}`;
            }
        });
    }

    // Helper functions
    function validateEmail(email) {
        const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return re.test(email);
    }

    function setButtonLoading(button, isLoading) {
        if (!button) return;
        
        const btnText = button.querySelector('.btn-text');
        const btnLoader = button.querySelector('.btn-loader');
        
        if (isLoading) {
            button.disabled = true;
            if (btnText) btnText.style.display = 'none';
            if (btnLoader) btnLoader.style.display = 'inline-flex';
        } else {
            button.disabled = false;
            if (btnText) btnText.style.display = 'inline';
            if (btnLoader) btnLoader.style.display = 'none';
        }
    }
});

