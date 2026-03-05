import os
import socket
import threading
import uuid
from typing import Dict, Any, Optional, Tuple

from protocol import send_frame, recv_frame

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

RECV_DIR = "received_files"
os.makedirs(RECV_DIR, exist_ok=True)

# UDP settings
UDP_CHUNK = 1200  # bytes payload chunk (safe-ish under MTU)
UDP_TIMEOUT = 6.0

def make_udp_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("0.0.0.0", 0))  # OS picks port
    return s

def udp_receiver(udp: socket.socket, stop_evt: threading.Event) -> None:
    """
    Receives media chunks via UDP and reassembles them.
    Protocol: each packet = header + chunk
      header is ASCII line terminated with \n:
      transfer_id|seq|total|filename\n
    """
    udp.settimeout(0.5)

    transfers: Dict[str, Dict[str, Any]] = {}
    # transfers[tid] = {"total": int, "filename": str, "chunks": dict[int, bytes], "from": (ip, port)}

    while not stop_evt.is_set():
        try:
            data, src = udp.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception:
            break

        try:
            header, chunk = data.split(b"\n", 1)
            tid_s, seq_s, total_s, filename_b64 = header.decode("utf-8").split("|", 3)
            seq = int(seq_s)
            total = int(total_s)
            filename = filename_b64  # keep simple (no base64) for prototype
        except Exception:
            continue

        t = transfers.setdefault(tid_s, {"total": total, "filename": filename, "chunks": {}, "from": src})
        if t["total"] != total:
            continue

        t["chunks"][seq] = chunk

        # If complete, write to file
        if len(t["chunks"]) == t["total"]:
            ordered = b"".join(t["chunks"][i] for i in range(total))
            safe_name = os.path.basename(t["filename"])
            out_path = os.path.join(RECV_DIR, f"{tid_s}_{safe_name}")
            with open(out_path, "wb") as f:
                f.write(ordered)
            print(f"\n[UDP] Received file saved to: {out_path}\n> ", end="")
            transfers.pop(tid_s, None)

def tcp_listener(sock: socket.socket, stop_evt: threading.Event) -> None:
    while not stop_evt.is_set():
        try:
            msg = recv_frame(sock)
        except Exception:
            print("\n[TCP] Disconnected from server.")
            stop_evt.set()
            break

        t = msg.get("TYPE")
        if t == "CONTROL":
            status = msg.get("CONTROL")
            print(f"\n[CONTROL:{status}] {msg.get('MESSAGE')} {('' if msg.get('REQ_SEQ') is None else f'(req_seq={msg.get('REQ_SEQ')})')}")
            # Print peer info if present
            if "PEER_IP" in msg and "PEER_PORT" in msg:
                print(f"[PEER_INFO] {msg['PEER_IP']}:{msg['PEER_PORT']}")
        elif t == "DATA":
            if msg.get("DATA") == "TEXT":
                print(f"\n[{msg.get('FROM')} → {msg.get('TO')}] {msg.get('BODY')}")
        else:
            print(f"\n[UNKNOWN] {msg}")

        print("> ", end="")

def request_peer_info(sock: socket.socket, seq: int, recipient: str) -> None:
    send_frame(sock, {
        "TYPE": "COMMAND",
        "COMMAND": "PEER_INFO",
        "SENDER_ID": "",  # server uses session identity; field kept for protocol symmetry
        "SEQ_NO": seq,
        "CONTENT_LENGTH": 0,
        "BODY": {"recipient": recipient}
    })

def send_udp_file(udp: socket.socket, peer: Tuple[str, int], filepath: str) -> None:
    if not os.path.isfile(filepath):
        print("[UDP] File not found.")
        return

    tid = str(uuid.uuid4())[:8]
    filename = os.path.basename(filepath)

    with open(filepath, "rb") as f:
        content = f.read()

    chunks = [content[i:i+UDP_CHUNK] for i in range(0, len(content), UDP_CHUNK)]
    total = len(chunks)

    print(f"[UDP] Sending {filename} to {peer[0]}:{peer[1]} as transfer {tid} in {total} chunks...")

    for i, ch in enumerate(chunks):
        header = f"{tid}|{i}|{total}|{filename}\n".encode("utf-8")
        udp.sendto(header + ch, peer)

    print("[UDP] Send complete (prototype: no retransmissions).")

