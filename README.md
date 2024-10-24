# Nahn
These are the scripts used to store and manage large files on AWS S3, encrypted or not. Some useful toolkits and algorithms are included.

Keywords: AWS, S3, Multipart, Deep Archive, Etag, SHA256, OpenSSL, AES-256-CTR, PBKDF2, Hash, Salt, IV

## Features
- Doesn't require the diskspace to encrypt the whole file. Each time it copies a chunk (default: 1GB) of the whole file, encrypt it and upload it, then move to the next one.
- Each chunk is verified using both md5sum and sha256sum, and the whole file also. You can check the checksum of the whole file manually after uploading.
- In case some chunks failed to upload, you can rerun the script multiple times to ensure the upload is finished. The uploading finishes only if all the checksums are correct.
- Later when you download the file, you can use `openssl` to decrypt the entire file. No more need to use the scripts to decrypt.
- No need to specify your own encrypting credentials. Whoever owns the bucket can decrypt the files. But you can easily add one if you wish to.
