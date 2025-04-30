import os, hashlib
import socket

def get_local_ip():
    try:
        # Tenta se conectar a um servidor externo (Google DNS), só para descobrir o IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # não envia nada, só resolve a rota
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # fallback se estiver offline


def current_time():
    import time
    return int(time.time() * 1000)

def split_file(path, chunk_size=1024):
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk

def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()
