import os
import socket
import threading
from typing import Any, Dict, Tuple
import uuid

class ChatClient:
    def __init__(self, server_host='127.0.0.1', server_port=5555):
        self.server_host = "196.24.149.74"
        self.server_port = server_port
        self.tcp_socket = None
        self.udp_socket = None
        
        # Callbacks (functions provided by the GUI to update the screen)
        self.on_message_received = None
        self.on_connection_error = None
        self.on_user_list_updated = None
        self.on_group_list_updated = None
        self.on_file_received = None  # (sender, filename, filepath)
        self.on_file_sent = None      # (target_user, filename)
        
        # Track groups locally (group_name -> list of members)
        self.groups: Dict[str, list[str]] = {}
        
        # Track peer addresses to their usernames for file transfers
        self.peer_addresses: Dict[Tuple[str, int], str] = {}

    def connect(self, username: str, message_callback, error_callback, user_list_callback=None, group_list_callback=None) -> bool:
        """
        Connects to the server and starts listening in the background. <p>
        Return True on successful connection, False otherwise
        """
        self.on_message_received = message_callback
        self.on_connection_error = error_callback
        self.on_user_list_updated = user_list_callback
        self.on_group_list_updated = group_list_callback
        self.username = username
        
        try:
            # Create UDP socket for sending and receiving media from peers
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            def get_local_ip():
                """Finds the actual local routing IPv4 address of this computer."""
                try:
                    # Create a temporary UDP socket
                    dummy_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    
                    # Connect to an external IP (Google DNS). 
                    # Port 80 is just a placeholder; no actual data is sent.
                    dummy_socket.connect(("8.8.8.8", 80))
                    
                    # Read the IP address the OS assigned to this socket
                    local_ip = dummy_socket.getsockname()[0]
                    
                    # Close the socket so we don't leave trash in the system
                    dummy_socket.close()
                    
                    return local_ip
                except Exception:
                    # Fallback just in case the computer has absolutely no network connection
                    return "127.0.0.1"
            
            my_IPv4_addr = get_local_ip()
            self.udp_socket.bind((my_IPv4_addr, 0))    # OS assigns port
            udp_host, udp_port = self.udp_socket.getsockname()
            self.udp_socket_addr: str = f"{udp_host}:{udp_port}"
            
            # Create TCP socket for communicating with server
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.server_host, self.server_port))
            self.tcp_socket_addr: str = self.tcp_socket.getsockname()

            self.tcp_socket.send((f"{self.username}|{self.udp_socket_addr}").encode('utf-8'))  # Send username & UDP socket addr to register with server
            
            # Start the background listening threads
            threading.Thread(target=self.receive_media, daemon= True).start()
            threading.Thread(target=self.receive_messages, daemon=True).start()
            print(f"Connected to server {self.server_host}:{self.server_port}.")
            print(f"Listening for text messages from server on TCP socket {self.tcp_socket_addr}...")
            print(f"Listening for media transfers from peers on UDP socket {self.udp_socket_addr}...")
            return True # Connection successful
            
        except Exception as e:
            if self.on_connection_error:
                self.on_connection_error(str(e))
            return False

    def send_message(self, target, message):
        """Sends a formatted message to the server via a TCP socket.
        
        If target is a group, sends GROUP_MESSAGE format.
        If target is a user, sends regular user message format.
        """
        if self.tcp_socket:
            try:
                # Check if target is a group
                if target in self.groups:
                    # Send as group message
                    network_payload = f"GROUP_MESSAGE|{target}|{message}\n"
                else:
                    # Send as individual message
                    network_payload = f"{target}|{message}\n"
                self.tcp_socket.send(network_payload.encode('utf-8'))
            except Exception as e:
                print(f"Failed to send message: {e}")
    
    def create_group(self, group_name: str, members: list[str]):
        """Send a group creation request to the server"""
        if self.tcp_socket:
            try:
                members_str = ",".join(members)
                network_payload = f"GROUP_CREATE|{group_name}|{members_str}"
                self.tcp_socket.send(network_payload.encode('utf-8'))
            except Exception as e:
                print(f"Failed to create group: {e}")

    def receive_messages(self):
        """Constantly listens for incoming messages."""
        buffer = ""
        while True:
            try:
                data = self.tcp_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                buffer += data
                
                # Process complete messages (delimited by newline)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    line = line.strip()
                    
                    if not line:
                        continue
                    
                    # Split "Sender|Message"
                    if '|' not in line:
                        continue
                        
                    sender, msg = line.split('|', 1)
                    
                    # Check if it's a group message
                    if sender == "GROUP":
                        # Format: GROUP|groupname|sender|message
                        parts = msg.split('|', 2)
                        if len(parts) >= 3:
                            group_name = parts[0]
                            actual_sender = parts[1]
                            actual_message = parts[2]
                            # Call message received with group info
                            if self.on_message_received:
                                self.on_message_received(actual_sender, actual_message, group=group_name)
                        continue
                    
                    # Check if it's a user list update
                    if sender == "USERS":
                        if self.on_user_list_updated:
                            users = msg.split(',')
                            self.users_dict: Dict[str, Tuple[str, int]] = {}
                            for user in users:
                                if '(' not in user or ')' not in user:
                                    continue
                                username, rem = user.split("(", 1)
                                host, port = rem.rstrip(")").split(":")
                                try:
                                    peer_addr = (host, int(port))
                                    self.users_dict[username] = peer_addr
                                    # Track the mapping from address to username for incoming file transfers
                                    self.peer_addresses[peer_addr] = username
                                except ValueError:
                                    continue
                            self.on_user_list_updated(self.users_dict.keys())
                    # Check if it's a group list update
                    elif sender == "GROUPS":
                        if self.on_group_list_updated:
                            groups = {}
                            # Parse format: groupname:user1,user2;groupname2:user3,user4
                            if msg.strip():
                                for group_entry in msg.split(';'):
                                    if ':' in group_entry:
                                        group_name, members_str = group_entry.split(':', 1)
                                        members = [m.strip() for m in members_str.split(',') if m.strip()]
                                        groups[group_name.strip()] = members
                            # Update local groups dict
                            self.groups = groups
                            self.on_group_list_updated(groups)
                    else:
                        # Regular message
                        if self.on_message_received:
                            self.on_message_received(sender, msg)
                    
            except Exception as e:
                print(f"Disconnected from server: {e}")
                break    
    
    def send_media(self, filepath: str, target: str):
        """Send formatted media files in chunks to a peer or group via UDP socket.
        
        Args:
            filepath: Path to the file to send
            target: Target user or group name
        """
        if not os.path.isfile(filepath):
            print("File not found.")
            return

        tid = str(uuid.uuid4())[:8]
        filename = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            content = f.read()
            
        UDP_CHUNK = 1200
        chunks = [content[i:i + UDP_CHUNK] for i in range(0, len(content), UDP_CHUNK)]
        total = len(chunks)

        # Check if target is a group
        if target in self.groups:
            # Send to all group members
            members = self.groups[target]
            group_mode = True
            print(f"\n Sending '{filename}' to group '{target}' ({len(members)-1} members via UDP ({total} chunks)...")
        else:
            # Send to single user
            members = [target]
            group_mode = False
            print(f"\n Sending '{filename}' to {target} via UDP ({total} chunks)...")

        # Send to each member
        for member in members:
            if member not in self.users_dict or member == self.username:
                continue
                
            peer: Tuple[str, int] = self.users_dict[member]
            print(f"  Sending to {member} at {peer[0]}:{peer[1]}...")

            for i, ch in enumerate(chunks):
                header = f"{tid}|{i}|{total}|{filename}\n".encode("utf-8")
                self.udp_socket.sendto(header + ch, peer)

        print("UDP send complete (prototype: no retransmissions).\n")
        
        # Trigger callback to update GUI
        if self.on_file_sent:
            self.on_file_sent(target, filename)  
    
    def receive_media(self):
        """Constantly listens for incoming media."""
        transfers: Dict[str, Dict[str, Any]] = {}
        RECV_DIR = "received_files"
        os.makedirs(RECV_DIR, exist_ok=True)

        while True:
            try:
                data, src = self.udp_socket.recvfrom(65535)
                header, chunk = data.split(b"\n", 1)
                tid, seq_s, total_s, filename = header.decode("utf-8").split("|", 3)
                seq = int(seq_s)
                total = int(total_s)

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
                    
                    # Trigger callback to update GUI
                    sender = self.peer_addresses.get(src, "Unknown")
                    if self.on_file_received:
                        self.on_file_received(sender, safe_name, out_path)
                    
                    transfers.pop(tid, None)
            except Exception as e:
                print(f"Disconnected from server: {e}")
                break    

    def disconnect(self):
        """Closes the network connection safely."""
        if self.tcp_socket or self.udp_socket:
            self.tcp_socket.close()
            self.udp_socket.close()
            print(f"Disconnected from server and closed UDP socket")