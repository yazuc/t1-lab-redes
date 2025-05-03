import os, base64, threading, time
from utils import split_file, hash_file

class FileTransferManager:
    def __init__(self, protocol):
        self.protocol = protocol
        self.waiting_acks = {}
        self.lock = threading.Lock()  # Para acesso seguro aos dicionários

    def wait_for_ack(self, ack_id, timeout=5.0):
        """Aguarda o ACK com o ID especificado por até 'timeout' segundos."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.lock:
                if ack_id in self.protocol.pending_acks:
                    return True
            time.sleep(0.1)  # Evitar consumo excessivo de CPU
        return False

    def handle_ack(self, uid):
        """Registra o recebimento de um ACK."""
        with self.lock:
            self.protocol.pending_acks[uid] = True
            print(f"ACK recebido para {uid} em file_transfer")

    def send_file(self, target_name, filepath):
        if not os.path.exists(filepath):
            print(f"Arquivo {filepath} não encontrado.")
            return

        for name, (ip, port, _) in self.protocol.devices.items():
            if name == target_name:
                addr = (ip, port)
                size = os.path.getsize(filepath)
                uid = str(int(time.time() * 1000))

                # Enviar FILE e aguardar ACK
                self.protocol.send(f"FILE {uid} {os.path.basename(filepath)} {size}", addr)
                print(f"Enviando FILE {uid}")
                if not self.wait_for_ack(uid, timeout=5.0):
                    print(f"Timeout aguardando ACK para FILE {uid}")
                    return

                # Tratamento de arquivo vazio
                if size == 0:
                    h = hash_file(filepath)
                    self.protocol.send(f"END {uid}_end {h}", addr)
                    print(f"Enviando END {uid}_end")
                    if not self.wait_for_ack(uid, timeout=5.0):
                        print(f"Timeout aguardando ACK para END {uid}")
                        return
                    print("Transferência de arquivo vazio concluída.")
                    return

                # Enviar blocos CHUNK com leitura parcial
                chunk_size = 800
                total_chunks = (size + chunk_size - 1) // chunk_size  # Arredondamento para cima

                with open(filepath, "rb") as f:
                    seq = 0
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        encoded = base64.b64encode(chunk).decode()
                        chunk_id = f"{uid}_{seq}"
                        msg = f"CHUNK {chunk_id} {seq} {encoded}"
                        self.protocol.send(msg, addr)
                        if not self.wait_for_ack(chunk_id, timeout=5.0):
                            print(f"Timeout aguardando ACK para CHUNK {chunk_id}")
                            return
                        seq += 1
                        time.sleep(0.001)  # Evitar flooding
                        print(f"\rEnviando bloco {seq + 1}/{total_chunks} ({(seq + 1) / total_chunks * 100:.1f}%)", end="", flush=True)

                # Enviar mensagem END
                h = hash_file(filepath)
                end_id = f"{uid}_end"
                self.protocol.send(f"END {end_id} {h}", addr)
                print(f"Enviando END {end_id}")
                if not self.wait_for_ack(end_id, timeout=5.0):
                    print(f"Timeout aguardando ACK para END {uid}")
                    return

                print("Transferência concluída com sucesso.")
                return

        print("Dispositivo não encontrado.")

    def handle_file_request(self, parts, addr):
        uid, filename, size = parts[1].split()
        
        self.protocol.send(f"ACK {uid}", addr)
        
        print(f"Iniciando recebimento de {filename} ({size} bytes)")
        
        # Verifica se o arquivo já existe
        target_filename = filename
        counter = 1
        while os.path.exists(target_filename):
            name, ext = os.path.splitext(filename)
            target_filename = f"{name}_{counter}{ext}"
            counter += 1

        # Armazena o nome do arquivo ajustado
        self.waiting_acks[uid] = {"filename": target_filename, "chunks": [], "received_seqs": []}

        # Cria o arquivo com o nome ajustado
        with open(target_filename, "wb") as f:
            pass

    def handle_chunk(self, parts, addr):
        uid, seq, data = parts[1].split(" ", 2)
        uid, seq = uid.split("_")
        seq = int(seq)

        decoded = base64.b64decode(data)

        if uid not in self.waiting_acks:
            print(f"Recebeu chunk para UID desconhecido: {uid}")
            return
        
        print(f"\rRecebeu bloco {uid}_{seq}", end="", flush=True)

        # Armazenar chunk
        self.waiting_acks[uid]["chunks"].append((seq, decoded))
        self.protocol.send(f"ACK {uid}_{seq}", addr)

    def handle_end(self, parts, addr):
        uid, hash_remote = parts[1].split()
        uid, seq = uid.split("_")
        if uid not in self.waiting_acks:
            return

        # Enviar ACK imediato para confirmar recebimento do END
        self.protocol.send(f"ACK {uid}", addr)
        print("enviou ACK para o END, precisa validar hash ainda")

        target_filename = self.waiting_acks[uid]["filename"]
        chunks = sorted(self.waiting_acks[uid]["chunks"], key=lambda x: x[0])  # Reordenar
        with open(target_filename, "wb") as f:
            for _, data in chunks:
                f.write(data)

        hash_local = hash_file(target_filename)
        if hash_local == hash_remote:
            print("hash_local é igual ao hash_remote")
            print(f"Arquivo {target_filename} recebido com sucesso.")
            # ACK já foi enviado acima
        else:
            print(f"Arquivo {target_filename} corrompido.")
            os.remove(target_filename)  # Descartar arquivo corrompido
            self.protocol.send(f"NACK {uid} hash mismatch", addr)

        del self.waiting_acks[uid]
