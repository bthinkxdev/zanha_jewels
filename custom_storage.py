import re

from storages.backends.s3boto3 import S3Boto3Storage


class MediaFileStorage(S3Boto3Storage):
    # Store all media files under the S3 "queen-orange/media" prefix
    location = "testing/media"
    file_overwrite = False
    default_acl = None  # Don't use ACLs, rely on bucket policy
    
    def get_available_name(self, name, max_length=None):
        """
        Sanitize the filename before uploading to S3
        to avoid URL encoding issues.
        """
        # Replace spaces with underscores
        name = re.sub(r'[\s]+', '_', name)
        # Remove or replace problematic characters
        name = re.sub(r'[()[\]{}\"\'`]', '_', name)
        # Remove multiple consecutive underscores
        name = re.sub(r'_+', '_', name)
        
        return super().get_available_name(name, max_length)

    def url(self, name, parameters=None, expire=None, http_method=None):
        """
        Generate clean S3 URL without extra quotes
        """
        url = super().url(name, parameters=parameters, expire=expire, http_method=http_method)
        # Strip any stray quotes from the URL
        url = url.strip('\'"')
        return url