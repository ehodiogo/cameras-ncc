import cv2
import time
from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse
from .models import Camera
import os
from datetime import datetime

def camera_feed(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    rtsp_url = camera.rtsp_url
    camera_name = camera.nome.replace(" ", "_")

    def gen_frames():
        cap = cv2.VideoCapture(rtsp_url)
        ret, frame1 = cap.read()
        if not ret:
            return
        frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        frame1_gray = cv2.GaussianBlur(frame1_gray, (15, 15), 0)

        recording = False
        out = None
        start_time = None

        while True:
            ret, frame2 = cap.read()
            if not ret:
                break

            frame2_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
            frame2_gray = cv2.GaussianBlur(frame2_gray, (15, 15), 0)

            diff = cv2.absdiff(frame1_gray, frame2_gray)
            _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
            thresh = cv2.dilate(thresh, None, iterations=2)

            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            movement_detected = any(cv2.contourArea(c) >= 200 for c in contours)

            if movement_detected and not recording:
                recording = True
                start_time = time.time()

                now = datetime.now()
                folder_path = f"motion/{now.year}/{now.month:02}/{now.day:02}"
                os.makedirs(folder_path, exist_ok=True)

                timestamp = now.strftime("%H-%M-%S")

                foto_path = f"{folder_path}/{camera_name}_{timestamp}.jpg"
                cv2.imwrite(foto_path, frame2)

                height, width, _ = frame2.shape
                video_path = f"{folder_path}/{camera_name}_{timestamp}.avi"
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                out = cv2.VideoWriter(video_path, fourcc, 20.0, (width, height))

            if recording:
                out.write(frame2)
                if time.time() - start_time >= 20:
                    recording = False
                    out.release()
                    out = None

            frame1_gray = frame2_gray
            ret, buffer = cv2.imencode('.jpg', frame2)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    return StreamingHttpResponse(gen_frames(),
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

MOTION_FOLDER = "motion"

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
                for arquivo in sorted(os.listdir(dia_path)):
                    if arquivo.endswith(".avi") or arquivo.endswith(".jpg"):
                        arquivos.append({
                            "nome": arquivo,
                            "caminho": os.path.join(dia_path, arquivo).replace("\\", "/")
                        })

    return render(request, "cameras/gravacoes.html", {"arquivos": arquivos})