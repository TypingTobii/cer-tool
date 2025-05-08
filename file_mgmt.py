import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List
from zipfile import ZipFile

import util
import config


def check_path(path: str) -> None:
    if not os.path.exists(path):
        util.error(f"path '{path}' does not exist")


def create_file(path: str, text_content: List[str] = []) -> None:
    if os.path.exists(path):
        util.error(f"path '{path}' already exists, cannot create a new file.")

    with open(path, "x", encoding="utf-8") as f:
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


def unzip_if_not_folder(path: str) -> bool:
    if not Path(path).is_dir():
        with ZipFile(path) as zip:
            zip.extractall(config.FOLDER_NAME_ZIP)
            util.info(f"file '{path}' extracted to '{config.FOLDER_NAME_ZIP}'.")
        return True
    else:
        return False


def cleanup() -> None:
    if os.path.exists(config.FOLDER_NAME_ZIP):
        shutil.rmtree(config.FOLDER_NAME_ZIP)
        util.info(f"'{config.FOLDER_NAME_ZIP}' deleted.")


def _find_all_paths(keyword: str, path: Path) -> List[Path]:
    return list(path.rglob(f"{keyword}"))


def _find_single_path(keyword: str, path: Path) -> Path:
    results = _find_all_paths(keyword, path)
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


def extract_submissions(groups: List[List[str]], path_from: str, path_to: str) -> List[int]:
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


def open_file(path: str) -> None:
    path = Path(path)
    # taken from: https://stackoverflow.com/questions/434597/open-document-with-default-os-application-in-python-both-in-windows-and-mac-os
    if platform.system() == 'Darwin':  # macOS
        subprocess.call(('open', path))
    elif platform.system() == 'Windows':  # Windows
        os.startfile(path)
    else:  # linux variants
        subprocess.call(('xdg-open', path))
