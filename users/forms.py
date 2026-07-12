from django import forms
from django.db import transaction
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, GestoreProfile, ClienteProfile
from hotels.models import Hotel


class RegistrazioneGestoreForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Cognome')

    partita_iva = forms.CharField(
        max_length=11, min_length=11, required=True,
        label='Partita IVA',
        help_text='Inserisci 11 cifre numeriche.',
        widget=forms.TextInput(attrs={'placeholder': '12345678901'}),
    )
    ragione_sociale = forms.CharField(max_length=255, required=True, label='Ragione Sociale')

    crea_hotel = forms.BooleanField(
        required=False, initial=True,
        label='Registra anche una struttura'
    )

    nome_hotel = forms.CharField(max_length=255, required=False, label='Nome Hotel')
    citta_hotel = forms.CharField(max_length=255, required=False, label='Città')
    stelle_hotel = forms.ChoiceField(
        choices=[(i, f'{i} stelle') for i in range(1, 6)],
        required=False, label='Stelle',
    )
    foto_hotel = forms.ImageField(required=False, label='Foto Hotel')

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

    def clean_partita_iva(self):
        piva = self.cleaned_data.get('partita_iva')
        if not piva.isdigit() or len(piva) != 11:
            raise forms.ValidationError('La partita IVA deve contenere esattamente 11 cifre.')
        if GestoreProfile.objects.filter(partita_iva=piva).exists():
            raise forms.ValidationError('Questa partita IVA è già registrata.')
        return piva

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('crea_hotel'):
            if not cleaned.get('nome_hotel'):
                self.add_error('nome_hotel', 'Il nome dell\'hotel è obbligatorio se crei una struttura.')
            if not cleaned.get('citta_hotel'):
                self.add_error('citta_hotel', 'La città è obbligatoria se crei una struttura.')
            if not cleaned.get('stelle_hotel'):
                self.add_error('stelle_hotel', 'Le stelle sono obbligatorie se crei una struttura.')
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.tipo_utente = 'GESTORE'
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            with transaction.atomic():
                user.save()
                GestoreProfile.objects.create(
                    user=user,
                    partita_iva=self.cleaned_data['partita_iva'],
                    ragione_sociale=self.cleaned_data['ragione_sociale'],
                )
                if self.cleaned_data.get('crea_hotel'):
                    Hotel.objects.create(
                        gestore=user.gestore_profile,
                        nome=self.cleaned_data['nome_hotel'],
                        citta=self.cleaned_data['citta_hotel'],
                        stelle=int(self.cleaned_data['stelle_hotel']),
                        foto=self.cleaned_data.get('foto_hotel'),
                    )
        return user


class RegistrazioneClienteForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Cognome')
    telefono = forms.CharField(max_length=20, required=True, label='Telefono')

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.tipo_utente = 'CLIENTE'
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            ClienteProfile.objects.create(
                user=user,
                telefono=self.cleaned_data['telefono'],
            )
        return user


# ===========================================================================
# Form modifica profilo
# ===========================================================================

class ModificaProfiloGestoreForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Cognome')
    email = forms.EmailField(required=True)
    partita_iva = forms.CharField(max_length=11, min_length=11, required=True, label='Partita IVA')
    ragione_sociale = forms.CharField(max_length=255, required=True, label='Ragione Sociale')

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        self.gestore_profile = kwargs.pop('gestore_profile', None)
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'gestore_profile'):
            self.fields['partita_iva'].initial = self.instance.gestore_profile.partita_iva
            self.fields['ragione_sociale'].initial = self.instance.gestore_profile.ragione_sociale

    def clean_partita_iva(self):
        piva = self.cleaned_data.get('partita_iva')
        if not piva.isdigit() or len(piva) != 11:
            raise forms.ValidationError('La partita IVA deve contenere esattamente 11 cifre.')
        #gestisce la modifica escludendo se stesso dall'eccezione
        if GestoreProfile.objects.filter(partita_iva=piva).exclude(user=self.instance).exists():
            raise forms.ValidationError('Questa partita IVA è già registrata.')
        return piva

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            gestore = user.gestore_profile
            gestore.partita_iva = self.cleaned_data['partita_iva']
            gestore.ragione_sociale = self.cleaned_data['ragione_sociale']
            gestore.save()
        return user


class ModificaProfiloClienteForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True, label='Nome')
    last_name = forms.CharField(max_length=150, required=True, label='Cognome')
    email = forms.EmailField(required=True)
    telefono = forms.CharField(max_length=20, required=True, label='Telefono')

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        self.cliente_profile = kwargs.pop('cliente_profile', None)
        super().__init__(*args, **kwargs)
        if self.instance and hasattr(self.instance, 'cliente_profile'):
            self.fields['telefono'].initial = self.instance.cliente_profile.telefono

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            cliente = user.cliente_profile
            cliente.telefono = self.cleaned_data['telefono']
            cliente.save()
        return user
