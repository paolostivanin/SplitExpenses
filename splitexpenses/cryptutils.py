#!/usr/bin/python

import os
import json

from cryptography.hazmat.primitives import hashes
from cryptography import exceptions as crypto_exceptions
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptUtils(object):
    def __init__(self, file_path, password):
        self.file_path = file_path
        self.password = bytes(password, 'utf-8')

    def encrypt(self, json_data):
        salt = os.urandom(32)
        iv = os.urandom(16)
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
        aes_gcm = AESGCM(kdf.derive(self.password))
        enc_data_with_tag = aes_gcm.encrypt(iv, bytes(json.dumps(json_data), 'utf-8'), salt + iv)
        with open(self.file_path, "wb") as fd:
            fd.write(salt + iv + enc_data_with_tag)

    def decrypt(self):
        dec_data = None
        with open(self.file_path, "rb") as fd:
            salt, iv = fd.read(32), fd.read(16)
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000, backend=default_backend())
            aes_gcm = AESGCM(kdf.derive(self.password))
            try:
                dec_data = json.loads(aes_gcm.decrypt(iv, bytes(fd.read()), salt + iv))
            except crypto_exceptions.InvalidTag:
                print("==> ERROR: either the file is corrupted or the password is wrong.")
        return dec_data
