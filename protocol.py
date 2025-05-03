import socket, threading, time, base64
from utils import current_time, hash_file, split_file
from message_handler import MessageHandler
from file_transfer import FileTransferManager

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
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 2 * 1024 * 1024)  # 2MB send buffer
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024)  # 2MB receive buffer
        self.sock.bind(("", port))
        self.handler = MessageHandler(self)
        self.pending_acks = {}  # {uid: (msg, addr, timestamp, attempts)}        
        self.file_manager = FileTransferManager(self)
        self.socket_lock = threading.Lock()  # Add lock for thread-safe socket access
        #threading.Thread(target=self.retransmit, daemon=True).start()
    
    def send(self, msg, addr):
        parts = msg.split()
        if parts[0] not in ["HEARTBEAT", "ACK"]:
            uid = parts[1]
            self.pending_acks[uid] = (msg, addr, time.time(), 0)
        with self.socket_lock:
            try:
                self.sock.sendto(msg.encode(), addr)
            except socket.error as e:
                print(f"Socket error during send: {e}")


    def retransmit(self):
        while True:
            now = time.time()
            with self.socket_lock:  # Protect pending_acks access
                for uid, (msg, addr, sent_time, attempts) in list(self.pending_acks.items()):
                    if now - sent_time > 2 and attempts < 3:
                        try:
                            self.sock.sendto(msg.encode(), addr)
                            self.pending_acks[uid] = (msg, addr, now, attempts + 1)
                            print(f"Retransmitting {uid}, attempt {attempts + 1}")
                        except socket.error as e:
                            print(f"Socket error during retransmit: {e}")
                    elif attempts >= 3:
                        print(f"Falha ao enviar {msg}: timeout após 3 tentativas")
                        self.sock.sendto(f"NACK {uid}".encode(), addr)
                        del self.pending_acks[uid]
            time.sleep(1)  # Increase sleep to reduce retransmission overhead

    def handle_ack(self, uid):
        with self.socket_lock:
            if uid in self.pending_acks:
                #print(f"ACK recebido para {uid} em protocol")
                del self.pending_acks[uid]
                #print(self.pending_acks)

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
        while True:
            try:
                data, addr = self.sock.recvfrom(2048)
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
                    self.handler.handle(msg, addr)
                else:
                    print(f"Mensagem desconhecida: {msg}")
            except socket.error as e:
                print(f"Socket error in listen_loop: {e}")
                continue

    def send_broadcast(self, msg):
        self.send(msg, (BROADCAST_IP, self.port))

    def print_devices(self):
        now = time.time()
        print(self.devices)
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
