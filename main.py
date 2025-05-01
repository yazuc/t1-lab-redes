import threading
from protocol import UDPProtocol
import utils
import argparse

def main():
    #name = input("Digite o nome do dispositivo: ").strip()    
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    #parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    protocol = UDPProtocol(args.name)

    # Inicia HEARTBEAT
    threading.Thread(target=protocol.heartbeat_loop, daemon=True).start()

    # Inicia recebimento de mensagens
    threading.Thread(target=protocol.listen_loop, daemon=True).start()
   
    threading.Thread(target=protocol.clean_devices, daemon=True).start()

    print("Digite comandos: d | t <nome> <mensagem> | s <nome> <arquivo>")
    while True:
        cmd = input("> ").strip()
        if cmd == "d":
            protocol.print_devices()
        elif cmd.startswith("t "):
            _, nome, *msg = cmd.split()
            protocol.send_talk(nome, " ".join(msg))
        elif cmd.startswith("s "):
            _, nome, arquivo = cmd.split()
            protocol.send_file(nome, arquivo)
        else:
            print("Comando inválido.")
            print("> ")

if __name__ == "__main__":
    main()
