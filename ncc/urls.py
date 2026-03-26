from django.contrib import admin
from django.urls import path
from camera.views import detalhe_camera, camera_feed, painel_cameras, listar_gravacoes, dashboard
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cameras/<int:pk>/', detalhe_camera, name='detalhe_camera'),
    path('camera/<int:pk>/feed', camera_feed, name='camera_feed'),
    path('', painel_cameras, name='painel_cameras'),
    path('gravacoes/', listar_gravacoes, name='listar_gravacoes'),
    path('dashboard/', dashboard, name='dashboard_cameras')
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)