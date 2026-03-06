import os
import socket
import threading
import uuid
from typing import Dict, Any, Tuple, Optional

from protocol import send_frame, recv_frame

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000

RECV_DIR = "received_files"
os.makedirs(RECV_DIR, exist_ok=True)

UDP_CHUNK = 1200


# ---------------------------
# UDP Receiver (P2P Media)
# ---------------------------
def udp_receiver(udp: socket.socket, stop_evt: threading.Event) -> None:
    """
    Receives media chunks via UDP and reassembles them.
    Each packet format:
      header_line + b"\n" + chunk
    header_line = transfer_id|seq|total|filename
    """
    udp.settimeout(0.5)
    transfers: Dict[str, Dict[str, Any]] = {}

    while not stop_evt.is_set():
        try:
            data, src = udp.recvfrom(65535)
        except socket.timeout:
            continue
        except Exception:
            break

        try:
            header, chunk = data.split(b"\n", 1)
            tid, seq_s, total_s, filename = header.decode("utf-8").split("|", 3)
            seq = int(seq_s)
            total = int(total_s)
        except Exception:
            continue

        t = transfers.setdefault(
            tid,
            {"total": total, "filename": filename, "chunks": {}, "from": src}
        )

        # store chunk
        t["chunks"][seq] = chunk

        # complete?
        if len(t["chunks"]) == t["total"]:
            ordered = b"".join(t["chunks"][i] for i in range(total))
            safe_name = os.path.basename(t["filename"])
            out_path = os.path.join(RECV_DIR, f"{tid}_{safe_name}")
            with open(out_path, "wb") as f:
                f.write(ordered)
            print(f"\n [UDP] File received and saved: {out_path}\n")
            transfers.pop(tid, None)


# ---------------------------
# TCP Listener (Incoming msgs)
# ---------------------------
class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_peer: Optional[Tuple[str, int]] = None
        self.latest_peer_user: Optional[str] = None

def tcp_listener(sock: socket.socket, stop_evt: threading.Event, shared: SharedState) -> None:
    while not stop_evt.is_set():
        try:
            msg = recv_frame(sock)
        except Exception:
            print("\n [TCP] Disconnected from server.")
            stop_evt.set()
            break

        mtype = msg.get("TYPE")
        if mtype == "CONTROL":
            status = msg.get("CONTROL")
            message = msg.get("MESSAGE")
            req_seq = msg.get("REQ_SEQ")
            print(f"\n [CONTROL:{status}] {message}" + (f" (req_seq={req_seq})" if req_seq is not None else ""))

            if "PEER_IP" in msg and "PEER_PORT" in msg:
                ip = msg["PEER_IP"]
                port = msg["PEER_PORT"]
                # store for file send convenience
                with shared.lock:
                    shared.latest_peer = (ip, int(port))
                print(f"Peer endpoint received: {ip}:{port} (used for UDP file transfer)")

        elif mtype == "DATA" and msg.get("DATA") == "TEXT":
            print(f"\n [{msg.get('FROM')} → {msg.get('TO')}] {msg.get('BODY')}")

        else:
            print(f"\n[INFO] {msg}")


# ---------------------------
# UDP File Sender
# ---------------------------
def send_udp_file(udp: socket.socket, peer: Tuple[str, int], filepath: str) -> None:
    if not os.path.isfile(filepath):
        print("File not found.")
        return

    tid = str(uuid.uuid4())[:8]
    filename = os.path.basename(filepath)

    with open(filepath, "rb") as f:
        content = f.read()

    chunks = [content[i:i + UDP_CHUNK] for i in range(0, len(content), UDP_CHUNK)]
    total = len(chunks)

    print(f"\n Sending '{filename}' to {peer[0]}:{peer[1]} via UDP ({total} chunks)...")

    for i, ch in enumerate(chunks):
        header = f"{tid}|{i}|{total}|{filename}\n".encode("utf-8")
        udp.sendto(header + ch, peer)

    print("UDP send complete (prototype: no retransmissions).\n")


