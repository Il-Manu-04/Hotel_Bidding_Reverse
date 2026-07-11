"""
Management command per popolare il database con dati di test.
Uso: pipenv run python manage.py crea_dati_test
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import CustomUser, GestoreProfile, ClienteProfile
from hotels.models import Hotel, Camera, Servizio


class Command(BaseCommand):
    help = 'Popola il DB con dati di test (hotel, camere, servizi, utenti).'

    def handle(self, *args, **options):
        # ---------------------------------------------------------------
        # 1) Servizi
        # ---------------------------------------------------------------
        servizi_data = [
            ('WiFi', 'fa-wifi'),
            ('Piscina', 'fa-swimming-pool'),
            ('Parcheggio', 'fa-parking'),
            ('Aria Condizionata', 'fa-snowflake'),
            ('Colazione inclusa', 'fa-coffee'),
            ('Palestra', 'fa-dumbbell'),
        ]
        servizi = {}
        for nome, icona in servizi_data:
            s, created = Servizio.objects.get_or_create(nome=nome, defaults={'icona': icona})
            servizi[nome] = s
            if created:
                self.stdout.write(f"  Servizio creato: {nome}")

        # ---------------------------------------------------------------
        # 2) Utenti
        # ---------------------------------------------------------------
        gestore_user, _ = CustomUser.objects.get_or_create(
            username='gestore1',
            defaults={
                'tipo_utente': 'GESTORE',
                'email': 'gestore@example.com',
            },
        )
        gestore_user.set_password('testpass123!')
        gestore_user.save()

        gestore_profile, _ = GestoreProfile.objects.get_or_create(
            user=gestore_user,
            defaults={
                'partita_iva': '12345678901',
                'ragione_sociale': 'Hotel Group Italia SRL',
            },
        )
        self.stdout.write(f"  Gestore: gestore1 / testpass123!")

        cliente_user, _ = CustomUser.objects.get_or_create(
            username='cliente1',
            defaults={
                'tipo_utente': 'CLIENTE',
                'email': 'cliente@example.com',
            },
        )
        cliente_user.set_password('testpass123!')
        cliente_user.save()

        ClienteProfile.objects.get_or_create(
            user=cliente_user,
            defaults={'telefono': '3331234567'},
        )
        self.stdout.write(f"  Cliente: cliente1 / testpass123!")

        # ---------------------------------------------------------------
        # 3) Hotel e camere
        # ---------------------------------------------------------------
        hotels_config = [
            {
                'nome': 'Grand Hotel Roma',
                'citta': 'Roma',
                'stelle': 4,
                'descrizione': 'Elegante hotel nel centro di Roma, a due passi dalla Fontana di Trevi.',
                'servizi': ['WiFi', 'Piscina', 'Parcheggio'],
                'camere': [
                    ('Suite', 2, 120.00),
                    ('Deluxe', 4, 150.00),
                    ('Standard', 2, 80.00),
                ],
            },
            {
                'nome': 'Milano Inn',
                'citta': 'Milano',
                'stelle': 3,
                'descrizione': 'Accogliente struttura in zona Navigli, ideale per viaggi d\'affari.',
                'servizi': ['WiFi', 'Colazione inclusa'],
                'camere': [
                    ('Doppia', 2, 90.00),
                    ('Singola', 1, 60.00),
                ],
            },
            {
                'nome': 'Napoli Resort',
                'citta': 'Napoli',
                'stelle': 5,
                'descrizione': 'Resort di lusso con vista sul Golfo di Napoli e spa privata.',
                'servizi': ['WiFi', 'Piscina', 'Aria Condizionata', 'Palestra'],
                'camere': [
                    ('Presidenziale', 2, 250.00),
                    ('Junior Suite', 2, 180.00),
                ],
            },
            {
                'nome': 'Firenze B&B',
                'citta': 'Firenze',
                'stelle': 2,
                'descrizione': 'Piccolo B&B nel cuore di Firenze, a 5 minuti dal Duomo.',
                'servizi': ['WiFi'],
                'camere': [
                    ('Matrimoniale', 2, 70.00),
                    ('Singola', 1, 50.00),
                ],
            },
        ]

        for cfg in hotels_config:
            hotel, created = Hotel.objects.get_or_create(
                nome=cfg['nome'],
                defaults={
                    'gestore': gestore_profile,
                    'citta': cfg['citta'],
                    'stelle': cfg['stelle'],
                    'descrizione': cfg['descrizione'],
                },
            )
            if created:
                # Servizi
                for nome_servizio in cfg['servizi']:
                    hotel.servizi.add(servizi[nome_servizio])

                # Camere
                for nome_camera, capienza, prezzo in cfg['camere']:
                    Camera.objects.create(
                        hotel=hotel,
                        nome=nome_camera,
                        capienza=capienza,
                        prezzo_indicativo=prezzo,
                    )

                self.stdout.write(f"  Hotel creato: {hotel.nome} ({hotel.citta}, {hotel.stelle}★)")
            else:
                self.stdout.write(f"  Hotel già esistente: {hotel.nome}")

        self.stdout.write(self.style.SUCCESS('\n✅ Dati di test creati con successo!'))
        self.stdout.write('\nCredenziali:')
        self.stdout.write('  Gestore: gestore1 / testpass123!')
        self.stdout.write('  Cliente: cliente1 / testpass123!')
        self.stdout.write('\nAvvia il server con: pipenv run python manage.py runserver')