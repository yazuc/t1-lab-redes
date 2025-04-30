import netifaces

def get_broadcast_address():
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs:
            for addr in addrs[netifaces.AF_INET]:
                if "broadcast" in addr:
                    #print(addr["broadcast"])
                    return addr["broadcast"]
    return "255.255.255.255"  # fallback

BROADCAST_IP = get_broadcast_address()

