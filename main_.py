import bagulho
import sys
from bagulho import NetworkDevice
from cli import start_cli

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Uso: python device.py <nome> <porta> [porta_broadcast]")
        sys.exit(1)
        
    name = sys.argv[1]
    port = int(sys.argv[2])
    broadcast_port = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    
    device = NetworkDevice(name, port, broadcast_port=broadcast_port)
    device.start()
    
    try:
        start_cli(device)
    finally:
        device.stop()