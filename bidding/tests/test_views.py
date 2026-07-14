import datetime
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from users.models import GestoreProfile, ClienteProfile
from hotels.models import Hotel, Camera, Servizio
from bidding.models import Richiesta, Preventivo

User = get_user_model()


class CreaRichiestaViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.url = reverse('bidding:crea_richiesta')

    def test_caso_normale_form_valido_salva_in_sessione(self):
        self.client.login(username='cliente', password='testpass123!')
        data = {'data_checkin': '2026-12-01', 'data_checkout': '2026-12-05', 'capienza_richiesta': 2, 'budget_massimo': '150.00', 'citta': 'Roma', 'stelle_minime': 3}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('bidding:seleziona_hotel'))
        sessione = self.client.session.get('dati_richiesta')
        self.assertIsNotNone(sessione)
        self.assertEqual(sessione['citta'], 'Roma')

    def test_caso_limite_data_checkout_minore_checkin(self):
        self.client.login(username='cliente', password='testpass123!')
        data = {'data_checkin': '2026-12-05', 'data_checkout': '2026-12-01', 'capienza_richiesta': 1}
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'deve essere successiva')

    def test_caso_limite_data_checkout_uguale_checkin(self):
        self.client.login(username='cliente', password='testpass123!')
        data = {'data_checkin': '2026-12-05', 'data_checkout': '2026-12-05', 'capienza_richiesta': 1}
        response = self.client.post(self.url, data)
        self.assertContains(response, 'deve essere successiva')

    def test_caso_limite_solo_date_obbligatorie_compilate(self):
        self.client.login(username='cliente', password='testpass123!')
        data = {'data_checkin': '2026-12-01', 'data_checkout': '2026-12-05', 'capienza_richiesta': 1}
        response = self.client.post(self.url, data)
        self.assertRedirects(response, reverse('bidding:seleziona_hotel'))

    def test_caso_limite_gestore_puo_vedere_ricerca(self):
        gestore = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        GestoreProfile.objects.create(user=gestore, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.client.login(username='gestore', password='testpass123!')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)


class SelezionaHotelViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel_roma = Hotel.objects.create(gestore=self.gestore_profile, nome='Grand Hotel Roma', citta='Roma', stelle=4)
        Camera.objects.create(hotel=self.hotel_roma, nome='Suite', capienza=2, prezzo_indicativo=120.00)
        Camera.objects.create(hotel=self.hotel_roma, nome='Standard', capienza=4, prezzo_indicativo=80.00)
        self.hotel_milano = Hotel.objects.create(gestore=self.gestore_profile, nome='Milano Inn', citta='Milano', stelle=3)
        Camera.objects.create(hotel=self.hotel_milano, nome='Doppia', capienza=2, prezzo_indicativo=100.00)
        self.hotel_napoli = Hotel.objects.create(gestore=self.gestore_profile, nome='Napoli Resort', citta='Napoli', stelle=5)
        Camera.objects.create(hotel=self.hotel_napoli, nome='Deluxe', capienza=2, prezzo_indicativo=200.00)
        self.wifi = Servizio.objects.create(nome='WiFi')
        self.piscina = Servizio.objects.create(nome='Piscina')
        self.hotel_roma.servizi.add(self.wifi, self.piscina)
        self.hotel_milano.servizi.add(self.wifi)
        self.hotel_napoli.servizi.add(self.wifi, self.piscina)
        self.url = reverse('bidding:seleziona_hotel')
        self.client.login(username='cliente', password='testpass123!')

    def _set_session(self, **overrides):
        defaults = {'data_checkin': '2026-12-01', 'data_checkout': '2026-12-05', 'capienza_richiesta': 2, 'budget_massimo': None, 'citta': '', 'stelle_minime': None, 'servizi_ids': [], 'messaggio_cliente': ''}
        defaults.update(overrides)
        sess = dict(defaults)
        if sess.get('budget_massimo') is not None:
            sess['budget_massimo'] = str(sess['budget_massimo'])
        session = self.client.session
        session['dati_richiesta'] = sess
        session.save()

    def test_caso_normale_mostra_tutti_gli_hotel_senza_filtri(self):
        self._set_session()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Grand Hotel Roma')

    def test_caso_normale_filtro_citta_icontains(self):
        self._set_session(citta='rom')
        response = self.client.get(self.url)
        self.assertContains(response, 'Grand Hotel Roma')
        self.assertNotContains(response, 'Milano Inn')

    def test_caso_normale_filtro_stelle_minime(self):
        self._set_session(stelle_minime=4)
        response = self.client.get(self.url)
        self.assertContains(response, 'Grand Hotel Roma')
        self.assertNotContains(response, 'Milano Inn')

    def test_caso_normale_filtro_budget_massimo(self):
        self._set_session(budget_massimo='90.00')
        response = self.client.get(self.url)
        self.assertContains(response, 'Grand Hotel Roma')
        self.assertNotContains(response, 'Milano Inn')

    def test_caso_normale_filtro_servizi_and(self):
        self._set_session(servizi_ids=[self.wifi.id, self.piscina.id])
        response = self.client.get(self.url)
        self.assertContains(response, 'Grand Hotel Roma')
        self.assertNotContains(response, 'Milano Inn')

    def test_caso_limite_sessione_vuota_redirect(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('bidding:crea_richiesta'))

    def test_caso_normale_crea_richiesta_solo_hotel_selezionati(self):
        self._set_session()
        response = self.client.post(self.url, {'hotels': [self.hotel_roma.pk, self.hotel_napoli.pk]})
        self.assertEqual(response.status_code, 302)
        richiesta = Richiesta.objects.first()
        self.assertEqual(richiesta.hotels_contattati.count(), 2)

    def test_caso_limite_turnover_corretto(self):
        altro = User.objects.create_user(username='altro', password='testpass123!', tipo_utente='CLIENTE')
        altro_p = ClienteProfile.objects.create(user=altro, telefono='000')
        r = Richiesta.objects.create(cliente=altro_p, data_checkin=datetime.date(2026, 11, 25), data_checkout=datetime.date(2026, 12, 1), capienza_richiesta=1)
        suite = Camera.objects.get(nome='Suite', hotel=self.hotel_roma)
        Preventivo.objects.create(richiesta=r, hotel=self.hotel_roma, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=100.00, camera_assegnata=suite)
        self._set_session()
        response = self.client.get(self.url)
        self.assertContains(response, 'Grand Hotel Roma')

    def test_caso_limite_tutte_camere_occupate(self):
        altro = User.objects.create_user(username='altro', password='testpass123!', tipo_utente='CLIENTE')
        altro_p = ClienteProfile.objects.create(user=altro, telefono='000')
        for cam in Camera.objects.filter(hotel=self.hotel_roma):
            r = Richiesta.objects.create(cliente=altro_p, data_checkin=datetime.date(2026, 11, 28), data_checkout=datetime.date(2026, 12, 3), capienza_richiesta=1)
            Preventivo.objects.create(richiesta=r, hotel=self.hotel_roma, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=90.00, camera_assegnata=cam)
        self._set_session()
        response = self.client.get(self.url)
        self.assertNotContains(response, 'Grand Hotel Roma')


