import os
from auxFunctions import *
import json
import subprocess
from PIL import Image
from pillow_heif import register_heif_opener
from moviepy.editor import VideoFileClip

register_heif_opener()
CLR = "\x1B[0K"
exiftool_path = "/usr/local/bin/exiftool"
def CURSOR_UP_FACTORY(upLines): return "\x1B[" + str(upLines) + "A"
def CURSOR_DOWN_FACTORY(upLines): return "\x1B[" + str(upLines) + "B"


OrientationTagID = 274
piexifCodecs = [k.casefold() for k in ['TIF', 'TIFF', 'JPEG',
                                       'JPG', 'HEIC', 'PNG', 'MP4', 'MOV', 'AVI']]


def get_files_from_folder(folder: str, edited_word: str):
    files: list[tuple[str, str]] = []
    folder_entries = list(os.scandir(folder))

    for entry in folder_entries:
        if entry.is_dir():
            print(f"Checking: {entry}")
            files += get_files_from_folder(entry.path, edited_word)
            continue

        if entry.is_file():
            (file_name, ext) = os.path.splitext(entry.name)

            if ext == ".json" and file_name != "metadata":
                file = searchMedia(folder, file_name, edited_word)
                files.append((entry.path, file))

    return files


def get_output_filename(root_folder, out_folder, image_path):
    (image_name, ext) = os.path.splitext(os.path.basename(image_path))
    new_image_name = image_name + ".jpg"
    image_path_dir = os.path.dirname(image_path)
    relative_to_new_image_folder = os.path.relpath(image_path_dir, root_folder)
    return os.path.join(out_folder, relative_to_new_image_folder, new_image_name)


def extract_video_metadata(video_path, metadata_path):
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Extract relevant metadata fields
    title = metadata.get('title', '')
    description = metadata.get('description', '')
    # creation_time = int(metadata['creationTime']['timestamp'])
    photo_taken_time = int(metadata['photoTakenTime']['timestamp'])
    latitude = metadata['geoData']['latitude']
    longitude = metadata['geoData']['longitude']
    altitude = metadata['geoData']['altitude']
    people = [person['name'] for person in metadata.get('people', [])]

    # Construct a dictionary with the extracted metadata
    video_metadata = {
        'title': title,
        'description': description,
        # 'creation_time': creation_time,
        'photo_taken_time': photo_taken_time,
        'latitude': latitude,
        'longitude': longitude,
        'altitude': altitude,
        'people': people
        # Add more metadata fields as needed
    }
    return video_metadata


def extract_image_metadata(image_path, metadata_path):
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)

    # Extract relevant metadata fields
    title = metadata.get('title', '')
    description = metadata.get('description', '')
    people = [person['name']
              for person in metadata.get('people', [])]  # Extract names only

    # Construct a dictionary with the extracted metadata
    image_metadata = {
        'title': title,
        'description': description,
        'people': people  # Store only names in 'people'
        # Add more metadata fields as needed
    }
    return image_metadata


def save_processed_video(video_path, out_folder, metadata):
    # Extract photoTakenTime from metadata
    output_path = os.path.join(out_folder, os.path.basename(video_path))
    people_tag = ", ".join(metadata['people']) if metadata['people'] else ""

    # Construct FFmpeg command to copy video and audio streams and add metadata
    ffmpeg_command = [
        'ffmpeg',
        '-fflags', '+genpts',  # Add this flag to handle non-monotonic DTS
        '-i', video_path,
        '-c', 'copy',
        '-metadata', f'title={metadata["title"]}',
        '-metadata', f'description={metadata["description"]}',
        output_path
    ]

    # Execute FFmpeg command
    subprocess.run(ffmpeg_command, check=True)

    # Construct exiftool command to add people tag
    exiftool_command = [
        exiftool_path,
        '-overwrite_original',
        '-TagsFromFile', video_path,
        '-XMP:PersonInImage=' + people_tag,
        output_path
    ]

    # Execute exiftool command
    subprocess.run(exiftool_command, check=True)

    print("Video saved successfully!")
    setFileCreationTime(output_path, metadata["photo_taken_time"])


def save_processed_image(image_path, output_path, metadata):
    # Extract photoTakenTime from metadata
    # output_path = os.path.join(out_folder, os.path.basename(image_path))

    # Extract and format people tags
    people_tags = []
    for person in metadata['people']:
        if isinstance(person, str):
            people_tags.append(person)
        elif isinstance(person, dict) and 'name' in person:
            people_tags.append(person['name'])

    people_tag = ", ".join(people_tags) if people_tags else ""

    # Construct exiftool command to add people tag
    exiftool_command = [
        exiftool_path,
        '-overwrite_original',
        '-TagsFromFile', image_path,
        '-XMP:PersonInImage=' + people_tag,
        output_path
    ]

    # Execute exiftool command
    subprocess.run(exiftool_command, check=True)
    print("Image saved successfully!")


