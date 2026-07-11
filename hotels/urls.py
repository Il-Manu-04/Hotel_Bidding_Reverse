from django.urls import path
from . import views

app_name = 'hotels'

urlpatterns = [
    path('', views.ListaHotelView.as_view(), name='lista_hotel'),
    path('<int:pk>/', views.DettaglioHotelView.as_view(), name='dettaglio_hotel'),

    # Gestione hotel (gestore)
    path('miei/', views.GestisciMieiHotelView.as_view(), name='miei_hotel'),
    path('nuovo/', views.CreaHotelView.as_view(), name='crea_hotel'),
    path('<int:pk>/modifica/', views.ModificaHotelView.as_view(), name='modifica_hotel'),
    path('<int:pk>/camere/', views.GestisciCamereHotelView.as_view(), name='gestisci_camere'),
    path('camere/<int:pk>/modifica/', views.ModificaCameraView.as_view(), name='modifica_camera'),
    path('camere/<int:pk>/elimina/', views.EliminaCameraView.as_view(), name='elimina_camera'),
    path('<int:pk>/servizi/', views.GestisciServiziHotelView.as_view(), name='gestisci_servizi'),
]
