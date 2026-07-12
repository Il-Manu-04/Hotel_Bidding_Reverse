from django.views.generic import CreateView, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy, reverse
from django.contrib.auth import login
from django.contrib import messages
from django.shortcuts import redirect
from .forms import RegistrazioneGestoreForm, RegistrazioneClienteForm, ModificaProfiloGestoreForm, ModificaProfiloClienteForm
from .models import CustomUser


class RegistraGestoreView(CreateView):
    template_name = 'users/registra_gestore.html'
    form_class = RegistrazioneGestoreForm

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        return redirect('home')


class DashboardGestoreView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'users/dashboard_gestore.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['gestore'] = self.request.user.gestore_profile
        return ctx


class RegistraClienteView(CreateView):
    template_name = 'users/registra_cliente.html'
    form_class = RegistrazioneClienteForm

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        # Se l'utente arriva dalla ricerca anonima, completa la richiesta
        if self.request.session.get('dati_richiesta') and self.request.session.get('hotel_ids_pending'):
            return redirect('bidding:completa_richiesta')
        return redirect('bidding:dashboard_cliente')


class ModificaProfiloClienteView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CustomUser
    form_class = ModificaProfiloClienteForm
    template_name = 'users/modifica_profilo_cliente.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'CLIENTE'

    #modifica solo se stesso evitando id arbitrari nell'url
    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['cliente_profile'] = self.request.user.cliente_profile
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Profilo aggiornato con successo.")
        return reverse('bidding:dashboard_cliente')


class ModificaProfiloGestoreView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = CustomUser
    form_class = ModificaProfiloGestoreForm
    template_name = 'users/modifica_profilo_gestore.html'

    def test_func(self):
        return self.request.user.tipo_utente == 'GESTORE'

    def get_object(self, queryset=None):
        return self.request.user

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['gestore_profile'] = self.request.user.gestore_profile
        return kwargs

    def get_success_url(self):
        messages.success(self.request, "Profilo aggiornato con successo.")
        return reverse('bidding:dashboard_gestore')
