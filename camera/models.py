from django.db import models

class Camera(models.Model):
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=100)
    usuario = models.CharField(max_length=50, blank=True, null=True)
    rtsp_sub = models.CharField(max_length=255, blank=True, null=True)

    @property
    def rtsp_url(self):
        # main stream via MediaMTX
        return f"rtsp://mediamtx:8554/cam{self.id}"

    @property
    def rtsp_sub_url(self):
        # substream via MediaMTX
        return f"rtsp://mediamtx:8554/cam{self.id}_sub"

    def __str__(self):
        return f"{self.nome} - {self.endereco}"