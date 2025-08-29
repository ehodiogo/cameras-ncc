from django.shortcuts import render, get_object_or_404
from django.http import StreamingHttpResponse
from .models import Camera
import cv2

def camera_feed(request, pk):
    camera = get_object_or_404(Camera, pk=pk)
    rtsp_url = camera.rtsp_url

    def gen_frames():
            cap = cv2.VideoCapture(rtsp_url)
            ret, frame1 = cap.read()
            if not ret:
                return
            frame1_gray = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
            frame1_gray = cv2.GaussianBlur(frame1_gray, (15, 15), 0)

            while True:
                ret, frame2 = cap.read()
                if not ret:
                    break

                frame2_gray = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
                frame2_gray = cv2.GaussianBlur(frame2_gray, (15, 15), 0)

                diff = cv2.absdiff(frame1_gray, frame2_gray)
                _, thresh = cv2.threshold(diff, 15, 255,
                                          cv2.THRESH_BINARY)
                thresh = cv2.dilate(thresh, None, iterations=2)

                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                for contour in contours:
                    if cv2.contourArea(contour) < 200:
                        continue
                    (x, y, w, h) = cv2.boundingRect(contour)
                    cv2.rectangle(frame2, (x, y), (x + w, y + h), (0, 255, 0), 2)

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
