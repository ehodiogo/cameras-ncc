import cv2
from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse
from .models import Camera
import os
from datetime import datetime
import time
from django.conf import settings
from .funcs import verificar_espaco
import subprocess
import numpy as np
from django.core.paginator import Paginator
from datetime import datetime
from collections import Counter

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")

def open_camera(rtsp_url, nome):
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)

    # Ajustes pra reduzir travamento
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

    ret, frame = cap.read()
    if ret:
        print(f"Câmera {nome} conectada!")
        return cap
    else:
        print(f"Câmera {nome} offline.")
        cap.release()
        return None


def gen_frames(rtsp_url, camera_name):
    cap = open_camera(rtsp_url, camera_name)

    if cap is None:
        yield None
        return

    while True:
        ret, frame = cap.read()

        if not ret:
            print(f"{camera_name} reconectando...")
            cap.release()
            time.sleep(2)
            cap = open_camera(rtsp_url, camera_name)

            if cap is None:
                yield None
                continue
            else:
                continue

        # Só encode (sem processamento pesado)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        
def camera_feed(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    rtsp_url = camera.rtsp_sub_url
    camera_name = camera.nome.replace(" ", "_")

    def generator():
        for frame in gen_frames(rtsp_url, camera_name):
            if frame is None:
                placeholder_path = os.path.join(settings.BASE_DIR, "static", "camera_off.jpg")
                placeholder = cv2.imread(placeholder_path)
                ret, buffer = cv2.imencode('.jpg', placeholder)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                yield frame

    return StreamingHttpResponse(generator(),
                                 content_type='multipart/x-mixed-replace; boundary=frame')

def detalhe_camera(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    return render(request, "cameras/detalhe.html", {"camera": camera})


def painel_cameras(request):
    cameras = Camera.objects.all()
    return render(request, "cameras/painel.html", {"cameras": cameras})


def listar_gravacoes(request):
    ano = request.GET.get("ano")
    mes = request.GET.get("mes")
    dia = request.GET.get("dia")
    hoje = request.GET.get("hoje")
    page_number = request.GET.get("page", 1)          # Página atual
    page_size = request.GET.get("page_size", 20)     # Tamanho da página padrão 20

    try:
        page_size = int(page_size)
        if page_size <= 0:
            page_size = 20
    except ValueError:
        page_size = 20

    arquivos = []

    if hoje == "1":
        now = datetime.now()
        ano, mes, dia = now.year, now.month, now.day

    ano_folders = [ano] if ano else sorted(os.listdir(MOTION_FOLDER))
    for a in ano_folders:
        ano_path = os.path.join(MOTION_FOLDER, str(a))
        if not os.path.exists(ano_path):
            continue
        mes_folders = [mes] if mes else sorted(os.listdir(ano_path))
        for m in mes_folders:
            mes_path = os.path.join(ano_path, f"{int(m):02}")
            if not os.path.exists(mes_path):
                continue
            dia_folders = [dia] if dia else sorted(os.listdir(mes_path))
            for d in dia_folders:
                dia_path = os.path.join(mes_path, f"{int(d):02}")
                if not os.path.exists(dia_path):
                    continue

                arquivos_dia = [f for f in os.listdir(dia_path) if f.endswith(".mp4") or f.endswith(".jpg")]
                arquivos_dia.sort(key=lambda x: x.split('_')[-1].split('.')[0])

                for arquivo in arquivos_dia:
                    try:
                        # pega o horário do nome (HH-MM-SS)
                        hora_str = arquivo.split('_')[-1].split('.')[0]
                        hora_formatada = hora_str.replace("-", ":")

                        data_obj = datetime(int(a), int(m), int(d))
                        data_formatada = data_obj.strftime("%d/%m/%Y")  

                    except Exception:
                        hora_formatada = ""
                        data_formatada = ""

                    arquivos.append({
                        "nome": arquivo,
                        "caminho": f"motion/{a}/{int(m):02}/{int(d):02}/{arquivo}",
                        "data": data_formatada,
                        "hora": hora_formatada,
                        "data_hora": f"{data_formatada} {hora_formatada}"
                    })

    arquivos.sort(key=lambda x: x['nome'].split('_')[-1].split('.')[0], reverse=True)
    paginator = Paginator(arquivos, page_size)
    page_obj = paginator.get_page(page_number)

    return render(request, "cameras/gravacoes.html", {
        "arquivos": page_obj, 
        "MEDIA_URL": settings.MEDIA_URL,
        "paginator": paginator,
        "page_number": int(page_number),
        "page_size": page_size
    })

def dashboard(request):

    now = datetime.now()
    base_path = os.path.join(
        MOTION_FOLDER,
        str(now.year),
        f"{now.month:02}",
        f"{now.day:02}"
    )

    arquivos = []

    if os.path.exists(base_path):
        for f in os.listdir(base_path):
            if f.endswith(".mp4") or f.endswith(".jpg"):
                arquivos.append(f)

    horas = []
    cameras = []
    timeline = []

    for nome in arquivos:
        partes = nome.split("_")

        if len(partes) >= 2:
            camera = partes[0]
            tempo = partes[-1].split(".")[0]

            h, m, s = tempo.split("-")

            horas.append(h)
            cameras.append(camera)

            segundos = int(h)*3600 + int(m)*60 + int(s)

            timeline.append({
                "segundos": segundos,
                "nome": nome
            })

    stats = {
        "total": len(arquivos),
        "por_hora": dict(Counter(horas)),
        "por_camera": dict(Counter(cameras)),
    }

    return render(request, "cameras/dashboard.html", {
        "stats": stats,
        "timeline": timeline,
        "MEDIA_URL": settings.MEDIA_URL,
        "base_path": f"motion/{now.year}/{now.month:02}/{now.day:02}/"
    })