import socket
import logging

from warden_core.crypto import CryptoManager
from warden_core.protocol import Protocol

class WardenNetClient:
    def __init__(self, host="127.0.0.1", port=8000):
        self.host = host
        self.port = port
        self.sock = None
        self.aes_key = None
        self.logger = logging.getLogger("WardenNetClient")

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(10.0) # 10 second timeout for operations
            self.sock.connect((self.host, self.port))
            
            # --- Handshake ---
            # 1. Receive server's RSA public key
            pub_key_bytes = Protocol.recv_packet(self.sock)
            if not pub_key_bytes:
                raise ConnectionError("Failed to receive public key from server.")
            
            server_pub_key = CryptoManager.load_public_key(pub_key_bytes)
            
            # 2. Generate and encrypt AES key
            self.aes_key = CryptoManager.generate_aes_key()
            encrypted_aes = CryptoManager.encrypt_rsa(server_pub_key, self.aes_key)
            
            # 3. Send encrypted AES key
            Protocol.send_packet(self.sock, encrypted_aes)
            
            self.logger.info("Successfully connected and negotiated AES session key.")
            return True
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            if self.sock:
                self.sock.close()
                self.sock = None
            return False

    def send_command(self, cmd, data):
        """Sends an encrypted command to the server and returns the response."""
        if not self.sock:
            if not self.connect():
                raise ConnectionError("Not connected to server.")

        try:
            # Prepare payload
            payload_bytes = Protocol.serialize_message(cmd, data)
            encrypted_payload = CryptoManager.encrypt_aes(self.aes_key, payload_bytes)
            
            # Send
            Protocol.send_packet(self.sock, encrypted_payload)
            
            # Receive response
            encrypted_response = Protocol.recv_packet(self.sock)
            if not encrypted_response:
                raise ConnectionError("Server closed connection prematurely.")
                
            decrypted_bytes = CryptoManager.decrypt_aes(self.aes_key, encrypted_response)
            _, response_data = Protocol.deserialize_message(decrypted_bytes)
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending command {cmd}: {e}")
            # Invalidate connection on error
            if self.sock:
                self.sock.close()
                self.sock = None
            raise

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None
