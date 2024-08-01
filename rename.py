import os
import shutil
import argparse


def rename_files_in_directory(directory):
    for root, _, files in os.walk(directory):
        # Extract the name of the current directory
        dir_name = os.path.basename(root)
        for file in files:
            file_path = os.path.join(root, file)
            new_file_name = f"{dir_name}.{file}"
            new_file_path = os.path.join(root, new_file_name)
            shutil.move(file_path, new_file_path)
            print(f"Renamed {file} to {new_file_name}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Rename all files by prepending the directory name to the filename.')
    parser.add_argument('directory', type=str,
                        help='The directory containing the files to rename')
    args = parser.parse_args()
    rename_files_in_directory(args.directory)
