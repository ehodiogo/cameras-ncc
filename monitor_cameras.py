import os
import django
import cv2
import time
from datetime import datetime
from threading import Thread
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ncc.settings')
django.setup()

from camera.models import Camera
from camera.funcs import verificar_espaco

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")

VIDEO_WIDTH, VIDEO_HEIGHT = 1024, 768
VIDEO_FPS = 15.0


def open_camera(rtsp_url, nome):
    cap = cv2.VideoCapture(rtsp_url + '?tcp', cv2.CAP_FFMPEG)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 30000)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 18)
    ret, frame = cap.read()
    if ret:
        print(f"[{nome}] Câmera conectada com sucesso.")
        return cap, frame
    else:
        print(f"[{nome}] Câmera offline.")
        cap.release()
        return None, None


def monitorar_camera(camera):
    nome = camera.nome.replace(" ", "_")
    rtsp = camera.rtsp_url

    while True:
        cap, frame1 = open_camera(rtsp, nome)
        if cap is None:
            time.sleep(10)
            continue

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
                print(f"[{nome}] Falha na leitura. Tentando reconectar...")
                cap.release()
                break
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
                video_path = os.path.join(folder_path, f"{nome}_{timestamp}.mp4")
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(video_path, fourcc, VIDEO_FPS, (VIDEO_WIDTH, VIDEO_HEIGHT))

            if recording:
                frame_resized = cv2.resize(frame2, (VIDEO_WIDTH, VIDEO_HEIGHT))
                out.write(frame_resized)

                if not photo_taken and time.time() - movement_time >= 0.5:
                    foto_path = os.path.join(folder_path, f"{nome}_{timestamp}.jpg")
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

        time.sleep(5)


def iniciar_monitoramento():
    cameras = Camera.objects.all()
    print(f"Iniciando monitoramento de {len(cameras)} câmeras...")
    for camera in cameras:
        Thread(target=monitorar_camera, args=(camera,), daemon=True).start()

    while True:
        time.sleep(60)


if __name__ == "__main__":
    iniciar_monitoramento()
