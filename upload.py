#!/usr/bin/env python

import sys
import threading
import hashlib
import os
import platform
import time
from tqdm import tqdm
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA256
from Crypto.Cipher import AES
from Crypto.Util import Counter

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from botocore.exceptions import ParamValidationError
from botocore.exceptions import NoCredentialsError

GB = 1024 * 1024 * 1024
s3 = boto3.resource('s3')
backet_name = ''

"""
The upload part has not been verified. Nor does it work great with large files.
I can't find reliable resources on how to use multipart manually in Python.
What's worse, the progress callback doesn't work at all.
But the other hash parts, with or without encryption, work great.
And have been verified with the other two scripts,
even with downloading after uploading.
"""

class TransferCallback(object):
    def __init__(self, target_size):
        self._target_size = target_size
        self._total_transferred = 0
        self._lock = threading.Lock()
        self.thread_info = {}

    def __call__(self, bytes_transferred):
        thread = threading.current_thread()
        with self._lock:
            self._total_transferred + bytes_transferred
            if thread.ident not in self.thread_info.keys():
                self.thread_info[thread.ident] = bytes_transferred
            else:
                self.thread_info[thread.ident] += bytes_transferred

        sys.stdout.write(
                f"\r{self._total_transferred} of {self._target_size} transferred "
                f"\r({(self._total_transferred / self._target_size) * 100:.2f}%).")
        sys.stdout.flush()

def upload_with_chunksize_and_meta(local_file_path, object_key):
    file_size = os.path.getsize(local_file_path)
    transfer_callback = TransferCallback(file_size)

    config = TransferConfig(multipart_chunksize = 1 * GB, multipart_threshold = 1 * GB)
    s3.Bucket(bucket_name).upload_file(
            local_file_path,
            object_key,
            Config = config,
            ExtraArgs = {
                #'StorageClass': 'DEEP_ARCHIVE',
                'ChecksumAlgorithm': 'sha256'
                },
            Callback = transfer_callback)
    return transfer_callback.thread_info

class TransferManager:
    def __init__(self):
        try:
            s3.meta.client.head_bucket(Bucket = bucket_name)
        except ParamValidationError as err:
            print(err, file = sys.stderr)
        except ClientError as err:
            print(err, file = sys.stderr)
            print(
                    f"Either bucket_name doesn't exist or you don't "
                    f"have access to it.", file = sys.stderr)

    def transfer(self, local_file_path, object_key):
        start_time = time.perf_counter()
        thread_info = upload_with_chunksize_and_meta(local_file_path, object_key)
        end_time = time.perf_counter()
        self._report_transfer_result(thread_info, end_time - start_time)

    @staticmethod
    def _report_transfer_result(thread_info, elapsed):
        print(f"\nUsed {len(thread_info)} threads.", file = sys.stderr)
        for ident,  byte_count in thread_info.items():
            print(f"{'':4}Thread {ident} copied {byte_count} bytes.", file = sys.stderr)
        print(f"Your transfer took {elapsed:.2f} seconds.", file = sys.stderr)

def encrypt_aes(data, chunk_size, seed, num):
    salt = int(seed[0:16], 16).to_bytes(8, 'big')
    pbkdf2Hash = PBKDF2(seed, salt, 32, count = 10000, hmac_hash_module = SHA256)
    key = pbkdf2Hash[0:32]
    iv =  int(seed[0:31], 16) + int(num * chunk_size / 16)
    return AES.new(key, AES.MODE_CTR, counter = Counter.new(128, initial_value = iv)).encrypt(data)

def calc_s3_etag(file_path, chunk_size = 1 * GB, enc = False, seed = None):
    print("Calculating S3 Etag:", file_path, file = sys.stderr)
    md5s = []

    with open(file_path, 'rb') as fp:
        i = 0
        while True:
            data = fp.read(chunk_size)
            if not data:
                break
            if enc:
                data = encrypt_aes(data, chunk_size, seed, i)
            md5s.append(hashlib.md5(data))
            i += 1

        #if len(md5s) < 1:
        #    return '"{}"'.format(hashlib.md5().hexdigest())

        #if len(md5s) == 1:
        #    return '"{}"'.format(md5s[0].hexdigest())

        digests = b''.join(m.digest() for m in md5s)
        digests_md5 = hashlib.md5(digests)
        return '"{}-{}"'.format(digests_md5.hexdigest(), len(md5s))

def calc_s3_sha256(file_path, chunk_size = 1 * GB, enc = False, seed = None):
    print("Calculating S3 SHA256:", file_path, file = sys.stderr)
    sha256s = []

    with open(file_path, 'rb') as fp:
        i = 0
        while True:
            data = fp.read(chunk_size)
            if not data:
                break
            if enc:
                data = encrypt_aes(data, chunk_size, seed, i)
            sha256s.append(hashlib.sha256(data))
            i += 1

        #if len(sha256s) < 1:
        #    return '"{}"'.format(hashlib.sha256().hexdigest())

        #if len(sha256s) == 1:
        #    return '"{}"'.format(sha256s[0].hexdigest())

        digests = b''.join(m.digest() for m in sha256s)
        digests_sha256 = hashlib.sha256(digests)
        print('{}-{}'.format(digests_sha256.hexdigest(), len(sha256s)), file = sys.stderr)
        return '{}-{}'.format(digests_sha256.hexdigest(), len(sha256s))

if __name__ == '__main__':
    if sys.argv[1] == 'md5':
        print(calc_s3_etag(sys.argv[2]))
        exit(0)
    elif sys.argv[1] == 'encmd5':
        print(calc_s3_etag(sys.argv[2], enc = True, seed = sys.argv[3]))
        exit(0)
    elif sys.argv[1] == 'sha256':
        print(calc_s3_sha256(sys.argv[2]))
        exit(0)
    elif sys.argv[1] == 'encsha256':
        print(calc_s3_sha256(sys.argv[2], enc = True, seed = sys.argv[3]))
        exit(0)

    try:
        transfer_manager = TransferManager()
        transfer_manager.transfer(sys.argv[1], sys.argv[2])
    except NoCredentialsError as error:
        print(error, file = sys.stderr)
