import os
import re
import json
import subprocess
import argparse
from datetime import datetime
from tqdm import tqdm
import shutil
import time

allowed_extensions = [
    'jpg', 'jpeg', 'png', 'tif', 'gif', 'jfif', 'mp4', 'mov', 'heic', 'webp',
    'JPG', 'JPEG', 'PNG', 'TIF', 'GIF', 'JFIF', 'MP4', 'MOV', 'HEIC', 'WEBP'
]


def get_files_in_directory(directory, extensions):
    valid_files = []
    failure_files = []

    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root, filename)

            if 'failures' in file_path.split(os.sep) or 'successes' in file_path.split(os.sep):
                continue  # Skip failures & successes

            ext = filename.rsplit('.', 1)[-1].lower()
            if ext in extensions:
                valid_files.append(file_path)
            elif ext not in ['json', 'JSON']:
                failure_files.append(file_path)

    print(f"{len(valid_files)} valid file(s) found.")
    print(f"{len(failure_files)} file(s) with unsupported extensions.")
    return valid_files, failure_files


def get_metadata_json(file_path, input_dir):

    json_path = f'{file_path}.json'

    if not os.path.exists(json_path):
        print(f'{json_path} does not exist.')
        print('Trying to use metadata from a related media file...')
        json_path = find_alt_metadata(file_path, input_dir)
        print(f"NEW JSON PATH: {json_path}")

    if json_path and os.path.exists(json_path):
        with open(json_path, 'r') as json_file:
            return json.load(json_file)
    else:
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
    return ", ".join(people_tags) if people_tags else ""


def format_datetime(timestamp):
    return datetime.fromtimestamp(int(timestamp)).strftime('%Y:%m:%d %H:%M:%S')


def set_file_creation_time(filepath, timestamp):
    date = datetime.fromtimestamp(timestamp)
    mod_time = time.mktime(date.timetuple())
    os.utime(filepath, (mod_time, mod_time))


def update_image_metadata(image_path, metadata, exiftool_path, input_dir):
    def run_exiftool_command(image_path):
        exiftool_command = [
            exiftool_path,
            '-overwrite_original',
            f'-XMP:PersonInImage={people_tag}',
            f'-XMP:Description={metadata.get("description", "")}',
            f'-EXIF:DateTimeOriginal={formatted_date}',
            image_path
        ]
        subprocess.run(exiftool_command, check=True)
        set_file_creation_time(image_path, int(
            metadata['photoTakenTime']['timestamp']))

    people_tag = get_people_tag(metadata)
    formatted_date = format_datetime(metadata['photoTakenTime']['timestamp'])

    try:
        run_exiftool_command(image_path)
        print(f"Image updated successfully: {image_path}")
        move_to_successes(image_path, input_dir)
    except subprocess.CalledProcessError as e:
        if "looks more like a JPEG" in e.stderr or "looks more like a JPG" in e.stderr:
            jpeg_image_path = os.path.splitext(image_path)[0] + '.jpg'
            shutil.copy(image_path, jpeg_image_path)
            print(f"Retrying as JPEG: {jpeg_image_path}")
            try:
                run_exiftool_command(jpeg_image_path)
                set_file_creation_time(jpeg_image_path, int(
                    metadata['photoTakenTime']['timestamp']))
                print(f"Image updated successfully: {jpeg_image_path}")
                os.remove(image_path)
                move_to_successes(jpeg_image_path, input_dir)
            except:
                print(f"Failed to update metadata for {jpeg_image_path}: {e}")
                move_to_failures(image_path, input_dir)
        elif "looks more like a PNG" in e.stderr:
            png_image_path = os.path.splitext(image_path)[0] + '.png'
            shutil.copy(image_path, png_image_path)
            print(f"Retrying as PNG: {png_image_path}")
            try:
                run_exiftool_command(png_image_path)
                set_file_creation_time(png_image_path, int(
                    metadata['photoTakenTime']['timestamp']))
                print(f"Image updated successfully: {png_image_path}")
                os.remove(image_path)
                move_to_successes(png_image_path, input_dir)
            except:
                print(f"Failed to update metadata for \
                      {png_image_path}: {e}")
                move_to_failures(image_path, input_dir)
        else:
            print(f"Failed to update metadata for \
                      {image_path}: {e}")
            move_to_failures(image_path, input_dir)


def update_video_metadata(video_path, metadata, exiftool_path, input_dir):
    people_tag = get_people_tag(metadata)
    formatted_date = format_datetime(metadata['photoTakenTime']['timestamp'])
    exiftool_command = [
        exiftool_path,
        '-overwrite_original',
        f'-XMP:PersonInImage={people_tag}',
        f'-XMP:Description={metadata.get("description", "")}',
        f'-QuickTime:CreateDate={formatted_date}',
        f'-QuickTime:ModifyDate={formatted_date}',
        video_path
    ]

    subprocess.run(exiftool_command, check=True)
    set_file_creation_time(video_path, int(
        metadata['photoTakenTime']['timestamp']))

    move_to_successes(video_path, input_dir)
    print(f"Video updated successfully: {video_path}\n")


