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
                                       'JPG', 'HEIC', 'PNG', 'MP4', 'MOV']]


def get_files_from_folder(folder: str, edited_word: str):
    files: list[tuple[str, str]] = []
    folder_entries = list(os.scandir(folder))

    for entry in folder_entries:
        if entry.is_dir():
            files = get_files_from_folder(entry.path, edited_word)
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
    print(f"\nMETADATA PATH: {metadata_path}")
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


def save_processed_image(image_path, out_folder, metadata):
    image = Image.open(image_path)
    output_path = os.path.join(out_folder, os.path.basename(image_path))
    image.save(output_path)


def save_processed_video(video_path, out_folder, metadata):
    print("SAVING PROCESSED VIDEO:")
    print(f"Metadata: {metadata}")
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
        # '-metadata', f'creation_time={metadata["creation_time"]}',
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


def processFolder(root_folder, edited_word, optimize, out_folder, max_dimension):
    errorCounter = 0
    successCounter = 0

    files = get_files_from_folder(root_folder, edited_word)

    print("Total files found:", len(files))

    for entry in progressBar(files, upLines=2):
        metadata_path = entry[0]
        file_path = entry[1]

        print("\n", "Current file:", file_path, CLR)
        print(f"METADATA PATH: {metadata_path}")

        if not file_path:
            print(CURSOR_UP_FACTORY(2), "Missing file for:",
                  metadata_path, CLR, CURSOR_DOWN_FACTORY(2))
            errorCounter += 1
            continue

        (_, ext) = os.path.splitext(file_path)

        if not ext[1:].casefold() in piexifCodecs:
            print(CURSOR_UP_FACTORY(2), 'File format is not supported:',
                  file_path, CLR, CURSOR_DOWN_FACTORY(2))
            errorCounter += 1
            continue

        if ext[1:].casefold() in ['mp4', 'mov']:
            # Video processing
            try:
                print("VIDEO IDENTIFIED")
                metadata = extract_video_metadata(file_path, metadata_path)
                print(f"{metadata}")
                save_processed_video(file_path, out_folder, metadata)
                # Merge metadata and save processed video
            except Exception as e:
                print(CURSOR_UP_FACTORY(2), 'Error processing video:',
                      str(e), CLR, CURSOR_DOWN_FACTORY(2))
                errorCounter += 1
                continue
            # # Image processing
            # try:
            #     metadata = extract_image_metadata(file_path)
            #     save_processed_image(file_path, out_folder, metadata)
            #     # Merge metadata and save processed image
            # except Exception as e:
            #     print(CURSOR_UP_FACTORY(2), 'Error processing image:',
            #           str(e), CLR, CURSOR_DOWN_FACTORY(2))
            #     errorCounter += 1
            #     continue

        successCounter += 1

    print()
    print('Metadata merging has been finished')
    print('Success', successCounter)
    print('Failed', errorCounter)
