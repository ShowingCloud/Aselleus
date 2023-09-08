#!/bin/bash

bucket_name=""
file_path=$1

part_size=$((1024*1024*1024))
upload_id=$2
part_file="$file_path.part_file"
base_name=$(basename "$file_path")

if [[ -z $upload_id ]]; then
        upload_id=$(aws s3api create-multipart-upload --bucket $bucket_name --key "$base_name" --storage-class DEEP_ARCHIVE --checksum-algorithm SHA256 --query 'UploadId' --output text)
fi

file_size=$(wc -c < "$file_path")
num_parts=$(( ($file_size + $part_size - 1) / $part_size ))
uploaded_parts=$(aws s3api list-parts --bucket $bucket_name --key "$base_name" --upload-id $upload_id --query 'Parts[].PartNumber' --output text)

completed=0
for ((i=1; i<=$num_parts; i++)); do
        if ! grep -q "$i" <<< "$uploaded_parts"; then
                dd if="$file_path" of="$part_file" bs=1048576 count=1024 skip=$((1024*($i-1)))
                etag=$(aws s3api upload-part --bucket $bucket_name --key "$base_name" --part-number $i --upload-id $upload_id --body "$part_file" --checksum-algorithm SHA256 --checksum-sha256 $(sha256sum "$part_file" |cut -f1 -d\ |xxd -r -p |base64))
                echo $i: $etag
                if [[ ! -z "$etag" ]]; then
                        ((completed++))
                fi
        else
                ((completed++))
        fi
done

if [[ $completed == $num_parts ]] ; then
        aws s3api list-parts --bucket $bucket_name --key "$base_name" --upload-id $upload_id --output json --query '{Parts: Parts[*].{PartNumber: PartNumber, ETag: ETag, ChecksumSHA256: ChecksumSHA256}}' |tee "/tmp/$base_name.aws_s3api_parts"
        checksum=$(upload.py sha256 "$file_path")
        aws s3api complete-multipart-upload --bucket $bucket_name --key "$base_name" --upload-id $upload_id --multipart-upload "file:///tmp/$base_name.aws_s3api_parts" --checksum-sha256 $(echo $checksum |cut -f1 -d- |xxd -r -p |base64)-$(echo $checksum |cut -f2 -d-)
fi

# Another high-level implementation with sse-c
# echo $seed |md5sum - |cut -f1 -d\ |head -c 32 >key.bin
# aws s3 cp "$file_path" s3://$bucket_name --sse-c --sse-c-key fileb://key.bin
