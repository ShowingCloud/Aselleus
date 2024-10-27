# Nahn
These are the scripts used to store and manage large files on AWS S3, encrypted or not. Some useful toolkits and algorithms are included.

Keywords: AWS, S3, Multipart, Deep Archive, Etag, SHA256, OpenSSL, AES-256-CTR, PBKDF2, Hash, Salt, IV

## Features
- Doesn't require the diskspace to encrypt the whole file. Each time it copies a chunk (default: 1GB) of the whole file, encrypt it and upload it, then move to the next one.
- Each chunk is verified using both md5sum and sha256sum, and the whole file also. You can check the checksum of the whole file manually after uploading.
- In case some chunks failed to upload, you can rerun the script multiple times to ensure the upload is finished. The uploading finishes only if all the checksums are correct.
- Later when you download the file, you can use `openssl` to decrypt the entire file. No more need to use the scripts to decrypt.
- No need to specify your own encrypting credentials. Whoever owns the bucket can decrypt the files. But you can easily add one if you wish to.
- You may need to remove the failed uploads manually with `aws s3api abort-multipart-upload`.
- `metadata.py` is provided to scan a directory and save the metadata of all files inside. For incremental backup you can also use this script to compare with the last backup and make backups to added and modified files only.

## Technical Details
- We use client-side encryption with AES256, in CTR (Counter) mode. All of the credentials required: Salt, Pass and IV, are derived from a pre-defined seed.
- Typically we simply use the md5sum of the original file as the seed, just to be defensive against server-side scanning and possible leakage. Remember to record the original md5sum (in the scripts we record them in object tagging) since you won't be able to find them after encryption.
- We use `tr` to change characters to upper case in the seed. Lower-case characters aren't fully tested, as seeds are used in salt, pass and iv.
- The initial vectors (IV) need to be calculated for each chunk, so that `openssl` can be used to decrypt the whole file. More specifically, inside each chunk IV is incremented by 1 each 16 Bytes, so for example if you're using 1 GB as chunk size you need to increment by `128 * 1024 * 1024` among each chunks.
- Remember to add 0's before the IV values because `openssl enc -aes-256-ctr` requires IV to be exactly 32 digits long.
- In `upload.py` we implemented functions to calculate the md5sum (called Etag in S3) and sha256sum values of the file, either encrypted or not. These checksums are not the same as that from `md5sum` and `sha256sum` commands. S3 calculates the checksums of each chunk, and then generate the checksum of the whole file from these ones of the chunks, along with the number of chunks. This applies whenever you're using multipart upload, even if the file is one-chunk-long.
- The above sha256sum value is needed to complete a multipart upload so it's a guarantee of integrity. You can check the Etag value yourself to be more confident. After uploading it's displayed in the Entity tag colunmn in object overview.
