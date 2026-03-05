import json
import struct
from typing import Any, Dict

MAX_FRAME = 10 * 1024 * 1024  # 10MB (TCP frames)

def send_frame(sock, obj: Dict[str, Any]) -> None:
    """Send a JSON object as a length-prefixed frame over TCP."""
    data = json.dumps(obj).encode("utf-8")
    if len(data) > MAX_FRAME:
        raise ValueError("Frame too large")
    header = struct.pack("!I", len(data))  # 4-byte length
    sock.sendall(header + data)

def recv_exact(sock, n: int) -> bytes:
    """Receive exactly n bytes or raise ConnectionError."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed")
        buf += chunk
    return buf

def recv_frame(sock) -> Dict[str, Any]:
    """Receive a length-prefixed JSON frame over TCP."""
    raw_len = recv_exact(sock, 4)
    (length,) = struct.unpack("!I", raw_len)
    if length <= 0 or length > MAX_FRAME:
        raise ValueError("Invalid frame length")
    payload = recv_exact(sock, length)
    obj = json.loads(payload.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Invalid JSON frame type")
    return obj