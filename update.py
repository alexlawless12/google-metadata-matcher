import os
import json
import fnmatch
import subprocess
import argparse
from datetime import datetime
import shutil

allowed_extensions = ['jpg', 'jpeg', 'png', 'mp4', 'mov', 'avi', 'heic', 'webp',
                      'JPG', 'JPEG', 'PNG', 'MP4', 'MOV', 'AVI', 'HEIC', 'WEBP']


def get_files_in_directory(directory, extensions):
    valid_files = []
    failure_files = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename)

            if 'failures' in file_path.split(os.sep):
                continue  # Skip failures

            ext = filename.rsplit('.', 1)[-1].lower()
            if ext in extensions:
                valid_files.append(file_path)
            elif ext in ['json', 'JSON']:
                continue
            else:
                failure_files.append(file_path)

    print(f"{len(valid_files)} valid file(s) found.")
    print(f"{len(failure_files)} file(s) with unsupported extensions.")

    return valid_files, failure_files


def get_metadata_json(file_path):
    json_path = f'{file_path}.json'
    if not os.path.exists(json_path):
        base_name = os.path.splitext(file_path)[0]
        json_path = next((f for f in os.listdir(os.path.dirname(
            file_path)) if f.startswith(base_name) and f.endswith('.json')), None)
        if json_path:
            json_path = os.path.join(os.path.dirname(file_path), json_path)
    if json_path and os.path.exists(json_path):
        with open(json_path, 'r') as json_file:
            metadata = json.load(json_file)
            return metadata
    print(f"Metadata not found for: {file_path}")
    return None


def get_people_tag(metadata):
    people_tags = []
    if 'people' in metadata:
        for person in metadata['people']:
            if isinstance(person, str):
                people_tags.append(person)
            elif isinstance(person, dict) and 'name' in person:
                people_tags.append(person['name'])
    people_tag = ", ".join(people_tags) if people_tags else ""
    return people_tag


def format_datetime(timestamp):
    return datetime.fromtimestamp(int(timestamp)).strftime('%Y:%m:%d %H:%M:%S')


def update_image_metadata(image_path, metadata, exiftool_path):
    people_tag = get_people_tag(metadata)
    formatted_date = format_datetime(metadata['photoTakenTime']['timestamp'])
    exiftool_command = [
        exiftool_path,
        '-overwrite_original',
        '-XMP:PersonInImage=' + people_tag,
        '-XMP:Description=' + metadata.get("description", ""),
        '-EXIF:DateTimeOriginal=' + formatted_date,
        image_path
    ]
    subprocess.run(exiftool_command, check=True)
    print(f"Image updated successfully: {image_path}")


def update_video_metadata(video_path, metadata, exiftool_path):
    people_tag = get_people_tag(metadata)
    formatted_date = format_datetime(metadata['photoTakenTime']['timestamp'])
    exiftool_command = [
        exiftool_path,
        '-overwrite_original',
        '-XMP:PersonInImage=' + people_tag,
        '-XMP:Description=' + metadata.get("description", ""),
        '-QuickTime:CreateDate=' + formatted_date,
        '-QuickTime:ModifyDate=' + formatted_date,
        video_path
    ]
    subprocess.run(exiftool_command, check=True)
    print(f"Video updated successfully: {video_path}")


def move_to_failures(file_path, input_dir):
    failures_dir = os.path.join(input_dir, 'failures')
    os.makedirs(failures_dir, exist_ok=True)
    try:
        shutil.move(file_path, failures_dir)
        print(f"Moved {file_path} to {failures_dir}")
    except shutil.Error as e:
        print(f"Failed to move {file_path} to {failures_dir}: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def process_files(input_dir, exiftool_path):
    media_files, failures = get_files_in_directory(
        input_dir, allowed_extensions)
    for failure in failures:
        print(f"Moving {failure} to failure directory")
        move_to_failures(failure, input_dir)
    for media_file in media_files:
        try:
            print(f'\n{media_file}...')
            metadata = get_metadata_json(media_file)
            if not metadata:
                print('Trying to use metadata from a related image file...')
                image_file_path = media_file.rsplit('.', 1)[0] + '.HEIC'
                if os.path.exists(image_file_path + '.json'):
                    metadata = get_metadata_json(image_file_path)
                    if metadata:
                        print('Using metadata from image file:', image_file_path)

            if metadata:
                if media_file.lower().endswith(('jpg', 'jpeg', 'png', 'webp', 'heic')):
                    update_image_metadata(media_file, metadata, exiftool_path)
                elif media_file.lower().endswith(('mp4', 'mov', 'avi')):
                    update_video_metadata(media_file, metadata, exiftool_path)
            else:
                print('No metadata available for:', media_file)
                move_to_failures(media_file, input_dir)
        except Exception as e:
            print(f"Failed to process {media_file}: {e}")
            move_to_failures(media_file, input_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Process media files and update metadata.')
    parser.add_argument(
        'input_directory', help='The input directory containing media files and metadata.')
    parser.add_argument('--exiftool_path', default='exiftool',
                        help='Path to the exiftool executable.')

    args = parser.parse_args()

    process_files(args.input_directory, args.exiftool_path)
