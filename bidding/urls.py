from django.urls import path
from . import views

app_name = 'bidding'

urlpatterns = [
    # Fase 3 – Flusso cliente (ricerca pubblica)
    path('richiesta/nuova/', views.CreaRichiestaView.as_view(), name='crea_richiesta'),
    path('richiesta/seleziona-hotel/', views.SelezionaHotelView.as_view(), name='seleziona_hotel'),
    path('richiesta/completa/', views.CompletaRichiestaDopoLoginView.as_view(), name='completa_richiesta'),

    # Dashboard
    path('dashboard/gestore/', views.DashboardGestoreView.as_view(), name='dashboard_gestore'),
    path('dashboard/cliente/', views.DashboardClienteView.as_view(), name='dashboard_cliente'),

    # Fase 4 – Bidding
    path('preventivo/crea/<int:richiesta_pk>/', views.CreaPreventivoView.as_view(), name='crea_preventivo'),
    path('richiesta/<int:richiesta_pk>/scarta/', views.ScartaRichiestaView.as_view(), name='scarta_richiesta'),
    path('preventivo/<int:pk>/accetta/', views.AccettaPreventivoView.as_view(), name='accetta_preventivo'),
    path('preventivo/<int:pk>/annulla-accettazione/', views.AnnullaAccettazioneView.as_view(), name='annulla_accettazione'),
    path('preventivo/<int:pk>/pagamento/', views.ConfermaPagamentoSimulatoView.as_view(), name='conferma_pagamento'),
    path('preventivo/<int:pk>/rifiuta/', views.RifiutaPreventivoView.as_view(), name='rifiuta_preventivo'),
    path('richiesta/<int:richiesta_pk>/rifiuta-altri/', views.RifiutaAltriPreventiviRichiestaView.as_view(), name='rifiuta_altri'),
]