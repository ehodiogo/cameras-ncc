import os
from django.conf import settings

# Limite máximo em MB
MAX_STORAGE_MB = 180  # exemplo: 1GB

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")

def verificar_espaco():
    if not MOTION_FOLDER or not os.path.exists(MOTION_FOLDER):
        return

    total_size = 0
    arquivos = []

    for root, dirs, files in os.walk(MOTION_FOLDER):
        for f in files:
            caminho = os.path.join(root, f)
            try:
                size = os.path.getsize(caminho)
                total_size += size
                arquivos.append((caminho, size, os.path.getmtime(caminho)))
            except FileNotFoundError:
                continue

    total_mb = total_size / (1024 * 1024)

    if total_mb > MAX_STORAGE_MB:
        arquivos.sort(key=lambda x: x[2])  # mais antigos primeiro
        while total_mb > MAX_STORAGE_MB and arquivos:
            caminho, size, _ = arquivos.pop(0)
            try:
                os.remove(caminho)
                total_mb -= size / (1024 * 1024)
                print(f"[CLEANUP] Arquivo removido: {caminho}")
            except Exception as e:
                print(f"[ERRO] Não conseguiu remover {caminho}: {e}")
