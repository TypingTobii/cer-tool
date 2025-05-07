import os
import shutil
from pathlib import Path
from typing import List
from zipfile import ZipFile

import util
import config

def create_folder_structure() -> None:
    ## TODO: include parent path
    if not os.path.exists(config.FOLDER_NAME_SUBMISSIONS):
        os.mkdir(config.FOLDER_NAME_SUBMISSIONS)
    if not os.path.exists(config.FOLDER_NAME_OUTPUT):
        os.mkdir(config.FOLDER_NAME_OUTPUT)


def unzip(path: str) -> None:
    with ZipFile(path) as zip:
        zip.extractall(config.FOLDER_NAME_UNZIP)


def cleanup() -> None:
    if os.path.exists(config.FOLDER_NAME_UNZIP):
        shutil.rmtree(config.FOLDER_NAME_UNZIP)


def _find_all_paths(keyword: str, path: Path) -> List[Path]:
    return list( path.rglob(f"{keyword}") )


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


def flat_copy_all(path_from: Path, path_to: Path, name_prefix, name_suffix) -> None:
    files_in_folder = sorted(path_from.glob("*"))
    for i, file in enumerate(files_in_folder):
        i += 1
        if not file.is_dir():
            extension = file.suffix
            shutil.copy(file, path_to / f"{name_prefix}{i}{name_suffix}{extension}")
        else:
            flat_copy_all(file, path_to, name_prefix + f"{i}-", name_suffix)



def extract_submissions(groups: List[List[str]], path_from: Path, path_to: Path) -> List[int]:
    extracted = []

    for groupIdx, group in enumerate(groups):
        for memberIdx, member in enumerate(group):
            submission_folder = _find_single_path(f"*{member}*{config.MOODLE_SUBMISSION_KEYWORD}*", path_from)
            moodle_id = submission_folder.name.split("_")[1]

            prefix = f"Submission | G {groupIdx + 1}{util.index_to_ascii(memberIdx)} | {member} | {moodle_id} | File "
            suffix = f"| ??? pts"

            flat_copy_all(path_from, path_to, prefix, suffix)
            extracted.append(moodle_id)

    return extracted