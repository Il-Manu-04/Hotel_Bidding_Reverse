import uuid
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.urls import reverse
from django.views.generic import FormView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db.models import Q, Exists, OuterRef
from django.db import transaction
from .models import Richiesta, Preventivo
from hotels.models import Hotel, Camera, Servizio


# ===========================================================================
# Form per la creazione della richiesta (Fase 3 – step 1)
# ===========================================================================
class RichiestaForm(forms.Form):
    data_checkin = forms.DateField(label="Check-in", widget=forms.DateInput(attrs={'type': 'date'}))
    data_checkout = forms.DateField(label="Check-out", widget=forms.DateInput(attrs={'type': 'date'}))
    capienza_richiesta = forms.IntegerField(label="Numero ospiti", min_value=1, initial=1)
    budget_massimo = forms.DecimalField(label="Budget massimo per notte (€, opzionale)", max_digits=8, decimal_places=2, required=False)
    citta = forms.CharField(label="Città (opzionale)", max_length=255, required=False)
    nome_hotel = forms.CharField(label="Nome hotel (opzionale)", max_length=255, required=False)
    stelle_minime = forms.IntegerField(label="Stelle minime (opzionale)", min_value=1, max_value=5, required=False)
    servizi_richiesti = forms.ModelMultipleChoiceField(label="Servizi richiesti (opzionale)", queryset=Servizio.objects.all(), required=False, widget=forms.CheckboxSelectMultiple)
    messaggio_cliente = forms.CharField(label="Messaggio per gli hotel (opzionale)", widget=forms.Textarea(attrs={'rows': 3}), required=False)

    def clean(self):
        cleaned = super().clean()
        checkin = cleaned.get('data_checkin')
        checkout = cleaned.get('data_checkout')
        if checkin and checkout and checkout <= checkin:
            raise forms.ValidationError("La data di check-out deve essere successiva al check-in.")
        return cleaned


# ===========================================================================
# Form per la creazione del preventivo (Fase 4 – step risposta gestore)
# ===========================================================================
class CreaPreventivoForm(forms.Form):
    hotel = forms.ModelChoiceField(queryset=Hotel.objects.none(), label="Hotel", empty_label="Seleziona un hotel")
    prezzo_proposto = forms.DecimalField(max_digits=8, decimal_places=2, label="Prezzo per notte (€)")
    durata_validita = forms.IntegerField(min_value=1, initial=60, label="Validità preventivo (minuti)")
    messaggio_gestore = forms.CharField(label="Messaggio per il cliente (opzionale)", widget=forms.Textarea(attrs={'rows': 2}), required=False)

    def __init__(self, *args, gestore_profile=None, richiesta=None, **kwargs):
        super().__init__(*args, **kwargs)
        if gestore_profile and richiesta:
            hotel_ids = gestore_profile.hotels.values_list('id', flat=True)

            #hotel per cui gestore ha già mandato preventivi per quella stessa richiesta
            hotel_gia_risposto = Preventivo.objects.filter(
                richiesta=richiesta,
                hotel__gestore=gestore_profile
            ).values_list('hotel_id', flat=True)

            self.fields['hotel'].queryset = Hotel.objects.filter(
                id__in=richiesta.hotels_contattati.values_list('id', flat=True),
                gestore=gestore_profile,
            ).exclude(id__in=hotel_gia_risposto)


# ===========================================================================
# Helper: pool di camere libere con select_for_update
# ===========================================================================
def _get_camere_libere_pool(hotel, data_checkin, data_checkout, capienza_richiesta):
    camere_occupate = Camera.objects.filter(
        preventivi__stato__in=[Preventivo.Stato.IN_PAGAMENTO, Preventivo.Stato.ACCETTATO],
        preventivi__richiesta__data_checkin__lt=data_checkout,
        preventivi__richiesta__data_checkout__gt=data_checkin,
    )
    return Camera.objects.select_for_update().filter(hotel=hotel, capienza__gte=capienza_richiesta).exclude(pk__in=camere_occupate).order_by('pk')


