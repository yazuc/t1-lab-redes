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
            
                if size == 0:
                    open(f"recv_{uid}.tmp", "wb").close()  # cria o arquivo vazio no destino
                    self.protocol.send(f"END {uid} {hash_file(filepath)}", addr)
                    return

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
        
        # Verifica se o arquivo já existe
        target_filename = filename
        counter = 1
        while os.path.exists(target_filename):
            name, ext = os.path.splitext(filename)
            target_filename = f"{name}_{counter}{ext}"
            counter += 1

        # Armazena o nome do arquivo ajustado
        self.waiting_acks[uid] = {"filename": target_filename, "chunks": []}

        # Cria o arquivo com o nome ajustado
        with open(target_filename, "wb") as f:
            pass

    def handle_chunk(self, parts, addr):
        uid, seq, data = parts[1].split(" ", 2)
        if uid not in self.waiting_acks:
            print(f"[ERRO] UID {uid} não encontrado em waiting_acks.")
            return
        
        raw = base64.b64decode(data)
        target_filename = self.waiting_acks[uid]["filename"]
        with open(target_filename, "ab") as f:
            f.write(raw)
        self.protocol.send(f"ACK {uid}", addr)

    def handle_end(self, parts, addr):
        uid, hash_remote = parts[1].split()
        if uid not in self.waiting_acks:
            print(f"[ERRO] UID {uid} não encontrado em waiting_acks.")
            return
        
        target_filename = self.waiting_acks[uid]["filename"]
        
        if not os.path.exists(target_filename):
            print(f"[ERRO] Arquivo {target_filename} ainda não existe. Talvez CHUNKs não chegaram?")
            return

        hash_local = hash_file(target_filename)
        if hash_local == hash_remote:
            print(f"Arquivo {target_filename} recebido com sucesso.")
            self.protocol.send(f"ACK {uid}", addr)
        else:
            print(f"Arquivo {target_filename} corrompido.")
            self.protocol.send(f"NACK {uid} hash mismatch", addr)
        
        # Limpa o waiting_acks após o término
        del self.waiting_acks[uid]

    def handle_ack(self, uid):
        print(f"ACK recebido para {uid}")