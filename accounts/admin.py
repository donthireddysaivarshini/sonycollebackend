from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, SavedAddress


class SavedAddressInline(admin.StackedInline):
    model = SavedAddress
    extra = 0
    fields = (
        'label',
        'recipient_name',
        'phone',
        'address_line1',
        'address_line2',
        'landmark',
        'city',
        'state',
        'pincode',
        'country',
        'is_default',
    )


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = (
        'email',
        'first_name',
        'last_name',
        'phone',
        'is_staff',
        'is_active',
        'created_at',
    )
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-created_at',)
    inlines = [SavedAddressInline]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone', 'google_sub')}),
        (
            'Permissions',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
            },
        ),
    )


@admin.register(SavedAddress)
class SavedAddressAdmin(admin.ModelAdmin):
    list_display = (
        'recipient_name',
        'user',
        'phone',
        'city',
        'state',
        'pincode',
        'is_default',
        'created_at',
    )
    list_filter = ('is_default', 'state', 'city')
    search_fields = ('recipient_name', 'phone', 'pincode', 'user__email', 'address_line1')
    ordering = ('-is_default', '-created_at')