def move_to_failures(file_path, input_dir):
    failures_dir = os.path.join(input_dir, 'failures')
    os.makedirs(failures_dir, exist_ok=True)
    try:
        shutil.move(file_path, failures_dir)
        print(f"Moved {file_path} to {failures_dir}")
    except shutil.Error as e:
        print(f"Failed to move {file_path} to {failures_dir}: {e} \n")


def move_to_successes(file_path, input_dir):
    successes_dir = os.path.join(input_dir, 'successes')
    os.makedirs(successes_dir, exist_ok=True)
    try:
        destination_path = os.path.join(
            successes_dir, os.path.basename(file_path))
        if os.path.exists(destination_path):
            print(f"File already exists in successes: {destination_path}")
        else:
            shutil.move(file_path, successes_dir)
            print(f"Moved {file_path} to {successes_dir}")
    except shutil.Error as e:
        print(f"Failed to move {file_path} to {successes_dir}: {e}")


def get_exif_datetime(file_path, exiftool_path):
    exiftool_command = [
        exiftool_path,
        '-CreateDate',
        '-j',
        '-n',
        file_path
    ]
    try:
        result = subprocess.run(
            exiftool_command, capture_output=True, text=True, check=True)
        exif_data = json.loads(result.stdout)
        # print(f"Exif Data: {exif_data}")
        if exif_data and 'CreateDate' in exif_data[0]:

            date_string = exif_data[0]['CreateDate']
            # Parse the date string and convert to Unix timestamp
            date_object = datetime.strptime(date_string, "%Y:%m:%d %H:%M:%S")
            print(f"Create Date: {date_object}")
            return int(date_object.timestamp())
    except subprocess.CalledProcessError as e:
        print(f"Error reading EXIF data: {e}")
    return None


def find_alt_metadata(file_path, input_dir):
    file_name = os.path.basename(file_path)
    base_name, extension = os.path.splitext(file_name)

    # Check if the file name has a number in parentheses
    match = re.match(r'(.+)\((\d+)\)$', base_name)
    if match:
        base_without_number = match.group(1)
        number = match.group(2)
        json_names_to_search = [
            f"{base_without_number}{extension}({number}).json",
            f"{base_without_number}.JPG({number}).json",
            f"{base_without_number}.jpg({number}).json",
            f"{base_without_number}.JPEG({number}).json",
            f"{base_without_number}.jpeg({number}).json",
        ]
    else:
        base_without_edited = re.sub(
            r'-edited$', '', base_name, flags=re.IGNORECASE)
        json_names_to_search = [
            f"{base_without_edited}{extension}.json",
            f"{base_name}.JPG.json",
            f"{base_name}.jpg.json",
            f"{base_name}.JPEG.json",
            f"{base_name}.jpeg.json",
            f"{base_without_edited}.JPG.json",
            f"{base_without_edited}.jpg.json",
            f"{base_without_edited}.JPEG.json",
            f"{base_without_edited}.jpeg.json",
        ]

    print(f"Searching for JSON files: {json_names_to_search}")

    for root, _, filenames in os.walk(input_dir):
        for filename in filenames:
            if filename.lower().endswith('.json'):
                for json_name in json_names_to_search:
                    if filename.lower() == json_name.lower():
                        full_path = os.path.join(root, filename)
                        print(f"Found matching JSON: {full_path}")
                        return full_path

                # If no exact match, check if base name is in the JSON filename
                if base_name.lower() in filename.lower():
                    full_path = os.path.join(root, filename)
                    print(f"Found related JSON: {full_path}")
                    return full_path

    print("No matching or related JSON found")
    return None


def process_files(input_dir, exiftool_path):
    media_files, failures = get_files_in_directory(
        input_dir, allowed_extensions)
    for failure in failures:
        print(f"Moving {failure} to failure directory")
        move_to_failures(failure, input_dir)

    for media_file in tqdm(media_files):
        try:
            print(f'\nProcessing: {media_file}')
            metadata = get_metadata_json(media_file, input_dir)

            if metadata:
                if media_file.lower().endswith(('jpg', 'jpeg', 'png', 'tif', 'gif', 'jfif', 'webp', 'heic')):
                    update_image_metadata(
                        media_file, metadata, exiftool_path, input_dir)
                elif media_file.lower().endswith(('mp4', 'mov', 'avi')):
                    update_video_metadata(
                        media_file, metadata, exiftool_path, input_dir)
            else:
                print(f'No metadata file available for: {media_file}')
                exif_datetime = get_exif_datetime(media_file, exiftool_path)
                if exif_datetime:
                    set_file_creation_time(media_file, int(exif_datetime))
                    print(
                        f"Updated file date/time but that's it: {media_file}")
                    move_to_failures(media_file, input_dir)
                else:
                    print(f"No EXIF Create Date found for: {media_file}")
                    move_to_failures(media_file, input_dir)
        except Exception as e:
            print(f"Failed to process {media_file}: {e}")
            if os.path.exists(media_file):
                move_to_failures(media_file, input_dir)
            else:
                print(f"{media_file} does not exist. \n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Process media files and update metadata.')
    parser.add_argument(
        'input_directory', help='The input directory containing media files and metadata.')
    parser.add_argument('--exiftool_path', default='exiftool',
                        help='Path to the exiftool executable.')

    args = parser.parse_args()
    process_files(args.input_directory, args.exiftool_path)
