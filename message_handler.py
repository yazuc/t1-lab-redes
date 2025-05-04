import time
from utils import hash_file

class MessageHandler:
    def __init__(self, protocol):
        self.protocol = protocol
        self.received_ids = set()

    def handle(self, msg, addr):

        parts = msg.strip().split(" ", 2)
        if len(parts) < 2: return
        cmd, arg1 = parts[0], parts[1]   
        
        # Verificação de duplicata
        if cmd not in ("HEARTBEAT",) and arg1 in self.received_ids:
            return
        if cmd != "HEARTBEAT":
            self.received_ids.add(arg1)

        if cmd == "HEARTBEAT":
            name = arg1
            self.protocol.devices[name] = (addr[0], addr[1], time.time())
        elif cmd == "TALK":
            uid, content = arg1, parts[2]
            print(f"Mensagem recebida de {addr[0]}: [{uid}] {content}")            
            self.protocol.send(f"ACK {uid}", addr)
        elif cmd == "FILE":
            self.protocol.file_manager.handle_file_request(msg.split(" ", 1), addr)
        elif cmd == "CHUNK":
            self.protocol.file_manager.handle_chunk(msg.split(" ", 1), addr)
        elif cmd == "END":
            self.protocol.file_manager.handle_end(msg.split(" ", 1), addr)
        elif cmd == "ACK":
            self.protocol.handle_ack(arg1)
        elif cmd == "NACK":
            print(f"NACK recebido para {arg1}: {parts[2]}")
            self.protocol.retransmit(arg1)