def _check_pool_disponibile(hotel, data_checkin, data_checkout, capienza_richiesta):
    """Per il controllo proattivo: esclude solo camere ACCETTATO (non IN_PAGAMENTO).
    IN_PAGAMENTO è temporaneo — il cliente potrebbe non pagare e liberare la camera."""
    camere_occupate = Camera.objects.filter(
        preventivi__stato=Preventivo.Stato.ACCETTATO,
        preventivi__richiesta__data_checkin__lt=data_checkout,
        preventivi__richiesta__data_checkout__gt=data_checkin,
    )
    return Camera.objects.filter(
        hotel=hotel, capienza__gte=capienza_richiesta
    ).exclude(pk__in=camere_occupate).exists()


# ===========================================================================
# CreaRichiestaView (pubblica)
# ===========================================================================
class CreaRichiestaView(FormView):
    template_name = 'bidding/crea_richiesta.html'
    form_class = RichiestaForm

    def get_initial(self):
        dati = self.request.session.get('dati_richiesta')
        if not dati:
            return {}
        from datetime import date
        initial = {
            'data_checkin': dati.get('data_checkin'),
            'data_checkout': dati.get('data_checkout'),
            'capienza_richiesta': dati.get('capienza_richiesta'),
            'citta': dati.get('citta', ''),
            'nome_hotel': dati.get('nome_hotel', ''),
            'stelle_minime': dati.get('stelle_minime'),
            'messaggio_cliente': dati.get('messaggio_cliente', ''),
        }
        if dati.get('budget_massimo'):
            initial['budget_massimo'] = dati['budget_massimo']
        if dati.get('servizi_ids'):
            initial['servizi_richiesti'] = [int(sid) for sid in dati['servizi_ids']]
        return initial

    def form_valid(self, form):
        data = form.cleaned_data
        self.request.session['dati_richiesta'] = {
            'data_checkin': data['data_checkin'].isoformat(),
            'data_checkout': data['data_checkout'].isoformat(),
            'capienza_richiesta': data['capienza_richiesta'],
            'budget_massimo': str(data['budget_massimo']) if data['budget_massimo'] else None,
            'citta': data.get('citta') or '',
            'nome_hotel': data.get('nome_hotel') or '',
            'stelle_minime': data.get('stelle_minime'),
            'servizi_ids': list(data['servizi_richiesti'].values_list('id', flat=True)),
            'messaggio_cliente': data.get('messaggio_cliente') or '',
        }
        return redirect('bidding:seleziona_hotel')


