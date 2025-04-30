import socket, threading, time, base64
from utils import current_time, hash_file, split_file
from message_handler import MessageHandler
from file_transfer import FileTransferManager
from teste import get_broadcast_address

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
    

    def heartbeat_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        while True:
            msg = f"HEARTBEAT {self.name} {self.port}"
            sock.sendto(msg.encode(), (BROADCAST_IP, self.port))
            time.sleep(2)
            


    def listen_loop(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.sock.bind(("", self.port))

        while True:
            data, addr = self.sock.recvfrom(2048)
            msg = data.decode()
            print(f"Recebido de {addr}: {data.decode()}")  # Depuração para mostrar a mensagem recebida

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
