def start_cli(device):
    """Inicia a interface de linha de comando"""
    print(f"Dispositivo {device.name} iniciado na porta {device.port}")
    print("Comandos disponíveis:")
    print("- devices: lista dispositivos ativos")
    print("- talk <nome> <mensagem>: envia mensagem para dispositivo")
    print("- sendfile <nome> <arquivo>: envia arquivo para dispositivo")
    print("- exit: encerra o programa")
    
    while True:
        try:
            cmd = input("> ").strip()
            if not cmd:
                continue
                
            parts = cmd.split()
            command = parts[0].lower()
            
            if command == "devices":
                device.list_devices()
            elif command == "talk":
                if len(parts) < 3:
                    print("Uso: talk <nome> <mensagem>")
                else:
                    target = parts[1]
                    message = ' '.join(parts[2:])
                    device.send_message(target, message)
            elif command == "sendfile":
                if len(parts) < 3:
                    print("Uso: sendfile <nome> <arquivo>")
                else:
                    target = parts[1]
                    filepath = ' '.join(parts[2:])
                    device.send_file(target, filepath)
            elif command == "exit":
                device.stop()
                print("Encerrando...")
                break
            else:
                print("Comando desconhecido")
        except KeyboardInterrupt:
            device.stop()
            print("\nEncerrando...")
            break
        except Exception as e:
            print(f"Erro: {e}")