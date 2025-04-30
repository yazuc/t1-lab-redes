import socket, threading, time, base64
from utils import current_time, hash_file, split_file
from message_handler import MessageHandler
from file_transfer import FileTransferManager
#from teste import get_broadcast_address

BROADCAST_IP = '<broadcast>'
BUFFER_SIZE = 65507
port = 5000

class UDPProtocol:
    def __init__(self, name):
        self.name = name
        self.port = port
        self.devices = {}  # {name: (ip, port, last_heartbeat)}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", port))
        self.handler = MessageHandler(self)
        self.file_manager = FileTransferManager(self)
        self.pending_acks = {}  # {uid: (msg, addr, timestamp, attempts)}
        threading.Thread(target=self.retransmit, daemon=True).start()
    
    def send(self, msg, addr):
        uid = msg.split()[1] if msg.split()[0] != "HEARTBEAT" else None
        if uid:
            self.pending_acks[uid] = (msg, addr, time.time(), 0)
        self.sock.sendto(msg.encode(), addr)

    def retransmit(self):
        while True:
            now = time.time()
            for uid, (msg, addr, sent_time, attempts) in list(self.pending_acks.items()):
                if now - sent_time > 2 and attempts < 3:
                    self.sock.sendto(msg.encode(), addr)
                    self.pending_acks[uid] = (msg, addr, now, attempts + 1)
                elif attempts >= 3:
                    print(f"Falha ao enviar {msg}: timeout após 3 tentativas")
                    del self.pending_acks[uid]
            time.sleep(0.5)

    def handle_ack(self, uid):
        if uid in self.pending_acks:
            print(f"ACK recebido para {uid}")
            del self.pending_acks[uid]

    def heartbeat_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            msg = f"HEARTBEAT {self.name} {self.port}"
            sock.sendto(msg.encode(), (BROADCAST_IP, self.port))
            time.sleep(5)
            
    def clean_devices(self):
        while True:
            now = time.time()
            inactive = [name for name, (_, _, last_seen) in self.devices.items() if now - last_seen > 10]
            for name in inactive:
                del self.devices[name]
            time.sleep(1)


    def listen_loop(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.bind(("", self.port))

        while True:
            data, addr = self.sock.recvfrom(2048)
            msg = data.decode()
            #print(f"Recebido de {addr}: {data.decode()}")  # Depuração para mostrar a mensagem recebida
            sender_ip, sender_port = addr

            if sender_ip == self.name and sender_port == self.port:
                continue

            # Verifica se a mensagem é um HEARTBEAT
            if msg.startswith("HEARTBEAT"):
                parts = msg.split()
                name = parts[1]
                port = int(parts[2])  # <-- Aqui, usamos a porta enviada na mensagem
                ip = addr[0]
                last_seen = time.time()

                # Agora estamos usando a porta correta do outro dispositivo
                self.devices[name] = (ip, port, last_seen)

            if msg.startswith("TALK"):
                uid, message = msg.split(maxsplit=1)  # Obtém o UID e a mensagem
                print(f"Mensagem recebida de {addr[0]}: [{uid}] {message}")

            # FILE (início do envio)
            if msg.startswith("FILE"):
                self.file_manager.handle_file_request(msg.split(" ", 1), addr)
                continue

            # CHUNK (parte do arquivo)
            if msg.startswith("CHUNK"):
                self.file_manager.handle_chunk(msg.split(" ", 1), addr)
                continue

            # END (finalização do envio)
            if msg.startswith("END"):
                self.file_manager.handle_end(msg.split(" ", 1), addr)
                continue

            # ACK (resposta de recebimento)
            if msg.startswith("ACK"):
                parts = msg.split()
                if len(parts) >= 2:
                    uid = parts[1]
                    self.file_manager.handle_ack(uid)
                continue

            # NACK (resposta negativa)
            if msg.startswith("NACK"):
                print(f"NACK recebido: {msg}")
                continue

            # Qualquer outra coisa
            #print(f"Mensagem desconhecida: {msg}")


    def send(self, msg, addr):
        self.sock.sendto(msg.encode(), addr)

    def send_broadcast(self, msg):
        self.send(msg, (BROADCAST_IP, self.port))

    def print_devices(self):
        now = time.time()
        ativos = [(name, ip, port, round(now - last_seen, 1))
                for name, (ip, port, last_seen) in self.devices.items()
                if now - last_seen < 10]  # considerar inativo após 10s

        if not ativos:
            print("Nenhum dispositivo ativo.")
            return

        print("Dispositivos ativos (últimos 10s):")
        for name, ip, port, age in sorted(ativos, key=lambda x: x[0].lower()):
            print(f"  - {name:<12} {ip}:{port:<5} | Último contato: {age:>4}s atrás")


    def send_talk(self, target_name, message):
        for name, (ip, port, _) in self.devices.items():
            if name == target_name:
                uid = str(int(time.time() * 1000))
                msg = f"TALK {uid} {message}"

                # Verifica se a mensagem foi formada corretamente
                print(f"Enviando para {name} ({ip}:{port}): {msg}")

                # Envia a mensagem
                self.send(msg, (ip, port))
                return
        print("Dispositivo não encontrado.")


    def send_file(self, target_name, filepath):
        self.file_manager.send_file(target_name, filepath)
