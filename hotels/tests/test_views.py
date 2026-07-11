from django.test import TestCase
from django.urls import reverse
from users.models import CustomUser, GestoreProfile
from hotels.models import Hotel, Camera


class TestHotelViews(TestCase):

    def setUp(self):
        self.url_lista = reverse('hotels:lista_hotel')

        self.gestore_user = CustomUser.objects.create_user(
            username='gestore_test',
            password='testpass123!',
            tipo_utente='GESTORE',
        )
        self.gestore_profile = GestoreProfile.objects.create(
            user=self.gestore_user,
            partita_iva='12345678901',
            ragione_sociale='Hotel Test SRL',
        )
        self.hotel = Hotel.objects.create(
            gestore=self.gestore_profile,
            nome='Hotel Belvedere',
            citta='Roma',
            stelle=4,
        )
        self.url_dettaglio = reverse('hotels:dettaglio_hotel', args=[self.hotel.pk])

    # --- ListaHotelView ---

    def test_lista_hotel_accesso_pubblico(self):
        """Utente anonimo può accedere alla lista hotel."""
        response = self.client.get(self.url_lista)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hotel Belvedere')

    def test_lista_hotel_accesso_autenticato(self):
        """Utente autenticato può accedere alla lista hotel."""
        self.client.login(username='gestore_test', password='testpass123!')
        response = self.client.get(self.url_lista)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hotel Belvedere')

    def test_lista_hotel_contiene_hotel_creato(self):
        """La lista contiene l'hotel creato nel setUp."""
        Hotel.objects.create(
            gestore=self.gestore_profile,
            nome='Second Hotel',
            citta='Milano',
            stelle=3,
        )
        response = self.client.get(self.url_lista)
        self.assertContains(response, 'Hotel Belvedere')
        self.assertContains(response, 'Second Hotel')
        self.assertEqual(len(response.context['hotels']), 2)

    def test_lista_hotel_vuota(self):
        """Lista hotel senza hotel mostra messaggio."""
        Hotel.objects.all().delete()
        response = self.client.get(self.url_lista)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nessun hotel disponibile')

    # --- DettaglioHotelView ---

    def test_dettaglio_hotel_accesso_pubblico(self):
        """Utente anonimo può vedere il dettaglio di un hotel."""
        response = self.client.get(self.url_dettaglio)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hotel Belvedere')
        self.assertContains(response, 'Roma')
        self.assertContains(response, 'Hotel Test SRL')

    def test_dettaglio_hotel_mostra_camere(self):
        """Il dettaglio hotel mostra le camere associate."""
        Camera.objects.create(
            hotel=self.hotel,
            nome='Suite',
            capienza=2,
            prezzo_indicativo=150.00,
        )
        Camera.objects.create(
            hotel=self.hotel,
            nome='Standard',
            capienza=4,
            prezzo_indicativo=80.00,
        )
        response = self.client.get(self.url_dettaglio)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Suite')
        self.assertContains(response, 'Standard')
        self.assertContains(response, '150.00')
        self.assertContains(response, '80.00')

    def test_dettaglio_hotel_nessuna_camera(self):
        """Dettaglio hotel senza camere mostra messaggio appropriato."""
        response = self.client.get(self.url_dettaglio)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nessuna camera disponibile')

    def test_dettaglio_hotel_inesistente(self):
        """Richiedere un hotel inesistente restituisce 404."""
        url_inesistente = reverse('hotels:dettaglio_hotel', args=[99999])
        response = self.client.get(url_inesistente)
        self.assertEqual(response.status_code, 404)