# ===========================================================================
# SelezionaHotelView (pubblica)
# ===========================================================================
class SelezionaHotelView(View):
    template_name = 'bidding/seleziona_hotel.html'

    def _get_session_data(self):
        raw = self.request.session.get('dati_richiesta')
        if not raw:
            return None
        dati = dict(raw)  # copia per non modificare la sessione originale
        from datetime import date
        from decimal import Decimal
        if isinstance(dati['data_checkin'], str):
            dati['data_checkin'] = date.fromisoformat(dati['data_checkin'])
        if isinstance(dati['data_checkout'], str):
            dati['data_checkout'] = date.fromisoformat(dati['data_checkout'])
        dati['capienza_richiesta'] = int(dati['capienza_richiesta'])
        budget = dati.get('budget_massimo')
        if budget is not None and not isinstance(budget, Decimal):
            dati['budget_massimo'] = Decimal(str(budget)) if str(budget) else None
        else:
            dati['budget_massimo'] = budget if isinstance(budget, Decimal) else None
        stelle = dati.get('stelle_minime')
        if stelle is not None and not isinstance(stelle, int):
            dati['stelle_minime'] = int(stelle)
        else:
            dati['stelle_minime'] = stelle
        dati['servizi_ids'] = [int(sid) if not isinstance(sid, int) else sid for sid in dati.get('servizi_ids', [])]
        return dati

    def get(self, request):
        dati = self._get_session_data()
        if not dati:
            messages.warning(request, "Devi prima compilare i criteri di ricerca.")
            return redirect('bidding:crea_richiesta')
        hotels = Hotel.objects.all()
        citta = dati.get('citta', '').strip()
        if citta:
            hotels = hotels.filter(citta__icontains=citta)
        nome_hotel = dati.get('nome_hotel', '').strip()
        if nome_hotel:
            hotels = hotels.filter(nome__icontains=nome_hotel)
        if dati['stelle_minime']:
            hotels = hotels.filter(stelle__gte=dati['stelle_minime'])
        if dati['servizi_ids']:
            for sid in dati['servizi_ids']:
                hotels = hotels.filter(servizi__id=sid)
        camere_occupate = Camera.objects.filter(
            preventivi__stato__in=[Preventivo.Stato.IN_PAGAMENTO, Preventivo.Stato.ACCETTATO],
            preventivi__richiesta__data_checkin__lt=dati['data_checkout'],
            preventivi__richiesta__data_checkout__gt=dati['data_checkin'],
        )
        camere_libere = Camera.objects.filter(
            hotel=OuterRef('pk'), capienza__gte=dati['capienza_richiesta'],
        ).exclude(pk__in=camere_occupate)
        if dati['budget_massimo'] is not None:
            camere_libere = camere_libere.filter(Q(prezzo_indicativo__lte=dati['budget_massimo']) | Q(prezzo_indicativo__isnull=True))
        hotels = hotels.filter(Exists(camere_libere)).distinct().prefetch_related('camere')
        return render(request, self.template_name, {
            'hotels': hotels, 'dati': dati,
            'servizi_richiesti': Servizio.objects.filter(id__in=dati['servizi_ids']) if dati['servizi_ids'] else [],
        })

    def post(self, request):
        dati = self._get_session_data()
        if not dati:
            messages.error(request, "Sessione scaduta.")
            return redirect('bidding:crea_richiesta')
        hotel_ids = request.POST.getlist('hotels')
        if not hotel_ids:
            messages.error(request, "Seleziona almeno un hotel.")
            return self.get(request)
        hotel_ids_str = [str(pk) for pk in hotel_ids]
        if not request.user.is_authenticated:
            request.session['hotel_ids_pending'] = hotel_ids_str
            messages.info(request, "Accedi o registrati come cliente per inviare la richiesta.")
            return redirect(f"{reverse('login')}?next={reverse('bidding:completa_richiesta')}")
        if request.user.tipo_utente != 'CLIENTE':
            messages.warning(request, "Solo i clienti possono inviare richieste. Per provare la piattaforma, registra un account cliente.")
            return redirect('home')
        hotel_ids = [int(pk) for pk in hotel_ids_str]
        with transaction.atomic():
            r = Richiesta.objects.create(
                cliente=request.user.cliente_profile,
                data_checkin=dati['data_checkin'], data_checkout=dati['data_checkout'],
                capienza_richiesta=dati['capienza_richiesta'], budget_massimo=dati['budget_massimo'],
                citta_cercata=dati.get('citta') or None, stelle_minime=dati['stelle_minime'],
                messaggio_cliente=dati.get('messaggio_cliente') or '',
            )
            r.hotels_contattati.set(hotel_ids)
            if dati['servizi_ids']:
                r.servizi_richiesti.set(dati['servizi_ids'])
        del request.session['dati_richiesta']
        messages.success(request, "Richiesta inviata con successo!")
        return redirect('bidding:dashboard_cliente')


# ===========================================================================
# CompletaRichiestaDopoLoginView
# ===========================================================================
class CompletaRichiestaDopoLoginView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def get(self, request):
        dati = request.session.get('dati_richiesta')
        hotel_ids_str = request.session.get('hotel_ids_pending', [])
        if not dati or not hotel_ids_str:
            messages.error(request, "Sessione scaduta.")
            return redirect('bidding:crea_richiesta')
        from datetime import date
        from decimal import Decimal
        hotel_ids = [int(pk) for pk in hotel_ids_str]
        with transaction.atomic():
            r = Richiesta.objects.create(
                cliente=request.user.cliente_profile,
                data_checkin=date.fromisoformat(dati['data_checkin']),
                data_checkout=date.fromisoformat(dati['data_checkout']),
                capienza_richiesta=int(dati['capienza_richiesta']),
                budget_massimo=Decimal(dati['budget_massimo']) if dati.get('budget_massimo') else None,
                citta_cercata=dati.get('citta') or None,
                stelle_minime=int(dati['stelle_minime']) if dati.get('stelle_minime') else None,
                messaggio_cliente=dati.get('messaggio_cliente') or '',
            )
            r.hotels_contattati.set(hotel_ids)
            if dati.get('servizi_ids'):
                r.servizi_richiesti.set([int(sid) for sid in dati['servizi_ids']])
        request.session.pop('dati_richiesta', None)
        request.session.pop('hotel_ids_pending', None)
        messages.success(request, "Richiesta inviata con successo!")
        return redirect('bidding:dashboard_cliente')


