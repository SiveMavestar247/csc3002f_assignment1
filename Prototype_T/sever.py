import socket
import threading
from typing import Dict, Tuple, Optional, Set, Any
from protocol import send_frame, recv_frame

HOST = "0.0.0.0"
PORT = 5000

# --- In-memory state ---
state_lock = threading.Lock()

# username -> conn
sessions: Dict[str, socket.socket] = {}
# conn -> username
reverse_sessions: Dict[socket.socket, str] = {}

# username -> (ip, udp_port)
udp_registry: Dict[str, Tuple[str, int]] = {}

# group_name -> set(usernames)
groups: Dict[str, Set[str]] = {}

# Simple credential store for prototype:
# username -> password
credentials: Dict[str, str] = {
    "alice": "pass",
    "bob": "pass",
    "carol": "pass",
    "dave": "pass",
    "erin": "pass",
}

def control(conn: socket.socket, ok: bool, message: str, req_seq: Optional[int] = None, **extra: Any) -> None:
    payload = {
        "TYPE": "CONTROL",
        "CONTROL": "ACK" if ok else "ERROR",
        "REQ_SEQ": req_seq,
        "MESSAGE": message,
    }
    payload.update(extra)
    send_frame(conn, payload)

def broadcast_group(group: str, sender: str, text: str) -> None:
    with state_lock:
        members = set(groups.get(group, set()))
        targets = [sessions[u] for u in members if u in sessions and u != sender]
    for c in targets:
        send_frame(c, {
            "TYPE": "DATA",
            "DATA": "TEXT",
            "FROM": sender,
            "TO": group,
            "BODY": text
        })

def send_dm(to_user: str, sender: str, text: str) -> bool:
    with state_lock:
        conn = sessions.get(to_user)
    if not conn:
        return False
    send_frame(conn, {
        "TYPE": "DATA",
        "DATA": "TEXT",
        "FROM": sender,
        "TO": to_user,
        "BODY": text
    })
    return True

def ensure_authed(conn: socket.socket) -> Optional[str]:
    with state_lock:
        return reverse_sessions.get(conn)

def handle_command(conn: socket.socket, addr: Tuple[str, int], msg: Dict[str, Any]) -> None:
    cmd = msg.get("COMMAND")
    seq = msg.get("SEQ_NO")

    if cmd == "LOGIN":
        username = msg.get("SENDER_ID")
        body = msg.get("BODY", {})
        password = body.get("password")

        if not username or not isinstance(password, str):
            control(conn, False, "Invalid LOGIN format", seq)
            return

        with state_lock:
            expected = credentials.get(username)
        if expected is None or expected != password:
            control(conn, False, "Authentication failed", seq)
            return

        with state_lock:
            # If already logged in elsewhere, reject
            if username in sessions:
                control(conn, False, "User already logged in", seq)
                return
            sessions[username] = conn
            reverse_sessions[conn] = username

        control(conn, True, "Login successful", seq)
        return

    if cmd == "REGISTER_UDP":
        user = ensure_authed(conn)
        if not user:
            control(conn, False, "Login required", seq)
            return

        udp_port = msg.get("BODY", {}).get("udp_port")
        if not isinstance(udp_port, int) or not (1 <= udp_port <= 65535):
            control(conn, False, "Invalid UDP port", seq)
            return

        ip = addr[0]
        with state_lock:
            udp_registry[user] = (ip, udp_port)

        control(conn, True, f"UDP registered on {ip}:{udp_port}", seq)
        return

    if cmd == "JOIN_GROUP":
        user = ensure_authed(conn)
        if not user:
            control(conn, False, "Login required", seq)
            return

        group = msg.get("BODY", {}).get("group")
        if not isinstance(group, str) or not group:
            control(conn, False, "Invalid group", seq)
            return

        with state_lock:
            groups.setdefault(group, set()).add(user)

        control(conn, True, f"Joined group {group}", seq)
        return

    if cmd == "LEAVE_GROUP":
        user = ensure_authed(conn)
        if not user:
            control(conn, False, "Login required", seq)
            return

        group = msg.get("BODY", {}).get("group")
        if not isinstance(group, str) or not group:
            control(conn, False, "Invalid group", seq)
            return

        with state_lock:
            if group in groups and user in groups[group]:
                groups[group].remove(user)

        control(conn, True, f"Left group {group}", seq)
        return

    if cmd == "PEER_INFO":
        # Request recipient's UDP endpoint for P2P media
        user = ensure_authed(conn)
        if not user:
            control(conn, False, "Login required", seq)
            return

        recipient = msg.get("BODY", {}).get("recipient")
        if not isinstance(recipient, str) or not recipient:
            control(conn, False, "Invalid recipient", seq)
            return

        with state_lock:
            info = udp_registry.get(recipient)

        if not info:
            control(conn, False, f"Recipient {recipient} has no UDP registration", seq)
            return

        ip, port = info
        control(conn, True, "PEER_INFO returned", seq, PEER_IP=ip, PEER_PORT=port)
        return

    if cmd == "LOGOUT":
        user = ensure_authed(conn)
        if not user:
            control(conn, False, "Not logged in", seq)
            return
        disconnect(conn)
        # conn might already be closed after disconnect() in some cases; safe to try
        try:
            control(conn, True, "Logged out", seq)
        except Exception:
            pass
        return

    control(conn, False, f"Unknown command: {cmd}", seq)

