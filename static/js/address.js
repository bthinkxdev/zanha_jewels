/**
 * Address Form JavaScript
 * Handles phone number and pincode input validation
 * Restricts input to numbers and allowed separators only
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize phone input restriction
    const phoneInput = document.querySelector('input[name="phone"]');
    if (phoneInput) {
        // Allow: digits, +, spaces, dashes, parentheses
        phoneInput.addEventListener('input', function(e) {
            // Remove any disallowed characters
            let value = this.value;
            // Keep only: digits, +, spaces, dashes, parentheses
            this.value = value.replace(/[^0-9+\s\-()]/g, '');
        });

        // Additional validation on keypress to prevent pasting disallowed chars
        phoneInput.addEventListener('keypress', function(e) {
            const char = String.fromCharCode(e.which);
            const allowedChars = /[0-9+\s\-()]/;
            
            if (!allowedChars.test(char)) {
                e.preventDefault();
                return false;
            }
        });

        // Handle paste event
        phoneInput.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text');
            // Keep only allowed characters from pasted text
            const cleanedText = pastedText.replace(/[^0-9+\s\-()]/g, '');
            // Insert cleaned text
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const before = this.value.substring(0, start);
            const after = this.value.substring(end);
            this.value = before + cleanedText + after;
            
            // Move cursor to end of inserted text
            this.selectionStart = this.selectionEnd = start + cleanedText.length;
        });
    }

    // Initialize pincode input restriction
    const pincodeInput = document.querySelector('input[name="pincode"]');
    if (pincodeInput) {
        // Allow: digits, spaces, dashes only
        pincodeInput.addEventListener('input', function(e) {
            // Remove any disallowed characters
            let value = this.value;
            // Keep only: digits, spaces, dashes
            this.value = value.replace(/[^0-9\s\-]/g, '');
        });

        // Additional validation on keypress
        pincodeInput.addEventListener('keypress', function(e) {
            const char = String.fromCharCode(e.which);
            const allowedChars = /[0-9\s\-]/;
            
            if (!allowedChars.test(char)) {
                e.preventDefault();
                return false;
            }
        });

        // Handle paste event
        pincodeInput.addEventListener('paste', function(e) {
            e.preventDefault();
            const pastedText = (e.clipboardData || window.clipboardData).getData('text');
            // Keep only allowed characters from pasted text
            const cleanedText = pastedText.replace(/[^0-9\s\-]/g, '');
            // Insert cleaned text
            const start = this.selectionStart;
            const end = this.selectionEnd;
            const before = this.value.substring(0, start);
            const after = this.value.substring(end);
            this.value = before + cleanedText + after;
            
            // Move cursor to end of inserted text
            this.selectionStart = this.selectionEnd = start + cleanedText.length;
        });
    }

    // Show helpful error for blocked characters
    [phoneInput, pincodeInput].forEach(input => {
        if (input) {
            input.addEventListener('change', function() {
                const fieldName = this.name === 'phone' ? 'Phone' : 'PIN Code';
                const hasDisallowedChars = this.dataset.lastLength && 
                    this.dataset.lastLength > this.value.length;
                
                this.dataset.lastLength = this.value.length;
            });
        }
    });
});
