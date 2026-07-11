from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator


class CustomUser(AbstractUser):
    TIPO_UTENTE_CHOICES = [
        ('GESTORE', 'Gestore'),
        ('CLIENTE', 'Cliente'),
    ]
    tipo_utente = models.CharField(
        max_length=10,
        choices=TIPO_UTENTE_CHOICES,
    )

    def __str__(self):
        return f"{self.username} ({self.tipo_utente})"


class GestoreProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='gestore_profile',
    )
    partita_iva = models.CharField(
        max_length=11,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\d{11}$',
                message='La partita IVA deve contenere esattamente 11 cifre.',
            )
        ],
    )
    ragione_sociale = models.CharField(max_length=255)

    def __str__(self):
        return self.ragione_sociale


class ClienteProfile(models.Model):
    user = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='cliente_profile',
    )
    telefono = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.user.username} - {self.telefono}"