from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from users.models import ClienteProfile
from hotels.models import Hotel, Camera, Servizio


class Richiesta(models.Model):
    """Richiesta di preventivi inviata da un cliente a uno o più hotel."""
    cliente = models.ForeignKey(ClienteProfile, on_delete=models.CASCADE, related_name='richieste')
    data_checkin = models.DateField(help_text="Data di arrivo prevista")
    data_checkout = models.DateField(help_text="Data di partenza prevista")
    capienza_richiesta = models.PositiveIntegerField(default=1, help_text="Numero di ospiti da ospitare")
    budget_massimo = models.DecimalField(
        max_digits=8, decimal_places=2,
        null=True, blank=True,
        help_text="Budget massimo per notte (opzionale)"
    )
    messaggio_cliente = models.TextField(blank=True, help_text="Messaggio opzionale per gli hotel contattati")
    hotels_contattati = models.ManyToManyField(Hotel, blank=True, related_name='richieste_ricevute')
    citta_cercata = models.CharField(max_length=255, null=True, blank=True, help_text="Città cercata dal cliente")
    stelle_minime = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Stelle minime richieste")
    servizi_richiesti = models.ManyToManyField(Servizio, blank=True, related_name='richieste')
    durata_richiesta = models.PositiveIntegerField(
        default=2880,
        validators=[MinValueValidator(1)],
        help_text="Minuti entro cui i gestori devono rispondere (default 48 ore)"
    )
    data_creazione = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Richiesta"
        verbose_name_plural = "Richieste"
        ordering = ['-data_creazione']

    def __str__(self):
        return (f"Richiesta {self.id} — {self.cliente.user.get_full_name()} "
                f"({self.data_checkin} → {self.data_checkout})")

    @property
    def is_scaduta(self):
        """True se la richiesta ha superato la durata massima per ricevere risposte."""
        scadenza = self.data_creazione + timedelta(minutes=self.durata_richiesta)
        return timezone.now() > scadenza

    @property
    def is_passata(self):
        """True se il check-out è già passato (soggiorno concluso)."""
        from datetime import date
        return date.today() > self.data_checkout


class Preventivo(models.Model):
    """Preventivo inviato da un gestore a una richiesta cliente."""

    class Stato(models.TextChoices):
        ATTESA = 'ATTESA', 'In Attesa'
        IN_PAGAMENTO = 'IN_PAGAMENTO', 'In Pagamento'
        ACCETTATO = 'ACCETTATO', 'Accettato'
        RIFIUTATO = 'RIFIUTATO', 'Rifiutato'
        SCADUTO = 'SCADUTO', 'Scaduto'
        INVALIDATO = 'INVALIDATO', 'Invalidato'

    richiesta = models.ForeignKey(Richiesta, on_delete=models.CASCADE, related_name='preventivi')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='preventivi_inviati')
    stato = models.CharField(max_length=15, choices=Stato.choices, default=Stato.ATTESA)
    timestamp_creazione = models.DateTimeField(auto_now_add=True)
    timestamp_accettazione = models.DateTimeField(null=True, blank=True)
    timestamp_pagamento = models.DateTimeField(null=True, blank=True)
    riferimento_pagamento = models.CharField(max_length=100, null=True, blank=True, unique=True)
    durata_validita = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1)],
        help_text="Validità del preventivo in minuti"
    )
    prezzo_proposto = models.DecimalField(max_digits=8, decimal_places=2)
    messaggio_gestore = models.TextField(blank=True, help_text="Messaggio opzionale del gestore")
    camera_assegnata = models.ForeignKey(
        Camera,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='preventivi'
    )

    class Meta:
        verbose_name = "Preventivo"
        verbose_name_plural = "Preventivi"
        ordering = ['-timestamp_creazione']

    def __str__(self):
        return f"Prev. {self.id} — {self.hotel.nome} → Rich. {self.richiesta.id} [{self.stato}]"

    @property
    def is_scaduto(self):
        """Verifica se il preventivo è scaduto in base allo stato e ai timestamp."""
        now = timezone.now()
        if self.stato == self.Stato.ATTESA:
            scadenza = self.timestamp_creazione + timedelta(minutes=self.durata_validita)
            return now > scadenza
        if self.stato == self.Stato.IN_PAGAMENTO:
            if self.timestamp_accettazione is None:
                return False
            scadenza = self.timestamp_accettazione + timedelta(
                minutes=settings.DURATA_PAGAMENTO_MINUTI
            )
            return now > scadenza
        return False