# ===========================================================================
# Dashboard Gestore
# ===========================================================================
class DashboardGestoreView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'bidding/dashboard_gestore.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        gestore = self.request.user.gestore_profile
        hotel_ids = gestore.hotels.values_list('id', flat=True)
        show_archive = self.request.GET.get('archivio') == '1'

        from datetime import timedelta as td
        # Richieste dove almeno un hotel del gestore contattato NON ha ancora risposto
        hotel_non_risposto = Hotel.objects.filter(
            gestore=gestore,
            richieste_ricevute=OuterRef('pk'),
        ).exclude(
            preventivi_inviati__richiesta=OuterRef('pk'),
        )
        richieste_qs = Richiesta.objects.filter(
            hotels_contattati__in=hotel_ids,
        ).filter(
            Exists(hotel_non_risposto)
        ).distinct().select_related('cliente__user').prefetch_related(
            'servizi_richiesti', 'hotels_contattati__gestore__user'
        ).order_by('-data_creazione')
        if not show_archive:
            richieste = [r for r in richieste_qs if not r.is_scaduta and not r.is_passata]
        else:
            richieste = list(richieste_qs)
        for r in richieste:
            r.scadenza_richiesta = r.data_creazione + td(minutes=r.durata_richiesta)

        # Preventivi inviati dal gestore
        preventivi_qs = Preventivo.objects.filter(hotel__gestore=gestore).select_related('richiesta__cliente__user', 'hotel', 'camera_assegnata').order_by('-timestamp_creazione')

        # Controllo proattivo: marca scaduti i preventivi ATTESA che hanno superato la validità
        for prev in preventivi_qs:
            if prev.stato == Preventivo.Stato.ATTESA and prev.is_scaduto:
                prev.stato = Preventivo.Stato.SCADUTO
                prev.save(update_fields=['stato'])

        if not show_archive:
            preventivi = [p for p in preventivi_qs if p.stato not in [Preventivo.Stato.RIFIUTATO, Preventivo.Stato.SCADUTO, Preventivo.Stato.INVALIDATO] and not p.richiesta.is_passata]
        else:
            preventivi = list(preventivi_qs)

        ctx['gestore'] = self.request.user.gestore_profile
        ctx['richieste'] = richieste
        ctx['preventivi'] = preventivi
        ctx['archivio'] = show_archive
        return ctx


# ===========================================================================
# Dashboard Cliente
# ===========================================================================
class DashboardClienteView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'bidding/dashboard_cliente.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def _is_richiesta_attiva(self, richiesta):
        """Una richiesta è attiva se ha almeno un preventivo valido
        o se la finestra per ricevere risposte non è ancora scaduta."""
        if richiesta.is_passata:
            return False
        # Se la finestra della richiesta non è scaduta, è ancora attiva
        if not richiesta.is_scaduta:
            return True
        # Finestra scaduta: attiva solo se c'è almeno un preventivo valido
        for prev in richiesta.preventivi.all():
            if prev.stato == Preventivo.Stato.ATTESA and not prev.is_scaduto:
                return True
            if prev.stato in [Preventivo.Stato.IN_PAGAMENTO, Preventivo.Stato.ACCETTATO]:
                return True
        return False

    def get_context_data(self, **kwargs):
        from datetime import timedelta
        from django.conf import settings
        import calendar

        ctx = super().get_context_data(**kwargs)
        cliente = self.request.user.cliente_profile
        now = timezone.now()
        show_archive = self.request.GET.get('archivio') == '1'

        richieste_qs = Richiesta.objects.filter(cliente=cliente).prefetch_related('preventivi__hotel', 'preventivi__camera_assegnata').order_by('-data_creazione')
        if not show_archive:
            richieste = [r for r in richieste_qs if self._is_richiesta_attiva(r)]
        else:
            richieste = richieste_qs

        from datetime import timedelta as td
        for richiesta in richieste:
            richiesta.scadenza_richiesta = richiesta.data_creazione + td(minutes=richiesta.durata_richiesta)
            for prev in richiesta.preventivi.all():
                if prev.stato == Preventivo.Stato.ATTESA:
                    # Controllo proattivo: segna scaduto se necessario
                    if prev.is_scaduto:
                        prev.stato = Preventivo.Stato.SCADUTO
                        prev.save(update_fields=['stato'])
                        continue
                    # Controllo proattivo: esclude solo camere ACCETTATO (IN_PAGAMENTO è temporaneo)
                    if not _check_pool_disponibile(
                        prev.hotel,
                        prev.richiesta.data_checkin,
                        prev.richiesta.data_checkout,
                        prev.richiesta.capienza_richiesta,
                    ):
                        prev.stato = Preventivo.Stato.INVALIDATO
                        prev.save(update_fields=['stato'])
                    else:
                        scadenza = prev.timestamp_creazione + timedelta(minutes=prev.durata_validita)
                        prev.scadenza_ts = calendar.timegm(scadenza.timetuple())
                elif prev.stato == Preventivo.Stato.IN_PAGAMENTO and prev.timestamp_accettazione:
                    scadenza = prev.timestamp_accettazione + timedelta(minutes=settings.DURATA_PAGAMENTO_MINUTI)
                    prev.scadenza_ts = calendar.timegm(scadenza.timetuple())
                else:
                    prev.scadenza_ts = None

        ctx['richieste'] = richieste
        ctx['archivio'] = show_archive
        return ctx


