import cv2
import time
from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse
from .models import Camera
import os
from datetime import datetime
from django.conf import settings
from .funcs import verificar_espaco

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")


def open_camera(rtsp_url, nome, retries=5, retry_delay=5):
    attempt = 0
    while attempt < retries:
        cap = cv2.VideoCapture(rtsp_url + '?tcp', cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 120000)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 18)

        ret, frame = cap.read()
        if ret:
            print(f"Câmera {nome} conectada com sucesso!")
            return cap, frame
        else:
            print(f"Câmera {nome} offline, tentando novamente em {retry_delay}s...")
            cap.release()
            attempt += 1
            time.sleep(retry_delay)
    print(f"Não foi possível conectar à câmera {nome}.")
    return None, None

def gen_frames(rtsp_url, camera_name):
    VIDEO_WIDTH, VIDEO_HEIGHT = 1024, 768
    VIDEO_FPS = 15.0
    cap, frame1 = open_camera(rtsp_url, camera_name)
    if cap is None:
        return  # Sai do generator se não conseguiu conectar

    frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
    frame1_gray = cv2.GaussianBlur(frame1_gray, (15, 15), 0)

    recording = False
    out = None
    start_time = None
    folder_path = None
    photo_taken = False

    while True:
        ret, frame2 = cap.read()
        if not ret:
            print(f"Câmera {camera_name} perdeu conexão. Tentando reconectar...")
            cap.release()
            cap, frame2 = open_camera(rtsp_url, camera_name)
            if cap is None:
                return
            frame1_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            frame1_gray = cv2.GaussianBlur(frame1_gray, (15, 15), 0)
            continue

        frame2_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        frame2_gray = cv2.GaussianBlur(frame2_gray, (15, 15), 0)
        diff = cv2.absdiff(frame1_gray, frame2_gray)
        _, thresh = cv2.threshold(diff, 38, 255, cv2.THRESH_BINARY)
        thresh = cv2.dilate(thresh, None, iterations=2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        movement_detected = any(cv2.contourArea(c) >= 200 for c in contours)

        now = datetime.now()
        timestamp = now.strftime("%H-%M-%S")

        if movement_detected and not recording:
            recording = True
            start_time = time.time()
            movement_time = time.time()
            photo_taken = False

            folder_path = os.path.join(MOTION_FOLDER, f"{now.year}", f"{now.month:02}", f"{now.day:02}")
            os.makedirs(folder_path, exist_ok=True)

            video_path = os.path.join(folder_path, f"{camera_name}_{timestamp}.mp4")
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(video_path, fourcc, VIDEO_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))

        if recording:
            frame_resized = cv2.resize(frame2, (VIDEO_WIDTH, VIDEO_HEIGHT))
            out.write(frame_resized)

            if not photo_taken and time.time() - movement_time >= 0.5:
                foto_path = os.path.join(folder_path, f"{camera_name}_{timestamp}.jpg")
                cv2.imwrite(foto_path, frame2)
                photo_taken = True
                verificar_espaco()

            if time.time() - start_time >= 20:
                recording = False
                out.release()
                out = None
                photo_taken = False
                verificar_espaco()

        frame1_gray = frame2_gray

        ret, buffer = cv2.imencode('.jpg', frame2)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

def camera_feed(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    rtsp_url = camera.rtsp_url
    camera_name = camera.nome.replace(" ", "_")
    return StreamingHttpResponse(gen_frames(rtsp_url, camera_name),
                                 content_type='multipart/x-mixed-replace; boundary=frame')

def lista_cameras(request):
    cameras = Camera.objects.all()
    return render(request, "cameras/lista.html", {"cameras": cameras})

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
                    arquivos.append({
                        "nome": arquivo,
                        "caminho": f"motion/{a}/{int(m):02}/{int(d):02}/{arquivo}"
                    })

    return render(request, "cameras/gravacoes.html", {"arquivos": arquivos, "MEDIA_URL": settings.MEDIA_URL})