# ---------------------------
# Menu UI Helpers
# ---------------------------
def print_menu() -> None:
    print("\n" + "=" * 50)
    print("CHAT CLIENT MENU")
    print("=" * 50)
    print("1) Send Direct Message (DM)")
    print("2) Join Group")
    print("3) Leave Group")
    print("4) Send Group Message")
    print("5) Send File (UDP P2P)")
    print("6) Quit")
    print("=" * 50)

def ask(prompt: str) -> str:
    return input(f"{prompt}: ").strip()

def safe_int(prompt: str, default: int = 0) -> int:
    s = input(f"{prompt}: ").strip()
    try:
        return int(s)
    except Exception:
        return default


# ---------------------------
# Main
# ---------------------------
def main() -> None:
    username = ask("Enter username")
    password = ask("Enter password (format: 'abcd123')")

    # TCP connect
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((SERVER_HOST, SERVER_PORT))

    # UDP setup (OS assigns port)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("0.0.0.0", 0))
    udp_port = udp.getsockname()[1]

    stop_evt = threading.Event()
    shared = SharedState()

    # Start threads
    threading.Thread(target=udp_receiver, args=(udp, stop_evt), daemon=True).start()
    threading.Thread(target=tcp_listener, args=(sock, stop_evt, shared), daemon=True).start()

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

    print(f"\nLogged in as '{username}'.")
    print(f"UDP receiver listening on port {udp_port}. Received files saved in ./{RECV_DIR}")

    # Menu loop
    while not stop_evt.is_set():
        print_menu()
        choice = ask("Choose an option (1-6)")

        if choice == "1":
            to_user = ask("Recipient username")
            message = ask("Message")
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

        elif choice == "2":
            group = ask("Group name")
            send_frame(sock, {
                "TYPE": "COMMAND",
                "COMMAND": "JOIN_GROUP",
                "SENDER_ID": username,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": 0,
                "BODY": {"group": group}
            })
            seq += 1

        elif choice == "3":
            group = ask("Group name")
            send_frame(sock, {
                "TYPE": "COMMAND",
                "COMMAND": "LEAVE_GROUP",
                "SENDER_ID": username,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": 0,
                "BODY": {"group": group}
            })
            seq += 1

        elif choice == "4":
            group = ask("Group name")
            message = ask("Group message")
            send_frame(sock, {
                "TYPE": "DATA",
                "DATA": "TEXT",
                "SENDER_ID": username,
                "RECIPIENT_ID": group,  # server treats this as group if it exists
                "SEQ_NO": seq,
                "CONTENT_LENGTH": len(message.encode("utf-8")),
                "BODY": message
            })
            seq += 1

        elif choice == "5":
            recipient = ask("Send file to which user")
            filepath = ask("File path (e.g., ./test.jpg)")

            # Ask server for peer info
            send_frame(sock, {
                "TYPE": "COMMAND",
                "COMMAND": "PEER_INFO",
                "SENDER_ID": username,
                "SEQ_NO": seq,
                "CONTENT_LENGTH": 0,
                "BODY": {"recipient": recipient}
            })
            seq += 1

            print("\n Waiting for PEER_INFO from server...")
            # Wait a short moment for the listener thread to update shared.latest_peer
            # (simple approach for prototype)
            peer: Optional[Tuple[str, int]] = None
            for _ in range(30):  # ~3 seconds
                with shared.lock:
                    peer = shared.latest_peer
                if peer:
                    break
                stop_evt.wait(0.1)

            if not peer:
                print("Did not receive peer info. Make sure the recipient is logged in and registered UDP.")
                continue

            send_udp_file(udp, peer, filepath)

            # Clear peer so we don't accidentally reuse it later
            with shared.lock:
                shared.latest_peer = None

        elif choice == "6":
            print("Exiting...")
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

        else:
            print("Invalid option. Choose 1–6.")

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