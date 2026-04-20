import os
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class CryptoManager:
    @staticmethod
    def generate_rsa_keypair():
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        return private_key

    @staticmethod
    def get_public_key_bytes(private_key):
        return private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    @staticmethod
    def load_public_key(pub_key_bytes):
        return serialization.load_pem_public_key(pub_key_bytes)

    @staticmethod
    def encrypt_rsa(public_key, data):
        return public_key.encrypt(
            data,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

    @staticmethod
    def decrypt_rsa(private_key, ciphertext):
        return private_key.decrypt(
            ciphertext,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

    @staticmethod
    def generate_aes_key():
        return AESGCM.generate_key(bit_length=256)

    @staticmethod
    def encrypt_aes(key, data):
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    @staticmethod
    def decrypt_aes(key, encrypted_data):
        aesgcm = AESGCM(key)
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        return aesgcm.decrypt(nonce, ciphertext, None)
