from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account
# Register your models here.

class AccountAdmin(UserAdmin):
    #define what fields will be diaplayed on admin site's account section
    list_display = ('email','first_name','last_name','username','last_login','date_joined','is_active')
    list_display_links = ('email', 'first_name', 'last_name')
    readonly_fields = ('last_login', 'date_joined')
    ordering = ('date_joined',)
    filter_horizontal = ()
    list_filter = ()
    fieldsets = () # make the password field read-only


admin.site.register(Account, AccountAdmin)