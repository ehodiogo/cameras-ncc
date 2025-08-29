from django.db import models
from decouple import config

class Camera(models.Model):
    senha = config("ADMIN_PASSWORD")
    nome = models.CharField(max_length=100)
    endereco = models.CharField(max_length=100)
    usuario = models.CharField(max_length=50, blank=True, null=True)

    @property
    def rtsp_url(self):
        if self.usuario and self.senha:
            return f"rtsp://{self.usuario}:{self.senha}@{self.endereco}:554/user=admin_password={self.senha}_channel=1_stream=0.sdp?real_stream"
        return f"rtsp://{self.endereco}:554/user=admin_password={self.senha}_channel=1_stream=0.sdp?real_stream"

    def __str__(self):
        return f"{self.nome} - {self.endereco}"
