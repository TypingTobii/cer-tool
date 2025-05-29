import os
import platform
import re
import shutil
import subprocess
import zipfile
from functools import reduce
from pathlib import Path
from typing import List, Tuple
from os import PathLike
from zipfile import ZipFile

import py7zr
shutil.register_unpack_format('7zip', ['.7z'], py7zr.unpack_7zarchive)
shutil.register_archive_format('7zip', py7zr.pack_7zarchive, description='7zip archive')

import util
import config


temporary_folders: List[Path] = []
def _get_temporary_name() -> str:
    return config.FOLDER_NAME_TEMP.format(len(temporary_folders))


def check_path(path: str) -> None:
    if not os.path.exists(path):
        util.error(f"path '{path}' does not exist")


def create_file(path: str, text_content: List[str] = []) -> None:
    mode = "x"

    if os.path.exists(path):
        option = util.choose_option({"y", "n"}, "y", f"path '{path}' already exists. Overwrite?")
        if option != "y":
            util.error("Aborted by user")
        else:
            mode = "w"

    with open(path, mode, encoding="utf-8") as f:
        util.info(f"file '{path}' created.")
        f.write('\n'.join(text_content))


def read_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().split('\n')


def delete_file(path: str) -> None:
    os.remove(path)
    util.info(f"file '{path}' deleted.")


def create_folder(path: str) -> None:
    if not Path(path).exists():
        Path(path).mkdir(parents=True)
        util.info(f"folder '{path}' created.")

def create_temporary_folder() -> Path:
    folder_name: str = _get_temporary_name()
    p = Path(folder_name)
    p.mkdir(parents=True)
    util.info(f"folder '{p}' created.")
    temporary_folders.append(p.resolve())
    return p


def extract_archive(path: str | PathLike[str], target: str | PathLike[str] | None = None):
    path_from = Path(path)
    path_to = Path(target) if target else path_from.with_suffix("")
    shutil.unpack_archive(path_from, path_to)
    util.info(f"file '{path_from}' extracted to '{path_to}'.")
    temporary_folders.append(path_to.resolve())


def extract_all_within(path: str | PathLike[str]):
    archive_suffixes: List[str] = reduce(lambda acc, curr: acc + curr[1], shutil.get_unpack_formats(), []) # create a list of supported archive extensions
    path: Path = Path(path)
    base_folder: str = path.stem

    def rec(path: Path, level: int = 0):
        if level > 10:
            util.error(f"archives/folders inside {base_folder} are nested to deeply.")

        for file in path.glob("*"):
            if file.is_dir():
                rec(file, level + 1)
            elif file.suffix in archive_suffixes:
                extract_archive(file)
                rec(file.with_suffix(""), level + 1)

    rec(path)

if __name__ == "__main__":
    extract_all_within("../test")



def unzip_if_not_folder(path: PathLike[str] | str) -> Path:
    path = Path(path)
    if not path.is_dir():
        target = Path(_get_temporary_name())
        extract_archive(path, target)
        return target
    else:
        return path


def zip_folder(path: str, output_path: str) -> None:
    if output_path.endswith(".zip"):
        output_path = re.sub(r"(.*)\.zip", r"\1", output_path)
    shutil.make_archive(output_path, "zip", path)
    util.info(f"Zipped '{path}' to '{output_path}.zip'.")


def zip_folder_with_limit(path: str | PathLike[str], output_path: str, limit_bytes: int = config.MOODLE_FILE_UPLOAD_LIMIT_BYTES) -> int:
    def partition(files: List[Tuple[Path, int]], acc_size: int = 0, acc: List[Path] = None) -> List[List[Path]]:
        if not files:
            return [acc] if acc is not None else []

        file, size = files[0]

        if size > limit_bytes:
            util.warning(f"file '{file}' exceeds limit of {limit_bytes} bytes.", "file will be skipped.")
            return partition(files[1:], acc_size, acc)

        if size + acc_size <= limit_bytes:  # insert file into current sub-list
            new_acc = acc + [file] if acc is not None else [file]
            return partition(files[1:], size + acc_size, new_acc)
        else:  # insert file into new sub-list
            rest = partition(files[1:], size, [file])
            return [acc] + rest

    def zip_files(files: List[Path], suffix: str) -> None:
        with ZipFile(f"{output_path}{suffix}.zip", "w", compression=zipfile.ZIP_DEFLATED) as zip:
            for file in files:
                zip.write(file, file.name)
                util.info(f"Zipped '{file}' to '{output_path}{suffix}.zip'.")

    if output_path.endswith(".zip"):
        output_path = re.sub(r"(.*)\.zip", r"\1", output_path)

    files_to_zip = list(Path(path).iterdir())
    files_to_zip = list(map(lambda p: (p, p.stat().st_size), files_to_zip))  # zip with file size

    partitioned_files = partition(files_to_zip)
    total_zips = len(partitioned_files)

    for i, partition in enumerate(partitioned_files):
        suffix = f"_{i + 1}_of_{total_zips}" if total_zips > 0 else ""
        zip_files(partition, suffix)

    return total_zips


def cleanup() -> None:
    for folder in reversed(temporary_folders):
        if folder.exists():
            shutil.rmtree(folder)
            util.info(f"'{folder}' deleted.")


