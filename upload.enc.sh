#!/bin/bash

bucket_name=""
file_path=$1

part_size=$((1024*1024*1024))
upload_id=$2
part_file="$file_path.part_file"
base_name=$(basename "$file_path") # eg. basename="dir/"$(basename "$file_path")

# export AWS_CA_BUNDLE=Cloudflare_CA.pem # for Cloudflare Zero Trust, but uploading doesn't seem to work

if [[ -z $upload_id ]]; then
        upload_id=$(aws s3api create-multipart-upload --bucket $bucket_name --key "$base_name" --storage-class DEEP_ARCHIVE --checksum-algorithm SHA256 --query 'UploadId' --output text)
fi

file_size=$(wc -c < "$file_path")
num_parts=$(( ($file_size + $part_size - 1) / $part_size ))
uploaded_parts=$(aws s3api list-parts --bucket $bucket_name --key "$base_name" --upload-id $upload_id --query 'Parts[].PartNumber' --output text)

completed=0
seed="" # takes 16 bytes hex (32 digits), all in upper case.
# eg. seed=$(md5sum "$file_path" |awk '{print $1}' |tr '[:lower:]' '[:upper:]')

for ((i=1; i<=$num_parts; i++)); do
        if ! egrep -q "(^|[[:space:]])$i($|[[:space:]])" <<< "$uploaded_parts"; then
                iv=$(echo "ibase=16; obase=10; $(echo $seed |cut -c 1-31) + $(printf "%032X" $((($i-1)*$part_size/16)))" |bc)
                while [ ${#iv} -lt 32 ]; do
                        iv=0$iv
                done

                dd if="$file_path" bs=1048576 count=1024 skip=$((1024*($i-1))) |openssl enc -aes-256-ctr -iv $iv -S $(echo $seed |cut -c 1-16) -pbkdf2 -pass pass:"$seed" -out "$part_file"
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
        checksum=$(upload.py encsha256 "$file_path" "$seed")
        aws s3api complete-multipart-upload --bucket $bucket_name --key "$base_name" --upload-id $upload_id --multipart-upload "file:///tmp/$base_name.aws_s3api_parts" --checksum-sha256 $(echo $checksum |cut -f1 -d- |xxd -r -p |base64)-$(echo $checksum |cut -f2 -d-)
        aws s3api put-object-tagging --bucket $bucket_name --key "$base_name" --tagging '{"TagSet": [{ "Key": "encryption seed", "Value": "'$seed'" }]}'
fi
