import cv2
from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse
from .models import Camera
import os
from datetime import datetime
import time
from django.conf import settings
from .funcs import verificar_espaco
from ultralytics import YOLO

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")
yolo_model = YOLO("yolov8n.pt")
PERSON_CLASS_ID = 0

def open_camera(rtsp_url, nome):
    cap = cv2.VideoCapture(rtsp_url + '?tcp', cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 30000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 18)
    ret, frame = cap.read()
    if ret:
        print(f"Câmera {nome} conectada com sucesso!")
        return cap, frame
    else:
        print(f"Câmera {nome} offline.")
        cap.release()
        return None, None


def gen_frames(rtsp_url, camera_name):
    VIDEO_WIDTH, VIDEO_HEIGHT = 1024, 768
    VIDEO_FPS = 15.0

    cap, frame1 = open_camera(rtsp_url, camera_name)
    if cap is None:
        yield None  # sinaliza câmera OFF
        return

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
            yield None
            return

        results = yolo_model(frame2, classes=[PERSON_CLASS_ID], verbose=False)
        if results and len(results[0].boxes) > 0:
            print(f"[{camera_name}] Pessoa detectada!")

            for box in results[0].boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])

                cv2.rectangle(frame2, (x1, y1), (x2, y2), (0, 255, 0), 2)

                cv2.putText(
                    frame2,
                    "Pessoa",
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2
                )

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

    def generator():
        for frame in gen_frames(rtsp_url, camera_name):
            if frame is None:
                placeholder_path = os.path.join(settings.STATIC_ROOT, "camera_off.jpg")
                placeholder = cv2.imread(placeholder_path)
                ret, buffer = cv2.imencode('.jpg', placeholder)
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            else:
                yield frame

    return StreamingHttpResponse(generator(),
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
