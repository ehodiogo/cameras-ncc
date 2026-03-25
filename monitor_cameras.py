import os
import django
import cv2
import time
from datetime import datetime
from threading import Thread
from django.conf import settings
import subprocess

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ncc.settings')
django.setup()

from camera.models import Camera
from camera.funcs import verificar_espaco

MOTION_FOLDER = os.path.join(settings.MEDIA_ROOT, "motion")

VIDEO_WIDTH, VIDEO_HEIGHT = 1024, 768
VIDEO_FPS = 30


def open_camera(rtsp_url, nome):
    cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
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
    rtsp_url = f"rtsp://172.17.0.1:8554/cam{camera.id}"

    while True:
        cap, frame1 = open_camera(rtsp_url, nome)
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
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-f", "rawvideo",
                    "-vcodec", "rawvideo",
                    "-pix_fmt", "bgr24",
                    "-s", f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}",
                    "-r", str(VIDEO_FPS),
                    "-i", "-",
                    "-c:v", "libx264",
                    "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p",
                    video_path
                ]
                ffmpeg_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

            if recording:
                frame_resized = cv2.resize(frame2, (VIDEO_WIDTH, VIDEO_HEIGHT))
                try:
                    ffmpeg_proc.stdin.write(frame_resized.tobytes())
                except BrokenPipeError:
                    print(f"[{nome}] Erro ao escrever no FFmpeg")
                    recording = False
                    ffmpeg_proc = None

                # Captura foto
                if not photo_taken and time.time() - movement_time >= 0.5:
                    foto_path = os.path.join(folder_path, f"{nome}_{timestamp}.jpg")
                    cv2.imwrite(foto_path, frame2)
                    photo_taken = True
                    verificar_espaco()

                # Para gravação após 20s
                if time.time() - start_time >= 20:
                    recording = False
                    if ffmpeg_proc:
                        ffmpeg_proc.stdin.close()
                        ffmpeg_proc.wait()
                        ffmpeg_proc = None
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
