import socket
import threading

class ChatClient:
    def __init__(self, host='127.0.0.1', port=5555):
        self.host = host
        self.port = port
        self.client_socket = None
        
        # Callbacks (functions provided by the GUI to update the screen)
        self.on_message_received = None
        self.on_connection_error = None
        self.on_user_list_updated = None

    def connect(self, username, message_callback, error_callback, user_list_callback=None) -> bool:
        """
        Connects to the server and starts listening in the background. <p>
        Return True on successful connection, False otherwise
        """
        self.on_message_received = message_callback
        self.on_connection_error = error_callback
        self.on_user_list_updated = user_list_callback
        
        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((self.host, self.port))
            
            # Send username to register with server
            self.client_socket.send(username.encode('utf-8'))
            
            # Start the background listening thread
            threading.Thread(target=self.receive_messages, daemon=True).start()
            return True # Connection successful
            
        except Exception as e:
            if self.on_connection_error:
                self.on_connection_error(str(e))
            return False

    def send_message(self, target_user, message):
        """Sends a formatted message to the server."""
        if self.client_socket:
            try:
                network_payload = f"{target_user}|{message}"
                self.client_socket.send(network_payload.encode('utf-8'))
            except Exception as e:
                print(f"Failed to send message: {e}")

    def receive_messages(self):
        """Constantly listens for incoming messages."""
        while True:
            try:
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break
                
                # Split "Sender|Message"
                sender, msg = data.split('|', 1)
                
                # Check if it's a user list update
                if sender == "USERS":
                    if self.on_user_list_updated:
                        users = msg.split(',')
                        self.on_user_list_updated(users)
                else:
                    # Trigger the GUI function to update the screen
                    if self.on_message_received:
                        self.on_message_received(sender, msg)
                    
            except Exception as e:
                print(f"Disconnected from server: {e}")
                break    
    
    def receive_media(self):
        """Constantly listens for incoming media."""
        pass

    def disconnect(self):
        """Closes the network connection safely."""
        if self.client_socket:
            self.client_socket.close()