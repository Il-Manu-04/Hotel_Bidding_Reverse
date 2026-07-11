from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

class CustomUserAdmin(UserAdmin):
    """
    Admin per CustomUser: aggiunge il campo 'tipo_utente' nelle schermate di 
    creazione e modifica, senza rompere il sistema di sicurezza delle password.
    """
    
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('tipo_utente',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('tipo_utente',)}),
    )

admin.site.register(CustomUser, CustomUserAdmin)
admin.site.register(GestoreProfile)
admin.site.register(ClienteProfile)