class DashboardGestoreViewTests(TestCase):
    def setUp(self):
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Mio Hotel', citta='Roma', stelle=4)
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.url = reverse('bidding:dashboard_gestore')

    def test_caso_normale_mostra_richieste_dove_contattato(self):
        r = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        r.hotels_contattati.add(self.hotel)
        self.client.login(username='gestore', password='testpass123!')
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['richieste']), 1)

    def test_caso_limite_non_vede_richieste_gia_risposte(self):
        r = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        r.hotels_contattati.add(self.hotel)
        Preventivo.objects.create(richiesta=r, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00)
        self.client.login(username='gestore', password='testpass123!')
        response = self.client.get(self.url)
        # La richiesta non deve comparire nella sezione richieste
        self.assertEqual(len(response.context['richieste']), 0)
        # Il preventivo deve comparire nella sezione preventivi
        self.assertEqual(len(response.context['preventivi']), 1)


class DashboardClienteViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Test Hotel', citta='Roma', stelle=4)
        self.camera = Camera.objects.create(hotel=self.hotel, nome='Suite', capienza=2, prezzo_indicativo=100.00)
        self.url = reverse('bidding:dashboard_cliente')
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_mostra_richieste_del_cliente(self):
        Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        response = self.client.get(self.url)
        self.assertContains(response, '01/12/2026')

    def test_caso_limite_cliente_vuoto(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Non hai ancora inviato nessuna richiesta')


class AccettaPreventivoViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Test Hotel', citta='Roma', stelle=4)
        self.camera = Camera.objects.create(hotel=self.hotel, nome='Suite', capienza=2, prezzo_indicativo=100.00)
        self.richiesta = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        self.cliente_user2 = User.objects.create_user(username='cliente2', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile2 = ClienteProfile.objects.create(user=self.cliente_user2, telefono='000')
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_assegna_camera_e_sposta_in_pagamento(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00)
        url = reverse('bidding:accetta_preventivo', args=[prev.pk])
        response = self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.IN_PAGAMENTO)
        self.assertIsNotNone(prev.camera_assegnata)

    def test_caso_limite_invalida_se_pool_vuoto(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00)
        r2 = Richiesta.objects.create(cliente=self.cliente_profile2, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        Preventivo.objects.create(richiesta=r2, hotel=self.hotel, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=90.00, camera_assegnata=self.camera)
        url = reverse('bidding:accetta_preventivo', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.INVALIDATO)

    def test_caso_limite_turnover_non_blocca(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00)
        r2 = Richiesta.objects.create(cliente=self.cliente_profile2, data_checkin=datetime.date(2026, 11, 25), data_checkout=datetime.date(2026, 12, 1), capienza_richiesta=2)
        Preventivo.objects.create(richiesta=r2, hotel=self.hotel, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=90.00, camera_assegnata=self.camera)
        url = reverse('bidding:accetta_preventivo', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.IN_PAGAMENTO)

    def test_caso_limite_preventivo_scaduto_non_accettabile(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00, durata_validita=1)
        prev.timestamp_creazione = timezone.now() - datetime.timedelta(minutes=5)
        prev.save()
        url = reverse('bidding:accetta_preventivo', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.SCADUTO)

    def test_caso_limite_idor_cliente_altrui_forbidden(self):
        """Un cliente non può accettare il preventivo di un altro cliente (IDOR protection)."""
        prev = Preventivo.objects.create(
            richiesta=self.richiesta, hotel=self.hotel,
            stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00,
        )
        # Logga come cliente2 (un altro utente)
        self.client.login(username='cliente2', password='testpass123!')
        url = reverse('bidding:accetta_preventivo', args=[prev.pk])
        response = self.client.post(url)
        # Deve ricevere 403 Forbidden
        self.assertEqual(response.status_code, 403)
        # Il preventivo NON deve essere stato modificato
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.ATTESA)


class AnnullaAccettazioneViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Test Hotel', citta='Roma', stelle=4)
        self.camera = Camera.objects.create(hotel=self.hotel, nome='Suite', capienza=2, prezzo_indicativo=100.00)
        self.richiesta = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_libera_camera_e_torna_attesa(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.IN_PAGAMENTO, prezzo_proposto=100.00, camera_assegnata=self.camera, timestamp_accettazione=timezone.now())
        url = reverse('bidding:annulla_accettazione', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.ATTESA)
        self.assertIsNone(prev.camera_assegnata)


class ConfermaPagamentoSimulatoViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Test Hotel', citta='Roma', stelle=4)
        self.camera = Camera.objects.create(hotel=self.hotel, nome='Suite', capienza=2, prezzo_indicativo=100.00)
        self.richiesta = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_pagamento_confermato(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.IN_PAGAMENTO, prezzo_proposto=100.00, camera_assegnata=self.camera, timestamp_accettazione=timezone.now())
        url = reverse('bidding:conferma_pagamento', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.ACCETTATO)
        self.assertIsNotNone(prev.riferimento_pagamento)

    def test_caso_limite_idempotente_doppio_submit(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.IN_PAGAMENTO, prezzo_proposto=100.00, camera_assegnata=self.camera, timestamp_accettazione=timezone.now())
        url = reverse('bidding:conferma_pagamento', args=[prev.pk])
        self.client.post(url)
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.ACCETTATO)


class RifiutaPreventivoViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel = Hotel.objects.create(gestore=self.gestore_profile, nome='Test Hotel', citta='Roma', stelle=4)
        self.richiesta = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_rifiuto_singolo_preventivo(self):
        prev = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel, stato=Preventivo.Stato.ATTESA, prezzo_proposto=100.00)
        url = reverse('bidding:rifiuta_preventivo', args=[prev.pk])
        self.client.post(url)
        prev.refresh_from_db()
        self.assertEqual(prev.stato, Preventivo.Stato.RIFIUTATO)


class RifiutaAltriPreventiviRichiestaViewTests(TestCase):
    def setUp(self):
        self.cliente_user = User.objects.create_user(username='cliente', password='testpass123!', tipo_utente='CLIENTE')
        self.cliente_profile = ClienteProfile.objects.create(user=self.cliente_user, telefono='1234567890')
        self.gestore_user = User.objects.create_user(username='gestore', password='testpass123!', tipo_utente='GESTORE')
        self.gestore_profile = GestoreProfile.objects.create(user=self.gestore_user, partita_iva='12345678901', ragione_sociale='Hotel SRL')
        self.hotel1 = Hotel.objects.create(gestore=self.gestore_profile, nome='Hotel 1', citta='Roma', stelle=4)
        self.hotel2 = Hotel.objects.create(gestore=self.gestore_profile, nome='Hotel 2', citta='Roma', stelle=3)
        self.richiesta = Richiesta.objects.create(cliente=self.cliente_profile, data_checkin=datetime.date(2026, 12, 1), data_checkout=datetime.date(2026, 12, 5), capienza_richiesta=2)
        self.client.login(username='cliente', password='testpass123!')

    def test_caso_normale_rifiuta_altri_su_conferma(self):
        Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel1, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=100.00)
        prev_attesa = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel2, stato=Preventivo.Stato.ATTESA, prezzo_proposto=80.00)
        url = reverse('bidding:rifiuta_altri', args=[self.richiesta.pk])
        self.client.post(url, {'conferma': '1'})
        prev_attesa.refresh_from_db()
        self.assertEqual(prev_attesa.stato, Preventivo.Stato.RIFIUTATO)

    def test_caso_limite_senza_conferma_non_modifica(self):
        Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel1, stato=Preventivo.Stato.ACCETTATO, prezzo_proposto=100.00)
        prev_attesa = Preventivo.objects.create(richiesta=self.richiesta, hotel=self.hotel2, stato=Preventivo.Stato.ATTESA, prezzo_proposto=80.00)
        url = reverse('bidding:rifiuta_altri', args=[self.richiesta.pk])
        self.client.post(url)
        prev_attesa.refresh_from_db()
        self.assertEqual(prev_attesa.stato, Preventivo.Stato.ATTESA)