import struct
import json

MAGIC_HEADER = b'WRDN'

class Protocol:
    @staticmethod
    def recv_exact(sock, num_bytes):
        data = bytearray()
        while len(data) < num_bytes:
            packet = sock.recv(num_bytes - len(data))
            if not packet:
                return None
            data.extend(packet)
        return bytes(data)

    @staticmethod
    def recv_packet(sock):
        # Read header (4 bytes magic + 4 bytes length)
        header = Protocol.recv_exact(sock, 8)
        if not header:
            return None
        
        magic, length = struct.unpack('!4sI', header)
        if magic != MAGIC_HEADER:
            raise ValueError(f"Invalid magic header: {magic}")
            
        payload = Protocol.recv_exact(sock, length)
        if not payload:
            return None
            
        return payload

    @staticmethod
    def send_packet(sock, payload_bytes):
        length = len(payload_bytes)
        header = struct.pack('!4sI', MAGIC_HEADER, length)
        sock.sendall(header + payload_bytes)

    @staticmethod
    def serialize_message(cmd, data):
        msg = {"cmd": cmd, "data": data}
        return json.dumps(msg).encode('utf-8')

    @staticmethod
    def deserialize_message(payload_bytes):
        msg = json.loads(payload_bytes.decode('utf-8'))
        return msg.get("cmd"), msg.get("data")
