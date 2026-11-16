from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower
from django.conf import settings


class CustomUserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifier
    for authentication instead of usernames.
    """

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a user with the given email and password.
        Normalizes the email to lowercase.
        """
        if not email:
            raise ValueError('The Email field must be set.')
        email = self.normalize_email(email).lower()
        extra_fields.setdefault('is_active', True)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        Strictly validates that is_staff and is_superuser are True.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    """
    Custom user model replacing default Django username with normalized email.
    Enforces case-insensitive email uniqueness at database level.
    """

    username = None
    email = models.EmailField('email address', unique=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    google_sub = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        constraints = [
            models.UniqueConstraint(
                Lower('email'),
                name='unique_case_insensitive_email',
            )
        ]

    def __str__(self):
        return self.email


class SavedAddress(models.Model):
    """
    Customer saved delivery address.
    Enforces single-default exclusivity and auto-default on first creation.
    Supports dual-compatibility with frontend field names.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_addresses',
    )
    recipient_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    address_line1 = models.CharField(max_length=255)  # corresponds to houseFlat
    address_line2 = models.CharField(max_length=255, blank=True)  # corresponds to streetArea
    landmark = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    country = models.CharField(max_length=100, default='India')
    label = models.CharField(max_length=50, default='Home')
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Saved Address'
        verbose_name_plural = 'Saved Addresses'
        ordering = ['-is_default', '-created_at']

    def save(self, *args, **kwargs):
        # A user's very first saved address automatically becomes default
        if self.pk is None and not type(self).objects.filter(user=self.user).exists():
            self.is_default = True

        # Single-default exclusivity: unset previous default if this address is default
        if self.is_default:
            type(self).objects.filter(user=self.user, is_default=True).exclude(pk=self.pk).update(is_default=False)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.recipient_name} - {self.address_line1}, {self.city} ({self.pincode})"
