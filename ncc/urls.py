from django.contrib import admin
from django.urls import path
from camera.views import detalhe_camera, lista_cameras, camera_feed, painel_cameras, listar_gravacoes

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cameras/', lista_cameras),
    path('cameras/<int:pk>/', detalhe_camera, name='detalhe_camera'),
    path('camera/<int:pk>/feed', camera_feed, name='camera_feed'),
    path('painel/', painel_cameras, name='painel_cameras'),
    path('gravacoes/', listar_gravacoes, name='listar_gravacoes'),
]
