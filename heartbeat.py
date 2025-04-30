import time
import threading

class HeartbeatSender:
    def __init__(self, protocol, interval=5):
        self.protocol = protocol
        self.interval = interval
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        while self.running:
            self.protocol.send_broadcast(f"HEARTBEAT {self.protocol.name}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False