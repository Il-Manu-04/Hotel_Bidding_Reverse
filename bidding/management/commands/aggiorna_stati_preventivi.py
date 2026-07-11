from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from django.conf import settings
from bidding.models import Preventivo
from hotels.models import Camera


class Command(BaseCommand):
    help = 'Aggiorna stati dei preventivi: scaduti, timeout pagamento, pool esaurito (INVALIDATO).'

    def handle(self, *args, **options):
        now = timezone.now()

        # 1) ATTESA con durata_validita superata → SCADUTO
        scaduti_attesa = Preventivo.objects.filter(
            stato=Preventivo.Stato.ATTESA,
            timestamp_creazione__lt=now - timedelta(minutes=1),  # sarà filtrato dopo
        )
        # Filtriamo quelli effettivamente scaduti usando la logica di is_scaduto
        # ma dato che is_scaduto è una property Python, usiamo una query raw-like:
        # timestamp_creazione + durata_validita < now
        from django.db.models import F, ExpressionWrapper, DateTimeField

        scaduti_attesa_ids = []
        for p in scaduti_attesa:
            if p.is_scaduto:
                scaduti_attesa_ids.append(p.pk)

        if scaduti_attesa_ids:
            aggiornati = Preventivo.objects.filter(
                pk__in=scaduti_attesa_ids,
                stato=Preventivo.Stato.ATTESA,
            ).update(stato=Preventivo.Stato.SCADUTO)
            self.stdout.write(f"[SCADUTO] Preventivi ATTESA scaduti: {aggiornati}")
        else:
            self.stdout.write("[SCADUTO] Nessun preventivo ATTESA scaduto.")

        # 2) IN_PAGAMENTO con finestra di pagamento superata → torna ATTESA, libera camera
        scadenza_pagamento = now - timedelta(minutes=settings.DURATA_PAGAMENTO_MINUTI)
        pagamento_scaduti = Preventivo.objects.filter(
            stato=Preventivo.Stato.IN_PAGAMENTO,
            timestamp_accettazione__lt=scadenza_pagamento,
        )
        for p in pagamento_scaduti:
            with transaction.atomic():
                target = Preventivo.objects.select_for_update().get(pk=p.pk)
                if target.stato == Preventivo.Stato.IN_PAGAMENTO:
                    target.camera_assegnata = None
                    target.stato = Preventivo.Stato.ATTESA
                    target.timestamp_accettazione = None
                    target.save(update_fields=['stato', 'camera_assegnata', 'timestamp_accettazione'])
                    self.stdout.write(f"[TIMEOUT PAGAMENTO] Prev. {target.pk} → tornato ATTESA")

        # 3) ATTESA il cui pool si è esaurito → INVALIDATO
        preventivi_attesa = Preventivo.objects.filter(
            stato=Preventivo.Stato.ATTESA,
        ).select_related('richiesta', 'hotel')

        for prev in preventivi_attesa:
            # Ricalcola il pool di camere libere per questo preventivo
            with transaction.atomic():
                target = Preventivo.objects.select_for_update().get(pk=prev.pk)
                if target.stato != Preventivo.Stato.ATTESA:
                    continue

                # Camere occupate nell'intervallo
                camere_occupate = Camera.objects.filter(
                    preventivi__stato__in=[
                        Preventivo.Stato.IN_PAGAMENTO, Preventivo.Stato.ACCETTATO,
                    ],
                    preventivi__richiesta__data_checkin__lt=target.richiesta.data_checkout,
                    preventivi__richiesta__data_checkout__gt=target.richiesta.data_checkin,
                )

                camere_libere = (
                    Camera.objects.select_for_update()
                    .filter(
                        hotel=target.hotel,
                        capienza__gte=target.richiesta.capienza_richiesta,
                    )
                    .exclude(pk__in=camere_occupate)
                )

                if not camere_libere.exists():
                    target.stato = Preventivo.Stato.INVALIDATO
                    target.save(update_fields=['stato'])
                    self.stdout.write(f"[INVALIDATO] Prev. {target.pk} → nessuna camera libera")

        self.stdout.write(self.style.SUCCESS("Aggiornamento stati completato."))