def handle_data(conn: socket.socket, msg: Dict[str, Any]) -> None:
    user = ensure_authed(conn)
    seq = msg.get("SEQ_NO")

    if not user:
        control(conn, False, "Unauthorized DATA message: login required", seq)
        return

    dtype = msg.get("DATA")
    if dtype == "TEXT":
        to = msg.get("RECIPIENT_ID")
        body = msg.get("BODY")

        if not isinstance(to, str) or not isinstance(body, str):
            control(conn, False, "Invalid TEXT format", seq)
            return

        # Direct message if recipient is a username, otherwise group name
        with state_lock:
            is_group = to in groups

        if is_group:
            # Enforce membership
            with state_lock:
                members = groups.get(to, set())
            if user not in members:
                control(conn, False, f"Not a member of group {to}", seq)
                return

            broadcast_group(to, user, body)
            control(conn, True, f"Group message delivered to {to}", seq)
        else:
            ok = send_dm(to, user, body)
            if ok:
                control(conn, True, f"DM delivered to {to}", seq)
            else:
                control(conn, False, f"User {to} not online", seq)
        return

    if dtype == "MEDIA_ANNOUNCE":
        # Optional: purely informational for prototype (actual transfer is UDP)
        control(conn, True, "MEDIA_ANNOUNCE received (use UDP transfer)", seq)
        return

    control(conn, False, f"Unknown DATA type: {dtype}", seq)

def disconnect(conn: socket.socket) -> None:
    with state_lock:
        user = reverse_sessions.pop(conn, None)
        if user:
            sessions.pop(user, None)
            udp_registry.pop(user, None)
            # remove from groups
            for g in list(groups.keys()):
                if user in groups[g]:
                    groups[g].remove(user)
                    if not groups[g]:
                        groups.pop(g, None)

def client_thread(conn: socket.socket, addr: Tuple[str, int]) -> None:
    try:
        while True:
            msg = recv_frame(conn)
            mtype = msg.get("TYPE")

            if mtype == "COMMAND":
                handle_command(conn, addr, msg)
            elif mtype == "DATA":
                handle_data(conn, msg)
            else:
                control(conn, False, "Invalid TYPE", msg.get("SEQ_NO"))

    except Exception:
        pass
    finally:
        disconnect(conn)
        try:
            conn.close()
        except Exception:
            pass

def main() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(50)
    print(f"[SERVER] Listening on {HOST}:{PORT}")

    while True:
        conn, addr = server.accept()
        print(f"[SERVER] New connection from {addr}")
        t = threading.Thread(target=client_thread, args=(conn, addr), daemon=True)
        t.start()

if __name__ == "__main__":
    main()