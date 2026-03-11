"""Core server implementation.

The :class:`ChatServer` defined here is used by the top–level ``server.py``
launcher.  It encapsulates all of the socket setup and per-client
handling logic.
"""

import socket
import threading
from typing import Dict, Tuple


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
        self.active_clients: Dict[str, Tuple[socket.socket, socket.socket]] = {}
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

    def _handle_client(self, client_tcp_socket: socket.socket):
        """Internal worker for a single client connection."""

        def broadcast_user_list():
            users : Tuple[str] = ()
            for user in list(self.active_clients.keys()):
                users += (f"{user}({self.active_clients[user][1]})",)
            users : str= ",".join(users)
            msg = f"USERS|{users}"
            for sockets in list(self.active_clients.values()):
                sockets[0].send(msg.encode("utf-8"))

        try:
            username, client_udp_socket = client_tcp_socket.recv(1024).decode("utf-8").split('|')
            print(f"[+] {username} connected.")
            self.active_clients[username] = (client_tcp_socket, client_udp_socket)
            broadcast_user_list()

            while True:
                data = client_tcp_socket.recv(1024).decode("utf-8")
                if not data:
                    break
                target_user, message = data.split("|", 1)
                if target_user in self.active_clients.keys():
                    formatted = f"{username}|{message}"
                    self.active_clients[target_user][0].send(formatted.encode("utf-8"))
                else:
                    client_tcp_socket.send(
                        f"SYSTEM|{target_user} is offline.".encode("utf-8")
                    )
        except Exception as e:
            print(f"[-] Error: {e}")
        finally:
            # cleanup on disconnect
            for user, sock in list(self.active_clients.items()):
                if sock[0] == client_tcp_socket:
                    del self.active_clients[user]
                    print(f"[-] {user} disconnected.")
            broadcast_user_list()
            client_tcp_socket.close()