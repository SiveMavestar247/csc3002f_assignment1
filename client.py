import os
import socket
import threading
from typing import Any, Dict, Tuple
import uuid

class ChatClient:
    def __init__(self, server_host='127.0.0.1', server_port=5555):
        self.server_host = server_host
        self.server_port = server_port
        self.tcp_socket = None
        self.udp_socket = None
        
        # Callbacks (functions provided by the GUI to update the screen)
        self.on_message_received = None
        self.on_connection_error = None
        self.on_user_list_updated = None
        self.on_file_received = None  # (sender, filename, filepath)
        self.on_file_sent = None      # (target_user, filename)
        
        # Track peer addresses to their usernames for file transfers
        self.peer_addresses: Dict[Tuple[str, int], str] = {}

    def connect(self, username: str, message_callback, error_callback, user_list_callback=None) -> bool:
        """
        Connects to the server and starts listening in the background. <p>
        Return True on successful connection, False otherwise
        """
        self.on_message_received = message_callback
        self.on_connection_error = error_callback
        self.on_user_list_updated = user_list_callback
        
        try:
            # Create UDP socket for sending and receiving media from peers
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.bind(("127.0.0.1", 0))    # OS assigns port on localhost
            udp_host, udp_port = self.udp_socket.getsockname()
            self.udp_socket_addr: str = f"{udp_host}:{udp_port}"
            
            # Create TCP socket for communicating with server
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.server_host, self.server_port))
            self.tcp_socket_addr: str = self.tcp_socket.getsockname()

            self.tcp_socket.send((f"{username}|{self.udp_socket_addr}").encode('utf-8'))  # Send username & UDP socket addr to register with server
            
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

    def send_message(self, target_user, message):
        """Sends a formatted message to the server via a TCP socket"""
        if self.tcp_socket:
            try:
                network_payload = f"{target_user}|{message}"
                self.tcp_socket.send(network_payload.encode('utf-8'))
            except Exception as e:
                print(f"Failed to send message: {e}")

    def receive_messages(self):
        """Constantly listens for incoming messages."""
        while True:
            try:
                data = self.tcp_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                # Split "Sender|Message"
                sender, msg = data.split('|', 1)
                
                # Check if it's a user list update
                if sender == "USERS":
                    if self.on_user_list_updated:
                        users = msg.split(',')
                        self.users_dict: Dict[str, Tuple[str, int]] = {}
                        for user in users:
                            username, rem = user.split("(")
                            host, port = rem.rstrip(")").split(":")
                            peer_addr = (host, int(port))
                            self.users_dict[username] = peer_addr
                            # Track the mapping from address to username for incoming file transfers
                            self.peer_addresses[peer_addr] = username
                        self.on_user_list_updated(self.users_dict.keys())
                else:
                    # Trigger the GUI function to update the screen
                    if self.on_message_received:
                        self.on_message_received(sender, msg)
                    
            except Exception as e:
                print(f"Disconnected from server: {e}")
                break    
    
    def send_media(self, filepath: str, target_user: str):
        """Send formatted media files in chunks to a peer via a UDP socket"""
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

        peer : Tuple[str, int] = self.users_dict[target_user]
        print(f"\n Sending '{filename}' to {peer[0]}:{peer[1]} via UDP ({total} chunks)...")

        for i, ch in enumerate(chunks):
            header = f"{tid}|{i}|{total}|{filename}\n".encode("utf-8")
            self.udp_socket.sendto(header +  ch, peer)

        print("UDP send complete (prototype: no retransmissions).\n")
        
        # Trigger callback to update GUI
        if self.on_file_sent:
            self.on_file_sent(target_user, filename)  
    
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