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

    def _broadcast_user_list(self):
        """Broadcast the list of online users to all connected clients."""
        users: Tuple[str] = ()
        for user in list(self.active_clients.keys()):
            users += (f"{user}({self.active_clients[user][1]})",)
        users_str = ",".join(users)
        msg = f"USERS|{users_str}\n"
        for sockets in list(self.active_clients.values()):
            try:
                sockets[0].send(msg.encode("utf-8"))
            except:
                pass

    def _broadcast_group_list(self):
        """Broadcast groups to each user - but only the groups they are a member of."""
        for username, sockets in list(self.active_clients.items()):
            try:
                # Find groups where this user is a member
                user_groups = {name: members for name, members in self.groups.items() 
                               if username in members}
                
                # Only send groups if user is in any groups
                if user_groups:
                    group_str = ";".join([f"{name}:{','.join(members)}" for name, members in user_groups.items()])
                    msg = f"GROUPS|{group_str}\n"
                else:
                    msg = "GROUPS|\n"  # Empty groups list
                
                sockets[0].send(msg.encode("utf-8"))
            except:
                pass

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
        is_disconnecting = False  # Track intentional disconnections

        try:
            username, client_udp_socket = client_tcp_socket.recv(1024).decode("utf-8").split('|')
            print(f"[+] {username} connected.")
            self.active_clients[username] = (client_tcp_socket, client_udp_socket)
            self._broadcast_user_list()
            self._broadcast_group_list()

            buffer = ""
            while True:
                chunk = client_tcp_socket.recv(1024).decode("utf-8")
                if not chunk:
                    break
                
                buffer += chunk
                
                # Process complete messages (lines ending with \n)
                while "\n" in buffer:
                    data, buffer = buffer.split("\n", 1)
                    data = data.strip()
                    if not data:
                        continue
                    
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
                            self._broadcast_group_list()
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
                    
                    # Check if it's a group modification request
                    if data.startswith("GROUP_MODIFY|"):
                        parts = data.split("|", 3)
                        if len(parts) >= 3:
                            old_group_name = parts[1]
                            new_group_name = parts[2]
                            users_to_add_str = parts[3] if len(parts) > 3 else ""
                            
                            # Check if group exists
                            if old_group_name in self.groups:
                                # Only allow modification by group members
                                if username in self.groups[old_group_name]:
                                    # Add new users
                                    users_to_add = [u.strip() for u in users_to_add_str.split(",") if u.strip()]
                                    current_members = self.groups[old_group_name]
                                    
                                    # Add only users not already in group
                                    for user in users_to_add:
                                        if user not in current_members:
                                            current_members.append(user)
                                    
                                    # Rename group if name changed
                                    if new_group_name != old_group_name:
                                        self.groups[new_group_name] = self.groups.pop(old_group_name)
                                        print(f"[+] Group '{old_group_name}' renamed to '{new_group_name}' by {username}")
                                    else:
                                        print(f"[+] Group '{old_group_name}' modified: added {users_to_add} by {username}")
                                    
                                    # Broadcast updated group list
                                    self._broadcast_group_list()
                                else:
                                    client_tcp_socket.send(
                                        f"SYSTEM|You are not a member of this group.\n".encode("utf-8")
                                    )
                            else:
                                client_tcp_socket.send(
                                    f"SYSTEM|Group '{old_group_name}' not found.\n".encode("utf-8")
                                )
                        continue
                    
                    # Check if it's a group leave request
                    if data.startswith("GROUP_LEAVE|"):
                        parts = data.split("|", 1)
                        if len(parts) >= 2:
                            group_name = parts[1]
                            
                            if group_name in self.groups:
                                if username in self.groups[group_name]:
                                    self.groups[group_name].remove(username)
                                    print(f"[+] {username} left group '{group_name}'")
                                    
                                    # If group is empty, remove it
                                    if not self.groups[group_name]:
                                        del self.groups[group_name]
                                        print(f"[+] Group '{group_name}' is now empty and has been removed")
                                    
                                    # Broadcast updated group list
                                    self._broadcast_group_list()
                                else:
                                    client_tcp_socket.send(
                                        f"SYSTEM|You are not a member of this group.\n".encode("utf-8")
                                    )
                            else:
                                client_tcp_socket.send(
                                    f"SYSTEM|Group '{group_name}' not found.\n".encode("utf-8")
                                )
                        continue
                    
                    # Regular user message
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
            # Only print exception if it's not an intentional disconnect
            if not is_disconnecting:
                print(f"[-] Error: {e}")
        finally:
            is_disconnecting = True  # Mark disconnection as intentional for finally block
            # cleanup on disconnect
            for user, sock in list(self.active_clients.items()):
                if sock[0] == client_tcp_socket:
                    del self.active_clients[user]
                    print(f"[-] {user} disconnected.")
            self._broadcast_user_list()
            self._broadcast_group_list()
            try:
                client_tcp_socket.close()
            except:
                pass