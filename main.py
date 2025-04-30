import threading
from protocol import UDPProtocol
import utils
import argparse

def main():
    name = input("Digite o nome do dispositivo: ").strip()    
    #parser = argparse.ArgumentParser()
    #parser.add_argument("--name", required=True)
    #parser.add_argument("--port", type=int, required=True)
    #args = parser.parse_args()

    protocol = UDPProtocol(name)

    # Inicia HEARTBEAT
    threading.Thread(target=protocol.heartbeat_loop, daemon=True).start()
    
    # Inicia recebimento de mensagens
    threading.Thread(target=protocol.listen_loop, daemon=True).start()
   
    threading.Thread(target=protocol.clean_devices, daemon=True).start()

    print("Digite comandos: devices | talk <nome> <mensagem> | sendfile <nome> <arquivo>")
    while True:
        cmd = input("> ").strip()
        if cmd == "devices":
            protocol.print_devices()
        elif cmd.startswith("talk "):
            _, nome, *msg = cmd.split()
            protocol.send_talk(nome, " ".join(msg))
        elif cmd.startswith("sendfile "):
            _, nome, arquivo = cmd.split()
            protocol.send_file(nome, arquivo)
        else:
            print("Comando inválido.")

if __name__ == "__main__":
    main()
