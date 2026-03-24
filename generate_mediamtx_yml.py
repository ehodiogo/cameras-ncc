import os
from decouple import config

ADMIN_PASSWORD = config("ADMIN_PASSWORD")

# lista das câmeras
cameras = [
    {"name": "cam1", "ip": "10.1.4.40"},
    {"name": "cam2", "ip": "10.1.4.41"},
    {"name": "cam3", "ip": "10.1.4.43"},
]

lines = ["paths:"]
for cam in cameras:
    lines.append(f"  {cam['name']}:")
    lines.append(f"    source: rtsp://admin:{ADMIN_PASSWORD}@{cam['ip']}:554/h264/ch1/main/av_stream")
    lines.append(f"  {cam['name']}_sub:")
    lines.append(f"    source: rtsp://admin:{ADMIN_PASSWORD}@{cam['ip']}:554/h264/ch1/sub/av_stream")

# gera dentro do /app no container ou no host se quiser testar localmente
output_path = os.path.join(os.getcwd(), "mediamtx.yml")
with open(output_path, "w") as f:
    f.write("\n".join(lines))

print(f"mediamtx.yml gerado com sucesso em {output_path}")