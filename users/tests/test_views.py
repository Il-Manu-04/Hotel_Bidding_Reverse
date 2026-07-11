from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from users.models import CustomUser, GestoreProfile, ClienteProfile
from hotels.models import Hotel


class TestRegistrazioneViews(TestCase):

    def setUp(self):
        self.url_gestore = reverse('users:registra_gestore')
        self.url_cliente = reverse('users:registra_cliente')

    def test_registrazione_gestore_crea_user_profile_hotel(self):
        """Caso normale: registrazione gestore con checkbox crea User+GestoreProfile+Hotel."""
        data = {
            'username': 'gestore1',
            'email': 'gestore1@example.com',
            'first_name': 'Mario',
            'last_name': 'Rossi',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
            'partita_iva': '12345678901',
            'ragione_sociale': 'Hotel Rossi SRL',
            'crea_hotel': 'on',
            'nome_hotel': 'Grand Hotel',
            'citta_hotel': 'Roma',
            'stelle_hotel': '4',
        }
        response = self.client.post(self.url_gestore, data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='gestore1')
        self.assertEqual(user.tipo_utente, 'GESTORE')
        self.assertEqual(user.email, 'gestore1@example.com')

        profile = user.gestore_profile
        self.assertEqual(profile.partita_iva, '12345678901')
        self.assertEqual(profile.ragione_sociale, 'Hotel Rossi SRL')

        hotel = Hotel.objects.get(gestore=profile)
        self.assertEqual(hotel.nome, 'Grand Hotel')
        self.assertEqual(hotel.citta, 'Roma')
        self.assertEqual(hotel.stelle, 4)

    def test_registrazione_cliente_crea_user_profile(self):
        """Caso normale: registrazione cliente crea User+ClienteProfile."""
        data = {
            'username': 'cliente1',
            'email': 'cliente1@example.com',
            'first_name': 'Anna',
            'last_name': 'Bianchi',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
            'telefono': '+39 333 1234567',
        }
        response = self.client.post(self.url_cliente, data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='cliente1')
        self.assertEqual(user.tipo_utente, 'CLIENTE')

        profile = user.cliente_profile
        self.assertEqual(profile.telefono, '+39 333 1234567')

        # Il cliente NON deve avere un GestoreProfile
        with self.assertRaises(GestoreProfile.DoesNotExist):
            _ = user.gestore_profile

    def test_registrazione_gestore_dati_hotel_invalidi_rollback(self):
        """Caso limite: errore nella creazione Hotel → rollback completo, nessun record orfano."""
        data = {
            'username': 'gestore_fail',
            'email': 'fail@example.com',
            'first_name': 'Test',
            'last_name': 'Fail',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
            'partita_iva': '12345678902',
            'ragione_sociale': 'Hotel Fail SRL',
            'crea_hotel': 'on',
            'nome_hotel': 'Bad Hotel',
            'citta_hotel': 'Milano',
            'stelle_hotel': '4',
        }

        with patch(
            'users.forms.Hotel.objects.create',
            side_effect=ValueError('Errore simulato creazione Hotel'),
        ):
            try:
                self.client.post(self.url_gestore, data)
            except ValueError:
                pass

        # Verifica che nessun record sia stato creato (rollback completo)
        self.assertFalse(CustomUser.objects.filter(username='gestore_fail').exists())
        self.assertFalse(GestoreProfile.objects.filter(partita_iva='12345678902').exists())
        self.assertFalse(Hotel.objects.filter(nome='Bad Hotel').exists())

    def test_cliente_non_riceve_gestore_profile(self):
        """Caso limite: la registrazione cliente non crea accidentalmente un GestoreProfile."""
        data = {
            'username': 'cliente2',
            'email': 'cliente2@example.com',
            'first_name': 'Luca',
            'last_name': 'Verdi',
            'password1': 'testpass123!',
            'password2': 'testpass123!',
            'telefono': '111',
        }
        response = self.client.post(self.url_cliente, data)
        self.assertEqual(response.status_code, 302)

        user = CustomUser.objects.get(username='cliente2')
        self.assertTrue(hasattr(user, 'cliente_profile'))
        self.assertIsNotNone(user.cliente_profile)

        with self.assertRaises(GestoreProfile.DoesNotExist):
            _ = user.gestore_profile

        self.assertFalse(GestoreProfile.objects.filter(user=user).exists())