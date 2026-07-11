from django.views.generic import ListView, DetailView, CreateView, UpdateView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from .models import Hotel, Camera
from .forms import HotelForm, CameraForm, ServiziHotelForm


class ListaHotelView(ListView):
    model = Hotel
    template_name = 'hotels/lista_hotel.html'
    context_object_name = 'hotels'
    ordering = ['citta', 'nome']


class DettaglioHotelView(DetailView):
    model = Hotel
    template_name = 'hotels/dettaglio_hotel.html'
    context_object_name = 'hotel'
    queryset = Hotel.objects.select_related('gestore__user').prefetch_related('camere')


# ===========================================================================
# Gestione hotel per il gestore
# ===========================================================================

class GestisciMieiHotelView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'hotels/miei_hotel.html'
    context_object_name = 'hotels'

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def get_queryset(self):
        return Hotel.objects.filter(gestore=self.request.user.gestore_profile).prefetch_related('camere').order_by('citta', 'nome')


class CreaHotelView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Hotel
    form_class = HotelForm
    template_name = 'hotels/crea_hotel.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def form_valid(self, form):
        form.instance.gestore = self.request.user.gestore_profile
        response = super().form_valid(form)
        messages.success(self.request, f"Hotel '{form.instance.nome}' creato con successo! Ora aggiungi le camere.")
        return redirect('hotels:gestisci_camere', pk=form.instance.pk)

    def get_success_url(self):
        return reverse('hotels:gestisci_camere', kwargs={'pk': self.object.pk})


class ModificaHotelView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Hotel
    form_class = HotelForm
    template_name = 'hotels/modifica_hotel.html'

    def test_func(self):
        hotel = self.get_object()
        return self.request.user.tipo_utente == 'GESTORE' and hotel.gestore.user == self.request.user

    def get_success_url(self):
        messages.success(self.request, "Hotel aggiornato.")
        return reverse('hotels:miei_hotel')


class GestisciCamereHotelView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'hotels/gestisci_camere.html'
    context_object_name = 'camere'

    def test_func(self):
        hotel = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        return self.request.user.tipo_utente == 'GESTORE' and hotel.gestore.user == self.request.user

    def get_queryset(self):
        self.hotel = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        return self.hotel.camere.all()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hotel'] = self.hotel
        ctx['form'] = CameraForm()
        return ctx

    def post(self, request, *args, **kwargs):
        self.hotel = get_object_or_404(Hotel, pk=kwargs['pk'])
        form = CameraForm(request.POST, request.FILES)
        if form.is_valid():
            quantita = form.cleaned_data.get('quantita', 1) or 1
            for i in range(quantita):
                camera = form.save(commit=False)
                camera.hotel = self.hotel
                camera.pk = None  # forza INSERT invece di UPDATE
                if quantita > 1:
                    camera.nome = f"{form.cleaned_data['nome']} #{i+1}"
                if 'foto' not in request.FILES and i > 0:
                    camera.foto = None
                camera.save()
            if quantita == 1:
                messages.success(request, f"Camera '{form.cleaned_data['nome']}' aggiunta.")
            else:
                messages.success(request, f"{quantita} camere '{form.cleaned_data['nome']}' create.")
        return redirect('hotels:gestisci_camere', pk=self.hotel.pk)


class ModificaCameraView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Camera
    form_class = CameraForm
    template_name = 'hotels/modifica_camera.html'

    def test_func(self):
        camera = self.get_object()
        return self.request.user.tipo_utente == 'GESTORE' and camera.hotel.gestore.user == self.request.user

    def get_success_url(self):
        messages.success(self.request, "Camera aggiornata.")
        return reverse('hotels:gestisci_camere', kwargs={'pk': self.object.hotel.pk})


class EliminaCameraView(LoginRequiredMixin, UserPassesTestMixin, View):
    def test_func(self):
        camera = get_object_or_404(Camera, pk=self.kwargs['pk'])
        return self.request.user.tipo_utente == 'GESTORE' and camera.hotel.gestore.user == self.request.user

    def post(self, request, pk):
        camera = get_object_or_404(Camera, pk=pk)
        hotel_pk = camera.hotel.pk

        # Warning se ci sono preventivi attivi che usano questa camera
        from bidding.models import Preventivo
        preventivi_attivi = Preventivo.objects.filter(
            camera_assegnata=camera,
            stato__in=[Preventivo.Stato.IN_PAGAMENTO, Preventivo.Stato.ACCETTATO]
        )
        if preventivi_attivi.exists():
            messages.error(
                request,
                f"Attenzione: questa camera è assegnata a {preventivi_attivi.count()} "
                f"prenotazione/i attiva/e. Al momento non risulta possibile procedere con la cancellazione"
            )
        else:
            camera.delete()
            messages.info(request, "Camera eliminata.")
        return redirect('hotels:gestisci_camere', pk=hotel_pk)


class GestisciServiziHotelView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    template_name = 'hotels/gestisci_servizi.html'
    form_class = ServiziHotelForm

    def test_func(self):
        hotel = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        return self.request.user.tipo_utente == 'GESTORE' and hotel.gestore.user == self.request.user

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['hotel'] = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs

    def get_initial(self):
        hotel = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        return {'servizi': hotel.servizi.all()}

    def form_valid(self, form):
        hotel = get_object_or_404(Hotel, pk=self.kwargs['pk'])
        hotel.servizi.set(form.cleaned_data['servizi'])
        messages.success(self.request, "Servizi aggiornati.")
        return redirect('hotels:miei_hotel')