def _find_all_paths(keyword: str, path: Path, replace_non_ascii: bool = True) -> List[Path]:
    if replace_non_ascii:
        keyword = ''.join([c if ord(c) < 128 else '*' for c in keyword])
    return list(path.rglob(f"{keyword}"))


def _find_single_path(keyword: str, path: Path, replace_non_ascii: bool = True) -> Path:
    results = _find_all_paths(keyword, path, replace_non_ascii)
    i = 0
    if not results:
        util.error(f"No results found for '{keyword}'")
    elif len(results) > 1:
        i = util.choose_index(results, f"Multiple results found for '{keyword}':", "Select the correct result:")

    return results[i]


def parse_groups_file(path: str) -> List[List[str]] | None:
    try:
        with open(path, "r", encoding="utf-8") as groups_file:
            # get all lines of the file (1 line = 1 group)
            groups = groups_file.read().splitlines()

            # ignore all empty lines
            groups = filter(lambda s: len(s) > 0, groups)

            # split each line (group) at "," and remove any unnecessary whitespace before or after the member's name
            groups = map(lambda group: [s.strip() for s in group.split(",")],
                         groups)
            return list(groups)

    except FileNotFoundError:
        util.error(f"file {path} not found")
        return None


def _flat_copy_all(path_from: Path, path_to: Path, name_prefix, name_suffix) -> None:
    files_in_folder = sorted(path_from.glob("*"))
    for i, file in enumerate(files_in_folder):
        i += 1
        if not file.is_dir():
            extension = file.suffix
            shutil.copy(file, path_to / f"{name_prefix}{i}{name_suffix}{extension}")
            util.info(f"'{file.name}' copied to '{name_prefix}{i}{name_suffix}{extension}'.")
        else:
            _flat_copy_all(file, path_to, name_prefix + f"{i}-", name_suffix)


def extract_submissions(groups: List[List[str]], path_from: str | PathLike[str], path_to: str) -> List[int]:
    create_folder(path_to)
    path_to = Path(path_to)
    path_from = Path(path_from)
    extracted = []

    for groupIdx, group in enumerate(groups):
        for memberIdx, member in enumerate(group):
            submission_folder = _find_single_path(f"*{member}*{config.MOODLE_SUBMISSION_KEYWORD}*", path_from)
            moodle_id = submission_folder.name.split("_")[1]

            prefix = f"Submission_Gr{groupIdx + 1}{util.index_to_ascii(memberIdx)}_{member}_{moodle_id}_File "
            suffix = f"_ --- pts"

            _flat_copy_all(submission_folder, path_to, prefix, suffix)
            extracted.append(moodle_id)

    return extracted


def parse_submission_filename(path: Path) -> (str, int, str, (float | None)):
    filename_split = path.stem.split('_')

    # try to extract the individual parts of the filename
    name = id = file_id = points = None
    try:
        name = filename_split[2]
        id = filename_split[3]
        file_id = filename_split[4].replace("File", "").strip()
        points = filename_split[5].replace("pts", "").replace(',', '.').strip()
    except IndexError:
        raise ValueError(f"Unsupported Filename: {path.stem}")

    # try to decode points
    try:
        points = float(points)
    except ValueError:
        points = None

    return name, id, file_id, points


def get_points_from_path(keyword: str, path: str) -> float | None:
    path = Path(path)
    feedback_files = _find_all_paths(f"*_{keyword}_*", path)

    points_sum = 0
    points_found = False

    for file in feedback_files:
        try:
            _, id, _, points = parse_submission_filename(file)
            points_sum += float(points)
            points_found = True
        except ValueError or TypeError:
            util.warning(f"No points found inside '{file.name}'.",
                         "File will not be considered for calculating points.")
            continue

    return points_sum if points_found else None


def copy_feedback_files(keyword: str, path_from: str | PathLike[str], path_to: str | PathLike[str], submission_name: str = "") -> int:
    path_from = Path(path_from)
    path_to = Path(path_to)
    feedback_files = _find_all_paths(f"*_{keyword}_*", path_from)
    copied = 0

    for file in feedback_files:
        student_name, student_id, file_id, points = parse_submission_filename(file)
        if points is None:
            util.warning(f"No points found inside '{file.name}'.", "File will not be included as feedback.")
            continue

        filename = f"{student_name}_{student_id}_{config.MOODLE_SUBMISSION_KEYWORD}_{config.MOODLE_FEEDBACK_FILENAME_PREFIX}"
        if submission_name:
            filename += f"_{submission_name}"
        filename += f"_(Datei {file_id})_{config.MOODLE_FEEDBACK_FILENAME_SUFFIX}{file.suffix}"

        shutil.copy2(file, path_to / filename)
        copied += 1
        util.info(f"Feedback file '{file}' copied to '{path_to / filename}'.")

    return copied


def open_file(path: str) -> None:
    path = Path(path)
    # taken from: https://stackoverflow.com/questions/434597/open-document-with-default-os-application-in-python-both-in-windows-and-mac-os
    if platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', path))
    elif platform.system() == 'Windows':  # Windows
        os.startfile(path)
    else:  # linux variants
        subprocess.call(('xdg-open', path))