# ===========================================================================
# CreaPreventivoView — GESTORE invia un preventivo
# ===========================================================================
class CreaPreventivoView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'bidding/crea_preventivo.html'
    form_class = CreaPreventivoForm

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        richiesta_pk = self.kwargs.get('richiesta_pk')
        richiesta = get_object_or_404(Richiesta, pk=richiesta_pk)
        kwargs['gestore_profile'] = self.request.user.gestore_profile
        kwargs['richiesta'] = richiesta
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        richiesta = get_object_or_404(Richiesta, pk=self.kwargs.get('richiesta_pk'))
        ctx['richiesta'] = richiesta

        # Prezzi suggeriti: per ogni hotel, la camera più economica che rispetta la capienza
        from django.db.models import Min
        prezzi_suggeriti = {}
        for hotel in ctx['form'].fields['hotel'].queryset:
            camera = (
                hotel.camere
                .filter(capienza__gte=richiesta.capienza_richiesta, prezzo_indicativo__isnull=False)
                .order_by('prezzo_indicativo')
                .first()
            )
            if camera:
                prezzi_suggeriti[str(hotel.pk)] = str(camera.prezzo_indicativo)

        ctx['prezzi_suggeriti'] = prezzi_suggeriti
        return ctx

    def form_valid(self, form):
        richiesta = get_object_or_404(Richiesta, pk=self.kwargs.get('richiesta_pk'))
        hotel = form.cleaned_data['hotel']
        if hotel.id not in richiesta.hotels_contattati.values_list('id', flat=True):
            messages.error(self.request, "Hotel non valido per questa richiesta.")
            return redirect('bidding:dashboard_gestore')
        if richiesta.is_scaduta:
            messages.error(self.request, "La richiesta è scaduta, non puoi più inviare preventivi.")
            return redirect('bidding:dashboard_gestore')
        # Impedisci doppio preventivo stessa coppia hotel-richiesta
        if Preventivo.objects.filter(richiesta=richiesta, hotel=hotel).exists():
            messages.error(self.request, "Hai già inviato un preventivo per questa richiesta con questo hotel.")
            return redirect('bidding:dashboard_gestore')
        Preventivo.objects.create(
            richiesta=richiesta, hotel=hotel,
            stato=Preventivo.Stato.ATTESA,
            prezzo_proposto=form.cleaned_data['prezzo_proposto'],
            durata_validita=form.cleaned_data['durata_validita'],
            messaggio_gestore=form.cleaned_data.get('messaggio_gestore') or '',
        )
        messages.success(self.request, "Preventivo inviato con successo!")
        return redirect('bidding:dashboard_gestore')


