"""Core server implementation.

The :class:`ChatServer` defined here is used by the top-level ``server.py``
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
        # group_name -> list of members
        self.groups: Dict[str, list[str]] = {}
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
            msg = f"USERS|{users}\n"
            for sockets in list(self.active_clients.values()):
                try:
                    sockets[0].send(msg.encode("utf-8"))
                except:
                    pass

        def broadcast_group_list():
            """Broadcast the current groups to all connected users."""
            group_str = ";".join([f"{name}:{','.join(members)}" for name, members in self.groups.items()])
            msg = f"GROUPS|{group_str}\n"
            for username, sockets in list(self.active_clients.items()):
                try:
                    if username in group_str:
                        sockets[0].send(msg.encode("utf-8"))
                except:
                    pass

        try:
            username, client_udp_socket = client_tcp_socket.recv(1024).decode("utf-8").split('|')
            print(f"[+] {username} connected.")
            self.active_clients[username] = (client_tcp_socket, client_udp_socket)
            broadcast_user_list()
            broadcast_group_list()

            while True:
                data = client_tcp_socket.recv(1024).decode("utf-8").strip()
                if not data:
                    break
                
                # Check if it's a group creation request
                if data.startswith("GROUP_CREATE|"):
                    parts = data.split("|", 2)
                    if len(parts) >= 3:
                        group_name = parts[1]
                        members_str = parts[2].strip()
                        members = [m.strip() for m in members_str.split(",")]
                        # Store the group
                        self.groups[group_name] = members
                        print(f"[+] Group '{group_name}' created with members: {members}")
                        # Broadcast updated group list to all users
                        broadcast_group_list()
                    continue
                
                # Check if it's a group message
                if data.startswith("GROUP_MESSAGE|"):
                    parts = data.split("|", 2)
                    if len(parts) >= 3:
                        group_name = parts[1]
                        message = parts[2]
                        
                        # Check if group exists
                        if group_name in self.groups:
                            # Send message to all group members
                            for member in self.groups[group_name]:
                                if member in self.active_clients and member != username:
                                    # Format: GROUP|groupname|sender|message
                                    formatted = f"GROUP|{group_name}|{username}|{message}\n"
                                    self.active_clients[member][0].send(formatted.encode("utf-8"))
                            print(f"[+] Message sent to group '{group_name}' by {username}")
                        else:
                            client_tcp_socket.send(
                                f"SYSTEM|Group '{group_name}' not found.\n".encode("utf-8")
                            )
                    continue
                
                parts = data.split("|", 1)
                if len(parts) < 2:
                    continue
                    
                target_user, message = parts
                if target_user in self.active_clients.keys():
                    formatted = f"{username}|{message}\n"
                    self.active_clients[target_user][0].send(formatted.encode("utf-8"))
                else:
                    client_tcp_socket.send(
                        f"SYSTEM|{target_user} is offline.\n".encode("utf-8")
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
            broadcast_group_list()
            client_tcp_socket.close()