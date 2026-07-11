from django import forms
from .models import Hotel, Camera, Servizio


class HotelForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = ['nome', 'citta', 'stelle', 'descrizione', 'foto']


class CameraForm(forms.ModelForm):
    quantita = forms.IntegerField(min_value=1, initial=1, required=False, label='Quante camere di questo tipo?')

    class Meta:
        model = Camera
        fields = ['nome', 'capienza', 'prezzo_indicativo', 'foto']


class ServiziHotelForm(forms.Form):
    servizi = forms.ModelMultipleChoiceField(
        queryset=Servizio.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Servizi offerti',
    )