# ===========================================================================
# ScartaRichiestaView — GESTORE scarta una richiesta
# ===========================================================================
class ScartaRichiestaView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def post(self, request, richiesta_pk):
        richiesta = get_object_or_404(Richiesta, pk=richiesta_pk)
        gestore = request.user.gestore_profile
        hotel_ids = gestore.hotels.values_list('id', flat=True)
        if not richiesta.hotels_contattati.filter(id__in=hotel_ids).exists():
            return HttpResponseForbidden("Non sei stato contattato per questa richiesta.")
        # Crea un Preventivo RIFIUTATO per tutti gli hotel del gestore contattati
        for hotel_id in richiesta.hotels_contattati.filter(id__in=hotel_ids).values_list('id', flat=True):
            if not Preventivo.objects.filter(richiesta=richiesta, hotel_id=hotel_id).exists():
                Preventivo.objects.create(richiesta=richiesta, hotel_id=hotel_id, stato=Preventivo.Stato.RIFIUTATO, prezzo_proposto=0)
        messages.info(request, "Richiesta scartata.")
        return redirect('bidding:dashboard_gestore')


# ===========================================================================
# FASE 4 — AccettaPreventivoView
# ===========================================================================
class AccettaPreventivoView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def post(self, request, pk):
        preventivo = get_object_or_404(Preventivo.objects.select_related('richiesta', 'richiesta__cliente__user', 'hotel'), pk=pk)
        if preventivo.richiesta.cliente.user != request.user:
            return HttpResponseForbidden("Non sei il proprietario.")
        if preventivo.stato != Preventivo.Stato.ATTESA:
            messages.error(request, f"Stato non valido: {preventivo.get_stato_display()}.")
            return redirect('bidding:dashboard_cliente')
        if preventivo.is_scaduto:
            with transaction.atomic():
                p = Preventivo.objects.select_for_update().get(pk=preventivo.pk)
                if p.stato == Preventivo.Stato.ATTESA:
                    p.stato = Preventivo.Stato.SCADUTO
                    p.save(update_fields=['stato'])
            messages.error(request, "Questo preventivo è scaduto.")
            return redirect('bidding:dashboard_cliente')
        with transaction.atomic():
            target = Preventivo.objects.select_for_update().get(pk=preventivo.pk)
            if target.stato != Preventivo.Stato.ATTESA:
                messages.error(request, f"Stato non valido.")
                return redirect('bidding:dashboard_cliente')
            pool = _get_camere_libere_pool(target.hotel, target.richiesta.data_checkin, target.richiesta.data_checkout, target.richiesta.capienza_richiesta)
            camera_scelta = pool.first()
            if camera_scelta is None:
                # Distingue tra camera persa (ACCETTATO) e bloccata temporaneamente (IN_PAGAMENTO)
                if _check_pool_disponibile(target.hotel, target.richiesta.data_checkin, target.richiesta.data_checkout, target.richiesta.capienza_richiesta):
                    messages.warning(request, "Camera momentaneamente prenotata da un altro utente. Riprova tra qualche minuto.")
                    return redirect('bidding:dashboard_cliente')
                target.stato = Preventivo.Stato.INVALIDATO
                target.save(update_fields=['stato'])
                messages.error(request, "Nessuna camera disponibile. Preventivo invalidato.")
                return redirect('bidding:dashboard_cliente')
            target.camera_assegnata = camera_scelta
            target.stato = Preventivo.Stato.IN_PAGAMENTO
            target.timestamp_accettazione = timezone.now()
            target.save(update_fields=['stato', 'camera_assegnata', 'timestamp_accettazione'])
        messages.success(request, "Preventivo accettato!")
        return redirect('bidding:conferma_pagamento', pk=target.pk)


# ===========================================================================
# AnnullaAccettazioneView, ConfermaPagamentoSimulatoView, RifiutaPreventivoView, RifiutaAltri
# ===========================================================================
class AnnullaAccettazioneView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def post(self, request, pk):
        prev = get_object_or_404(Preventivo.objects.select_related('richiesta__cliente__user'), pk=pk)
        if prev.richiesta.cliente.user != request.user:
            return HttpResponseForbidden()
        with transaction.atomic():
            t = Preventivo.objects.select_for_update().get(pk=prev.pk)
            if t.stato != Preventivo.Stato.IN_PAGAMENTO:
                messages.error(request, f"Stato non valido.")
                return redirect('bidding:dashboard_cliente')
            t.camera_assegnata = None
            t.stato = Preventivo.Stato.ATTESA
            t.timestamp_accettazione = None
            t.save(update_fields=['stato', 'camera_assegnata', 'timestamp_accettazione'])
        messages.info(request, "Accettazione annullata.")
        return redirect('bidding:dashboard_cliente')