def processFolder(root_folder, edited_word, optimize, out_folder, max_dimension):
    errorCounter = 0
    successCounter = 0

    files = get_files_from_folder(root_folder, edited_word)

    print("Total files found:", len(files))

    # Create failures directory if it doesn't exist
    failures_dir = os.path.join(out_folder, "failures")
    if not os.path.exists(failures_dir):
        os.makedirs(failures_dir)

    for entry in progressBar(files, upLines=2):
        metadata_path = entry[0]
        file_path = entry[1]

        print("\n", "Current file:", file_path, CLR)

        if not file_path:
            print(CURSOR_UP_FACTORY(2), "Missing file for:",
                  metadata_path, CLR, CURSOR_DOWN_FACTORY(2))
            errorCounter += 1
            # Move the metadata file to failures directory
            os.rename(metadata_path, os.path.join(
                failures_dir, os.path.basename(metadata_path)))
            continue

        (_, ext) = os.path.splitext(file_path)

        if not ext[1:].casefold() in piexifCodecs:
            print(CURSOR_UP_FACTORY(2), 'File format is not supported:',
                  file_path, CLR, CURSOR_DOWN_FACTORY(2))
            errorCounter += 1
            # Move the file to failures directory
            os.rename(file_path, os.path.join(
                failures_dir, os.path.basename(file_path)))
            continue

        if ext[1:].casefold() in ['mp4', 'mov', 'avi']:
            # Video processing
            try:
                print("VIDEO IDENTIFIED")
                metadata = extract_video_metadata(file_path, metadata_path)
                save_processed_video(file_path, out_folder, metadata)
                successCounter += 1
                # Merge metadata and save processed video
            except Exception as e:
                print(CURSOR_UP_FACTORY(2), 'Error processing video:',
                      str(e), CLR, CURSOR_DOWN_FACTORY(2))
                errorCounter += 1
                # Move the file and metadata to failures directory
                os.rename(file_path, os.path.join(
                    failures_dir, os.path.basename(file_path)))
                os.rename(metadata_path, os.path.join(
                    failures_dir, os.path.basename(metadata_path)))
                continue

        elif ext[1:].casefold() in ['tif', 'tiff', 'jpeg', 'jpg', 'heic', 'png']:
            # Image processing
            try:
                print("IMAGE IDENTIFIED")
                image = Image.open(file_path, mode="r").convert('RGB')

                image_exif = image.getexif()
                if OrientationTagID in image_exif:
                    orientation = image_exif[OrientationTagID]

                    if orientation == 3:
                        image = image.rotate(180, expand=True)
                    elif orientation == 6:
                        image = image.rotate(270, expand=True)
                    elif orientation == 8:
                        image = image.rotate(90, expand=True)

                if max_dimension:
                    image.thumbnail(max_dimension)

                new_image_path = get_output_filename(
                    root_folder, out_folder, file_path)

                dir = os.path.dirname(new_image_path)

                if not os.path.exists(dir):
                    os.makedirs(dir)

                with open(metadata_path, encoding="utf8") as f:
                    metadata = json.load(f)

                timeStamp = int(metadata['photoTakenTime']['timestamp'])
                if "exif" in image.info:
                    new_exif = adjust_exif(image.info["exif"], metadata)
                    image.save(new_image_path, quality=optimize, exif=new_exif)
                else:
                    image.save(new_image_path, quality=optimize)

                metadata = extract_image_metadata(file_path, metadata_path)
                save_processed_image(new_image_path, new_image_path, metadata)
                setFileCreationTime(new_image_path, timeStamp)

                successCounter += 1
            except Exception as e:
                print(CURSOR_UP_FACTORY(2), 'Error processing image:',
                      str(e), CLR, CURSOR_DOWN_FACTORY(2))
                errorCounter += 1
                # Move the file and metadata to failures directory
                os.rename(file_path, os.path.join(
                    failures_dir, os.path.basename(file_path)))
                os.rename(metadata_path, os.path.join(
                    failures_dir, os.path.basename(metadata_path)))
                continue

    print()
    print('Metadata merging has been finished')
    print('Success', successCounter)
    print('Failed', errorCounter)
