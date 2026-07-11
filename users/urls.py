from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('registra/gestore/', views.RegistraGestoreView.as_view(), name='registra_gestore'),
    path('registra/cliente/', views.RegistraClienteView.as_view(), name='registra_cliente'),
    path('dashboard/gestore/', views.DashboardGestoreView.as_view(), name='dashboard_gestore'),
    path('profilo/modifica/', views.ModificaProfiloClienteView.as_view(), name='modifica_profilo_cliente'),
    path('profilo/modifica-gestore/', views.ModificaProfiloGestoreView.as_view(), name='modifica_profilo_gestore'),
]