import socket
import threading
import time
import hashlib
import os
import base64
from collections import defaultdict

class NetworkDevice:
    def __init__(self, name, port, broadcast_addr='255.255.255.255', broadcast_port=5000):
        self.name = name
        self.port = port
        self.broadcast_addr = broadcast_addr
        self.broadcast_port = broadcast_port
        
        # Lista de dispositivos conhecidos {nome: (ip, port, last_seen)}
        self.known_devices = {}
        
        # Socket para comunicação
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.bind(('0.0.0.0', port))
        
        # Dados para transferência de arquivos
        self.file_transfers = {}
        self.pending_acks = {}
        
        # Threads
        self.receive_thread = threading.Thread(target=self.receive_messages)
        self.heartbeat_thread = threading.Thread(target=self.send_heartbeats)
        self.cleanup_thread = threading.Thread(target=self.cleanup_devices)
        
        self.running = True
        
    def start(self):
        """Inicia o dispositivo e todas as threads necessárias"""
        self.receive_thread.start()
        self.heartbeat_thread.start()
        self.cleanup_thread.start()
        self.send_heartbeat()  # Envia o primeiro heartbeat
        
    def stop(self):
        """Para o dispositivo e todas as threads"""
        self.running = False
        self.receive_thread.join()
        self.heartbeat_thread.join()
        self.cleanup_thread.join()
        self.sock.close()
        
    def send_heartbeats(self):
        """Thread que envia heartbeats periodicamente"""
        while self.running:
            time.sleep(5)
            self.send_heartbeat()
            
    def send_heartbeat(self):
        """Envia uma mensagem HEARTBEAT para a rede"""
        message = f"HEARTBEAT {self.name}"
        self.sock.sendto(message.encode(), (self.broadcast_addr, self.broadcast_port))
        
    def cleanup_devices(self):
        """Thread que remove dispositivos inativos"""
        while self.running:
            time.sleep(1)
            current_time = time.time()
            to_remove = []
            
            for name, (ip, port, last_seen) in self.known_devices.items():
                if current_time - last_seen > 10:  # 10 segundos de inatividade
                    to_remove.append(name)
            
            for name in to_remove:
                del self.known_devices[name]
                print(f"Dispositivo {name} removido por inatividade")
                
    def receive_messages(self):
        """Thread principal que recebe e processa mensagens"""
        while self.running:
            try:
                data, addr = self.sock.recvfrom(1024)
                message = data.decode()
                self.process_message(message, addr)
            except Exception as e:
                if self.running:
                    print(f"Erro ao receber mensagem: {e}")
                    
    def process_message(self, message, addr):
        """Processa uma mensagem recebida"""
        parts = message.split()
        if not parts:
            return
            
        msg_type = parts[0]
        
        if msg_type == "HEARTBEAT":
            self.handle_heartbeat(parts[1:], addr)
        elif msg_type == "TALK":
            self.handle_talk(parts[1:], addr)
        elif msg_type == "ACK":
            self.handle_ack(parts[1:], addr)
        elif msg_type == "NACK":
            self.handle_nack(parts[1:], addr)
        elif msg_type == "FILE":
            self.handle_file(parts[1:], addr)
        elif msg_type == "CHUNK":
            self.handle_chunk(parts[1:], addr)
        elif msg_type == "END":
            self.handle_end(parts[1:], addr)
            
    def handle_heartbeat(self, parts, addr):
        """Processa mensagem HEARTBEAT"""
        if len(parts) < 1:
            return
            
        name = parts[0]
        self.known_devices[name] = (addr[0], addr[1], time.time())
        print(f"Dispositivo {name} ativo em {addr[0]}:{addr[1]}")
        
    def handle_talk(self, parts, addr):
        """Processa mensagem TALK"""
        if len(parts) < 2:
            return
            
        msg_id = parts[0]
        message = ' '.join(parts[1:])
        
        print(f"Mensagem recebida de {addr[0]}:{addr[1]}: {message}")
        self.send_ack(msg_id, addr)
        
    def send_ack(self, msg_id, addr):
        """Envia confirmação ACK"""
        ack_msg = f"ACK {msg_id}"
        self.sock.sendto(ack_msg.encode(), addr)
        
    def handle_ack(self, parts, addr):
        """Processa mensagem ACK"""
        if len(parts) < 1:
            return
            
        msg_id = parts[0]
        if msg_id in self.pending_acks:
            self.pending_acks[msg_id].set()
            
    def handle_nack(self, parts, addr):
        """Processa mensagem NACK"""
        if len(parts) < 2:
            return
            
        msg_id = parts[0]
        reason = ' '.join(parts[1:])
        
        print(f"Recebido NACK para mensagem {msg_id}: {reason}")
        if msg_id in self.pending_acks:
            self.pending_acks[msg_id].set()
            
    def handle_file(self, parts, addr):
        """Processa mensagem FILE (início de transferência)"""
        if len(parts) < 3:
            return
            
        msg_id = parts[0]
        filename = parts[1]
        size = int(parts[2])
        
        print(f"Iniciando recebimento de arquivo {filename} ({size} bytes)")
        self.file_transfers[msg_id] = {
            'filename': filename,
            'size': size,
            'received_chunks': {},
            'total_received': 0
        }
        
        self.send_ack(msg_id, addr)
        
    def handle_chunk(self, parts, addr):
        """Processa mensagem CHUNK (parte de arquivo)"""
        if len(parts) < 3:
            return
            
        msg_id = parts[0]
        seq = int(parts[1])
        data = ' '.join(parts[2:])
        
        if msg_id not in self.file_transfers:
            return
            
        transfer = self.file_transfers[msg_id]
        
        # Ignora chunks duplicados
        if seq in transfer['received_chunks']:
            self.send_ack(msg_id, addr)
            return
            
        # Decodifica os dados (base64)
        try:
            decoded_data = base64.b64decode(data)
        except:
            print(f"Erro ao decodificar chunk {seq} do arquivo {transfer['filename']}")
            return
            
        transfer['received_chunks'][seq] = decoded_data
        transfer['total_received'] += len(decoded_data)
        
        self.send_ack(msg_id, addr)
        
    def handle_end(self, parts, addr):
        """Processa mensagem END (fim de transferência)"""
        if len(parts) < 2:
            return
            
        msg_id = parts[0]
        expected_hash = parts[1]
        
        if msg_id not in self.file_transfers:
            return
            
        transfer = self.file_transfers[msg_id]
        
        # Reconstroi o arquivo na ordem correta
        chunks = sorted(transfer['received_chunks'].items())
        file_data = b''.join([chunk for seq, chunk in chunks])
        
        # Calcula hash
        file_hash = hashlib.sha256(file_data).hexdigest()
        
        if file_hash == expected_hash:
            # Salva o arquivo
            with open(transfer['filename'], 'wb') as f:
                f.write(file_data)
                
            print(f"Arquivo {transfer['filename']} recebido com sucesso!")
            self.send_ack(msg_id, addr)
        else:
            print(f"Erro na transferência do arquivo {transfer['filename']}: hash inválido")
            self.send_nack(msg_id, "hash inválido", addr)
            
        del self.file_transfers[msg_id]
        
    def send_nack(self, msg_id, reason, addr):
        """Envia NACK"""
        nack_msg = f"NACK {msg_id} {reason}"
        self.sock.sendto(nack_msg.encode(), addr)
        
    def list_devices(self):
        """Lista dispositivos conhecidos"""
        current_time = time.time()
        print("\nDispositivos ativos:")
        for name, (ip, port, last_seen) in self.known_devices.items():
            print(f"- {name} ({ip}:{port}), visto há {current_time - last_seen:.1f} segundos")
        print()
        
    def send_message(self, target_name, message):
        """Envia mensagem TALK para um dispositivo"""
        if target_name not in self.known_devices:
            print(f"Dispositivo {target_name} não encontrado")
            return
            
        ip, port, _ = self.known_devices[target_name]
        msg_id = str(int(time.time()))
        
        talk_msg = f"TALK {msg_id} {message}"
        
        # Configura espera por ACK
        ack_event = threading.Event()
        self.pending_acks[msg_id] = ack_event
        
        # Envia a mensagem (com retransmissão se necessário)
        max_retries = 3
        retry_delay = 1
        
        for attempt in range(max_retries):
            self.sock.sendto(talk_msg.encode(), (ip, port))
            
            # Espera pelo ACK
            if ack_event.wait(retry_delay):
                print("Mensagem enviada com sucesso!")
                break
                
            print(f"Tentativa {attempt + 1} de {max_retries}...")
        else:
            print("Falha ao enviar mensagem: tempo esgotado")
            
        del self.pending_acks[msg_id]
        
    def send_file(self, target_name, filepath):
        """Inicia transferência de arquivo para um dispositivo"""
        if target_name not in self.known_devices:
            print(f"Dispositivo {target_name} não encontrado")
            return
            
        if not os.path.exists(filepath):
            print(f"Arquivo {filepath} não encontrado")
            return
            
        ip, port, _ = self.known_devices[target_name]
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        msg_id = str(int(time.time()))
        
        # Envia mensagem FILE
        file_msg = f"FILE {msg_id} {filename} {filesize}"
        ack_event = threading.Event()
        self.pending_acks[msg_id] = ack_event
        
        # Tenta enviar a mensagem FILE
        max_retries = 3
        file_ack_received = False
        
        for attempt in range(max_retries):
            self.sock.sendto(file_msg.encode(), (ip, port))
            
            if ack_event.wait(1):
                file_ack_received = True
                break
                
            print(f"Tentativa {attempt + 1} de {max_retries} para iniciar transferência...")
            
        if not file_ack_received:
            print("Falha ao iniciar transferência: tempo esgotado")
            del self.pending_acks[msg_id]
            return
            
        del self.pending_acks[msg_id]
        
        # Prepara para enviar os chunks
        chunk_size = 1024  # 1KB por chunk
        total_chunks = (filesize + chunk_size - 1) // chunk_size
        sent_chunks = 0
        
        # Calcula hash do arquivo
        file_hash = hashlib.sha256()
        
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                    
                file_hash.update(chunk)
                
        final_hash = file_hash.hexdigest()
        
        # Reinicia o arquivo para enviar os chunks
        with open(filepath, 'rb') as f:
            seq = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                    
                # Codifica em base64 para transmissão
                chunk_b64 = base64.b64encode(chunk).decode()
                chunk_msg = f"CHUNK {msg_id} {seq} {chunk_b64}"
                
                # Envia o chunk com confirmação
                chunk_ack_event = threading.Event()
                self.pending_acks[msg_id] = chunk_ack_event
                
                chunk_sent = False
                for attempt in range(max_retries):
                    self.sock.sendto(chunk_msg.encode(), (ip, port))
                    
                    if chunk_ack_event.wait(1):
                        chunk_sent = True
                        sent_chunks += 1
                        progress = (sent_chunks / total_chunks) * 100
                        print(f"Progresso: {progress:.1f}% ({sent_chunks}/{total_chunks} chunks)")
                        break
                        
                    print(f"Retransmitindo chunk {seq}...")
                    
                if not chunk_sent:
                    print(f"Falha ao enviar chunk {seq}, abortando transferência")
                    del self.pending_acks[msg_id]
                    return
                    
                del self.pending_acks[msg_id]
                seq += 1
                
        # Envia mensagem END
        end_msg = f"END {msg_id} {final_hash}"
        end_ack_event = threading.Event()
        self.pending_acks[msg_id] = end_ack_event
        
        end_sent = False
        for attempt in range(max_retries):
            self.sock.sendto(end_msg.encode(), (ip, port))
            
            if end_ack_event.wait(1):
                end_sent = True
                print("Transferência concluída com sucesso!")
                break
                
            print(f"Tentativa {attempt + 1} de {max_retries} para finalizar transferência...")
            
        if not end_sent:
            print("Falha ao confirmar finalização da transferência")
            
        del self.pending_acks[msg_id]