class ConfermaPagamentoSimulatoView(LoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'bidding/conferma_pagamento.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def _get(self, pk):
        return get_object_or_404(Preventivo.objects.select_related('richiesta', 'richiesta__cliente__user', 'hotel', 'camera_assegnata'), pk=pk)

    def get(self, request, pk):
        prev = self._get(pk)
        if prev.richiesta.cliente.user != request.user:
            return HttpResponseForbidden()
        if prev.stato != Preventivo.Stato.IN_PAGAMENTO or prev.is_scaduto:
            messages.warning(request, "Pagamento non disponibile.")
            return redirect('bidding:dashboard_cliente')
        return render(request, self.template_name, {'preventivo': prev})

    def post(self, request, pk):
        prev = self._get(pk)
        if prev.richiesta.cliente.user != request.user:
            return HttpResponseForbidden()
        if prev.stato == Preventivo.Stato.ACCETTATO:
            messages.info(request, "Pagamento già confermato.")
            return redirect('bidding:dashboard_cliente')
        with transaction.atomic():
            t = Preventivo.objects.select_for_update().get(pk=prev.pk)
            if t.stato == Preventivo.Stato.ACCETTATO:
                messages.info(request, "Pagamento già confermato.")
                return redirect('bidding:dashboard_cliente')
            if t.stato != Preventivo.Stato.IN_PAGAMENTO or t.is_scaduto:
                messages.warning(request, "Stato non valido.")
                return redirect('bidding:dashboard_cliente')
            t.riferimento_pagamento = f"PAY-{uuid.uuid4().hex[:12].upper()}"
            t.stato = Preventivo.Stato.ACCETTATO
            t.timestamp_pagamento = timezone.now()
            t.save(update_fields=['riferimento_pagamento', 'stato', 'timestamp_pagamento'])
        messages.success(request, f"Pagamento confermato! {t.riferimento_pagamento}")
        return redirect('bidding:dashboard_cliente')


class RifiutaPreventivoView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def post(self, request, pk):
        prev = get_object_or_404(Preventivo.objects.select_related('richiesta__cliente__user'), pk=pk)
        if prev.richiesta.cliente.user != request.user:
            return HttpResponseForbidden()
        if prev.stato != Preventivo.Stato.ATTESA:
            messages.error(request, "Non rifiutabile.")
            return redirect('bidding:dashboard_cliente')
        prev.stato = Preventivo.Stato.RIFIUTATO
        prev.save(update_fields=['stato'])
        messages.info(request, "Preventivo rifiutato.")
        return redirect('bidding:dashboard_cliente')


class RifiutaAltriPreventiviRichiestaView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    def get(self, request, richiesta_pk):
        richiesta = get_object_or_404(Richiesta.objects.prefetch_related('preventivi__hotel'), pk=richiesta_pk, cliente__user=request.user)
        if not richiesta.preventivi.filter(stato=Preventivo.Stato.ACCETTATO).exists():
            messages.warning(request, "Nessun pagamento confermato.")
            return redirect('bidding:dashboard_cliente')
        altri = richiesta.preventivi.filter(stato=Preventivo.Stato.ATTESA)
        return render(request, 'bidding/rifiuta_altri.html', {'richiesta': richiesta, 'altri': altri})

    def post(self, request, richiesta_pk):
        richiesta = get_object_or_404(Richiesta.objects.prefetch_related('preventivi__hotel'), pk=richiesta_pk, cliente__user=request.user)
        if 'conferma' not in request.POST:
            messages.info(request, "Nessuna modifica.")
            return redirect('bidding:dashboard_cliente')
        aggiornati = richiesta.preventivi.filter(stato=Preventivo.Stato.ATTESA).update(stato=Preventivo.Stato.RIFIUTATO)
        messages.success(request, f"{aggiornati} preventivo/i rifiutato/i.")
        return redirect('bidding:dashboard_cliente')