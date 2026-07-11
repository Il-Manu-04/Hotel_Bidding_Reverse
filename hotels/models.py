from django.db import models
from users.models import GestoreProfile


class Servizio(models.Model):
    """Servizio offerto da un hotel (es. WiFi, parcheggio, piscina)."""
    nome = models.CharField(max_length=100, unique=True)
    icona = models.CharField(max_length=50, blank=True, help_text="Classe icona FontAwesome opzionale")

    class Meta:
        verbose_name = "Servizio"
        verbose_name_plural = "Servizi"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Hotel(models.Model):
    gestore = models.ForeignKey(
        GestoreProfile,
        on_delete=models.CASCADE,
        related_name='hotels',
    )
    nome = models.CharField(max_length=255)
    citta = models.CharField(max_length=255)
    stelle = models.PositiveSmallIntegerField(
        choices=[(i, f"{i} stelle") for i in range(1, 6)],
    )
    foto = models.ImageField(upload_to='hotels/foto/', blank=True, null=True)
    descrizione = models.TextField(blank=True, help_text="Descrizione dell'hotel (opzionale)")
    servizi = models.ManyToManyField(Servizio, blank=True, related_name='hotels')

    def __str__(self):
        return f"{self.nome} - {self.citta} ({self.stelle}★)"


class Camera(models.Model):
    hotel = models.ForeignKey(
        Hotel,
        on_delete=models.CASCADE,
        related_name='camere',
    )
    nome = models.CharField(max_length=255, help_text="Nome/tipologia della camera")
    capienza = models.PositiveIntegerField(default=2, help_text="Numero massimo di ospiti")
    prezzo_indicativo = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Prezzo indicativo per notte (opzionale)"
    )
    foto = models.ImageField(upload_to='camere/foto/', blank=True, null=True, help_text="Foto della camera (opzionale)")

    def __str__(self):
        return f"{self.nome} (x{self.capienza}) - {self.hotel.nome}"
