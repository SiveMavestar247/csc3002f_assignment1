"""Core server implementation.

The :class:`ChatServer` defined here is used by the top–level ``server.py``
launcher.  It encapsulates all of the socket setup and per-client
handling logic.
"""

import socket
import threading
from typing import Dict


class ChatServer:
    """Simple TCP chat server that routes messages between connected clients.

    Each client registers with a username when they connect.  The
    ``active_clients`` dictionary maps that username to the corresponding
    socket object so that messages can be forwarded directly.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        # username -> socket
        self.active_clients: Dict[str, socket.socket] = {}
        self._server_socket: socket.socket | None = None

    def start(self):
        """Bind the listening socket and begin accepting connections."""
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen()
        print(f"Server is up and listening on {self.host}:{self.port}...")

        while True:
            client_sock, addr = self._server_socket.accept()
            threading.Thread(
                target=self._handle_client, args=(client_sock,), daemon=True
            ).start()

    def _handle_client(self, client_socket: socket.socket):
        """Internal worker for a single client connection."""

        def broadcast_user_list():
            users = ",".join(self.active_clients.keys())
            msg = f"USERS|{users}"
            for sock in list(self.active_clients.values()):
                try:
                    sock.send(msg.encode("utf-8"))
                except Exception:
                    pass

        try:
            username = client_socket.recv(1024).decode("utf-8")
            self.active_clients[username] = client_socket
            print(f"[+] {username} connected.")
            broadcast_user_list()

            while True:
                data = client_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                target_user, message = data.split("|", 1)
                if target_user in self.active_clients:
                    formatted = f"{username}|{message}"
                    self.active_clients[target_user].send(formatted.encode("utf-8"))
                else:
                    client_socket.send(
                        f"SYSTEM|{target_user} is offline.".encode("utf-8")
                    )
        except Exception as e:
            print(f"[-] Error: {e}")
        finally:
            # cleanup on disconnect
            for user, sock in list(self.active_clients.items()):
                if sock == client_socket:
                    del self.active_clients[user]
                    print(f"[-] {user} disconnected.")
            broadcast_user_list()
            client_socket.close()
