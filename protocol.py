import socket, threading, time, base64
from utils import current_time, hash_file, split_file
from message_handler import MessageHandler
from file_transfer import FileTransferManager
from datetime import datetime

BROADCAST_IP = '<broadcast>'
BUFFER_SIZE = 65507
port = 5000
total_received = 0

class UDPProtocol:
    def __init__(self, name):
        self.name = name
        self.port = port
        self.devices = {}  # {name: (ip, port, last_heartbeat)}
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1048576)  # 2MB send buffer
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1048576)  # 2MB receive buffer
        self.sock.bind(("", port))
        self.handler = MessageHandler(self)
        self.pending_acks = {}  # {uid: (msg, addr, timestamp, attempts)}        
        self.file_manager = FileTransferManager(self)
        self.socket_lock = threading.Lock()
        #threading.Thread(target=self.retransmit, daemon=True).start()
    
    def send(self, msg, addr):
        try:
            if not isinstance(msg, str) or not msg.strip():
                print(f"[ERRO] Mensagem inválida para envio: ")
                return

            if not (isinstance(addr, tuple) and len(addr) == 2):
                print(f"[ERRO] Endereço inválido para envio: ")
                return

            parts = msg.strip().split()
            if not parts:
                print(f"[ERRO] Mensagem sem conteúdo válido: ")
                return

            if parts[0] not in ["HEARTBEAT", "ACK"]:
                if len(parts) < 2:
                    print(f"[ERRO] Mensagem malformada (sem UID): ")
                    return
                uid = parts[1]
                self.pending_acks[uid] = (msg, addr, time.time(), 0, False)

            try:
                self.sock.sendto(msg.encode(), addr)
            except socket.error as e:
                print(f"Socket error durante envio: {e}")
        except Exception as e:
            print(f"[ERRO] Exceção inesperada em send(): {e} - msg: {msg}, addr: {addr}")



    def handle_ack(self, uid):
        #print("tratando de", uid)
        #with self.socket_lock:
        if uid in self.pending_acks:
            msg, addr, sent_time, attempts, _ = self.pending_acks[uid]
            self.pending_acks[uid] = (msg, addr, sent_time, attempts, True)

    def heartbeat_loop(self):
        while True:
            msg = f"HEARTBEAT {self.name} {self.port}"
            try:
                self.sock.sendto(msg.encode(), (BROADCAST_IP, self.port))
            except socket.error as e:
                print(f"Erro ao enviar heartbeat: {e}")
            time.sleep(5)
            
    def clean_devices(self):
        while True:
            now = time.time()
            inactive = [name for name, (_, _, last_seen) in self.devices.items() if now - last_seen > 10]
            for name in inactive:
                del self.devices[name]
            time.sleep(1)


    def listen_loop(self):

        total_received = 0
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)                

                msg = data.decode()
                sender_ip, sender_port = addr


                if sender_ip == self.name and sender_port == self.port:
                    continue                                    

                if msg.startswith("HEARTBEAT"):
                    parts = msg.split()
                    name = parts[1]
                    port = int(parts[2])
                    ip = addr[0]
                    last_seen = time.time()
                    self.devices[name] = (ip, port, last_seen)
                elif msg.startswith(("TALK", "FILE", "CHUNK", "END", "ACK", "NACK")):
                    try:
                        #print(f"[{datetime.now()}] Despachando mensagem para handler: {msg}")
                        self.handler.handle(msg, addr)
                    except Exception as e:
                        print(f"[{datetime.now()}] Erro no handler para mensagem {msg}: {e}")
                else:
                    print(f"Mensagem desconhecida: {msg}")
            except socket.error as e:
                print(f"Socket error in listen_loop: {e}")
                continue

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

                print(f"Enviando para {name} ({ip}:{port}): {msg}")
                
                # Envia a mensagem
                self.send(msg, (ip, port))
                return
        print("Dispositivo não encontrado.")


    def send_file(self, target_name, filepath):
        self.file_manager.send_file(target_name, filepath)
