from django import forms
from .models import Preventivo
from hotels.models import Hotel, Servizio


# ===========================================================================
# Form per la creazione della richiesta
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
# Form per la creazione del preventivo
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
