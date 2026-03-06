"""
Custom email backend that handles SSL certificate issues.
"""
import ssl

from django.core.mail.backends.smtp import EmailBackend


class CustomEmailBackend(EmailBackend):
    """
    Custom SMTP email backend that creates an unverified SSL context
    to bypass certificate verification issues on some systems.
    """
    
    @property
    def ssl_context(self):
        """
        Return a custom SSL context that doesn't verify certificates.
        """
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