def main() -> None:
    username = input("Username (e.g., alice): ").strip()
    password = input("Password (for prototype, try 'pass'): ").strip()

    # TCP connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    # UDP setup
    udp = make_udp_socket()
    udp_port = udp.getsockname()[1]

    stop_evt = threading.Event()

    # Start UDP receive thread
    t_udp = threading.Thread(target=udp_receiver, args=(udp, stop_evt), daemon=True)
    t_udp.start()

    # Start TCP listener thread
    t_tcp = threading.Thread(target=tcp_listener, args=(sock, stop_evt), daemon=True)
    t_tcp.start()

    seq = 0

    # LOGIN
    send_frame(sock, {
        "TYPE": "COMMAND",
        "COMMAND": "LOGIN",
        "SENDER_ID": username,
        "SEQ_NO": seq,
        "CONTENT_LENGTH": 0,
        "BODY": {"password": password}
    })
    seq += 1

    # REGISTER UDP
    send_frame(sock, {
        "TYPE": "COMMAND",
        "COMMAND": "REGISTER_UDP",
        "SENDER_ID": username,
        "SEQ_NO": seq,
        "CONTENT_LENGTH": 0,
        "BODY": {"udp_port": udp_port}
    })
    seq += 1

    print("\nCommands:")
    print("  /dm <user> <message>         send direct message")
    print("  /join <group>                join group")
    print("  /leave <group>               leave group")
    print("  /group <group> <message>     send message to group")
    print("  /sendfile <user> <path>      send file to user via UDP (P2P)")
    print("  /quit                        exit")
    print(f"\n[UDP] Listening on port {udp_port}. Received files go to ./{RECV_DIR}\n")

    while not stop_evt.is_set():
        try:
            cmd = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            cmd = "/quit"

        if not cmd:
            continue

        if cmd == "/quit":
            try:
                send_frame(sock, {
                    "TYPE": "COMMAND",
                    "COMMAND": "LOGOUT",
                    "SENDER_ID": username,
                    "SEQ_NO": seq,
                    "CONTENT_LENGTH": 0,
                    "BODY": {}
                })
            except Exception:
                pass
            stop_evt.set()
            break

        if cmd.startswith("/join "):
            group = cmd.split(" ", 1)[1].strip()
            send_frame(sock, {
                "TYPE": "COMMAND",
                "COMMAND": "JOIN_GROUP",
                "SENDER_ID": username,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": 0,
                "BODY": {"group": group}
            })
            seq += 1
            continue

        if cmd.startswith("/leave "):
            group = cmd.split(" ", 1)[1].strip()
            send_frame(sock, {
                "TYPE": "COMMAND",
                "COMMAND": "LEAVE_GROUP",
                "SENDER_ID": username,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": 0,
                "BODY": {"group": group}
            })
            seq += 1
            continue

        if cmd.startswith("/dm "):
            # /dm user message...
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /dm <user> <message>")
                continue
            to_user, message = parts[1], parts[2]
            send_frame(sock, {
                "TYPE": "DATA",
                "DATA": "TEXT",
                "SENDER_ID": username,
                "RECIPIENT_ID": to_user,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": len(message.encode("utf-8")),
                "BODY": message
            })
            seq += 1
            continue

        if cmd.startswith("/group "):
            # /group group message...
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /group <group> <message>")
                continue
            group, message = parts[1], parts[2]
            send_frame(sock, {
                "TYPE": "DATA",
                "DATA": "TEXT",
                "SENDER_ID": username,
                "RECIPIENT_ID": group,  # group name used in place of recipient
                "SEQ_NO": seq,
                "CONTENT_LENGTH": len(message.encode("utf-8")),
                "BODY": message
            })
            seq += 1
            continue

        if cmd.startswith("/sendfile "):
            # /sendfile user path
            parts = cmd.split(" ", 2)
            if len(parts) < 3:
                print("Usage: /sendfile <user> <path>")
                continue
            recipient, path = parts[1], parts[2]

            # Ask server for peer info
            request_peer_info(sock, seq, recipient)
            seq += 1

            # For prototype simplicity: user will manually copy the printed PEER_INFO
            # Better: store PEER_INFO from CONTROL response and auto-send.
            print("When you see [PEER_INFO] ip:port, type: /udpgo <ip> <port> <path>")
            continue

        if cmd.startswith("/udpgo "):
            # /udpgo ip port path
            parts = cmd.split(" ", 3)
            if len(parts) < 4:
                print("Usage: /udpgo <ip> <port> <path>")
                continue
            ip = parts[1].strip()
            port = int(parts[2].strip())
            path = parts[3].strip()
            send_udp_file(udp, (ip, port), path)
            continue

        print("Unknown command. Try /dm, /join, /group, /sendfile, /quit.")

    try:
        sock.close()
    except Exception:
        pass
    try:
        udp.close()
    except Exception:
        pass

if __name__ == "__main__":
    main()