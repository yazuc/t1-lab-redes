import os, base64, threading, time
from utils import split_file, hash_file

class FileTransferManager:
    def __init__(self, protocol):
        self.protocol = protocol
        self.waiting_acks = {}

    def send_file(self, target_name, filepath):
        for name, (ip, port, _) in self.protocol.devices.items():
            if name == target_name:
                addr = (ip, port)
                size = os.path.getsize(filepath)
                uid = str(int(time.time() * 1000))
                self.protocol.send(f"FILE {uid} {os.path.basename(filepath)} {size}", addr)

                chunks = split_file(filepath)
                def transfer():
                    for seq, chunk in enumerate(chunks):
                        encoded = base64.b64encode(chunk).decode()
                        msg = f"CHUNK {uid} {seq} {encoded}"
                        self.protocol.send(msg, addr)
                        time.sleep(0.05)  # evite flooding

                    h = hash_file(filepath)
                    self.protocol.send(f"END {uid} {h}", addr)
                threading.Thread(target=transfer, daemon=True).start()
                return
        print("Dispositivo não encontrado.")

    def handle_file_request(self, parts, addr):
        uid, filename, size = parts[1].split()
        print(f"Iniciando recebimento de {filename} ({size} bytes)")
        self.waiting_acks[uid] = []

    def handle_chunk(self, parts, addr):
        uid, seq, data = parts[1].split(" ", 2)
        raw = base64.b64decode(data)
        path = f"recv_{uid}.tmp"
        with open(path, "ab") as f:
            f.write(raw)
        self.protocol.send(f"ACK {uid}", addr)

    def handle_end(self, parts, addr):
        uid, hash_remote = parts[1].split()
        path = f"recv_{uid}.tmp"
        hash_local = hash_file(path)
        if hash_local == hash_remote:
            print("Arquivo recebido com sucesso.")
            self.protocol.send(f"ACK {uid}", addr)
        else:
            print("Arquivo corrompido.")
            self.protocol.send(f"NACK {uid} hash mismatch", addr)

    def handle_ack(self, uid):
        print(f"ACK recebido para {uid}")
