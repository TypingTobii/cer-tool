import os
import platform
import re
import shutil
import subprocess
import zipfile
from functools import reduce
from pathlib import Path
from typing import List, Tuple, Callable
from os import PathLike
from zipfile import ZipFile

import py7zr
shutil.register_unpack_format('7zip', ['.7z'], py7zr.unpack_7zarchive)
shutil.register_archive_format('7zip', py7zr.pack_7zarchive, description='7zip archive')

from cer_tool import util, config


temporary_folders: List[Path] = []
def _get_temporary_name() -> str:
    return config.get("filenames.tmp_folder").format(len(temporary_folders))


def check_path(path: str) -> Path:
    path = Path(path)
    if not path.exists():
        util.error(f"path '{path}' does not exist")
    return path


def create_file(path: str, text_content: List[str] = []) -> None:
    mode = "x"

    if os.path.exists(path):
        option = util.choose_option({"y", "n"}, "y", f"path '{path}' already exists. Overwrite?")
        if option != "y":
            util.error("Aborted by user")
        else:
            mode = "w"

    with open(path, mode, encoding="utf-8") as f:
        util.info(f" CREATE: file '{path}'")
        f.write('\n'.join(text_content))


def read_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().split('\n')


def delete_file(path: str) -> None:
    os.remove(path)
    util.info(f" DELETE: '{path}'")


def create_folder(path: str | PathLike[str]) -> None:
    if not Path(path).exists():
        Path(path).mkdir(parents=True)
        util.info(f" CREATE: folder '{path}'")

def create_temporary_folder() -> Path:
    folder_name: str = _get_temporary_name()
    p = Path(folder_name)
    p.mkdir(parents=True)
    util.info(f" CREATE: temporary folder '{p}'")
    temporary_folders.append(p.resolve())
    return p


def extract_archive(path: str | PathLike[str], target: str | PathLike[str] | None = None):
    path_from = Path(path)
    path_to = Path(target) if target else path_from.with_suffix("")
    shutil.unpack_archive(path_from, path_to)
    util.info(f" EXTRACT: '{path_from}' → '{path_to}'")
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
    util.info(f" ZIP: '{path}' → '{output_path}.zip'")


def zip_folder_with_limit(path: str | PathLike[str], output_path: str,
                          limit_bytes: int | None = None) -> int:
    limit_bytes = config.get("moodle.file_upload_limit_bytes") if limit_bytes is None else limit_bytes

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
                util.info(f" ZIP: '{file}' → '{output_path}{suffix}.zip'")

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


def delete_folder(folder: Path) -> None:
    if folder.exists():
        shutil.rmtree(folder)
        util.info(f" DELETE: '{folder}'")
    if folder.resolve() in temporary_folders:
        temporary_folders.remove(folder.resolve())


def cleanup() -> None:
    for folder in reversed(temporary_folders):
        delete_folder(folder)


def find_all_paths(keyword: str, path: str | PathLike[str], replace_non_ascii: bool = True) -> List[Path]:
    if replace_non_ascii:
        keyword = ''.join([c if ord(c) < 128 else '*' for c in keyword])
    return list(Path(path).rglob(f"{keyword}"))


def find_single_path(keyword: str, path: str | PathLike[str], replace_non_ascii: bool = True,
                     filter_fun: Callable[[Path], bool] | None = None) -> Path:
    results = find_all_paths(keyword, path, replace_non_ascii)
    if filter_fun:
        results = list(filter(filter_fun, results))

    i = 0
    if not results:
        util.error(f"No results found for '{keyword}'")
    elif len(results) > 1:
        i = util.choose_index(results, f"Multiple results found for '{keyword}':", "Select the correct result:")

    return results[i]


def parse_groups_file(path: str | PathLike[str]) -> List[List[str]] | None:
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


def _flat_copy_all(path_from: Path, path_to: Path, name_prefix: str, name_suffix: str, _count: int = 0) -> int:
    files_in_folder = sorted(path_from.glob("*"))
    for i, file in enumerate(files_in_folder):
        i += 1
        if not file.is_dir():
            extension = file.suffix
            shutil.copy(file, path_to / f"{name_prefix}{i}{name_suffix}{extension}")
            util.info(f" COPY: '{file.name}' → '{name_prefix}{i}{name_suffix}{extension}'")
            _count += 1
        else:
            sub_count = _flat_copy_all(file, path_to, name_prefix + f"{i}-", name_suffix)
            _count += sub_count
    return _count


def extract_theoretical_submissions(groups: List[List[str]], path_from: str | PathLike[str], path_to: str) -> List[int]:
    create_folder(path_to)
    path_to = Path(path_to)
    path_from = Path(path_from)
    extracted = []

    for groupIdx, group in enumerate(groups):
        for memberIdx, member in enumerate(group):
            submission_folder = find_single_path(f"*{member.replace(' ', '*')}*{config.get("moodle.submission_keyword")}*", path_from)
            extract_all_within(submission_folder)
            moodle_id = submission_folder.name.split("_")[1]

            prefix = f"Submission_Gr{groupIdx + 1}{util.index_to_ascii(memberIdx)}_{member}_{moodle_id}_File "
            suffix = f"_{config.get("filenames.points_placeholder")}pts"

            count = _flat_copy_all(submission_folder, path_to, prefix, suffix)
            if count > 0:
                extracted.append(moodle_id)
            else:
                util.warning(f"Did not find any files for member {member} (id: {moodle_id})", "Member will be skipped.")

    return extracted


def find_pex_submission(id: int, submissions: str | PathLike[str]) -> Path:
    submission_folder = find_single_path(f"*{id}*{config.get("moodle.submission_keyword")}", submissions)
    return find_single_path("*.ipynb", submission_folder,
                            filter_fun=lambda p: not p.name.endswith("-checkpoint.ipynb") and not p.name.startswith("._"))


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
    feedback_files = find_all_paths(f"*_{keyword}_*", path)

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
    feedback_files = find_all_paths(f"*_{keyword}_*", path_from)
    copied = 0

    for file in feedback_files:
        student_name, student_id, file_id, points = parse_submission_filename(file)
        if points is None:
            util.warning(f"No points found inside '{file.name}'.", "File will not be included as feedback.")
            continue

        filename = f"{student_name}_{student_id}_{config.get("moodle.submission_keyword")}_{config.get("filenames.feedback_filename_prefix")}"
        if submission_name:
            filename += f"_{submission_name}"
        filename += f"_(Datei {file_id})_{config.get("initials")}{file.suffix}"

        shutil.copy2(file, path_to / filename)
        copied += 1
        util.info(f" COPY: '{file}' → '{path_to / filename}'")

    return copied


def open_file(path: str | PathLike[str]) -> None:
    path = Path(path)
    # taken from: https://stackoverflow.com/questions/434597/open-document-with-default-os-application-in-python-both-in-windows-and-mac-os
    # and https://stackoverflow.com/questions/5772873/python-spawn-off-a-child-subprocess-detach-and-exit
    if platform.system() == 'Darwin':  # macOS
        subprocess.Popen(('open', path), start_new_session=True)
    elif platform.system() == 'Windows':  # Windows
        subprocess.Popen(('start', '', path), creationflags=subprocess.DETACHED_PROCESS, shell=True)
    else:  # linux variants
        subprocess.Popen(('xdg-open', path), start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def replace_in_file(path: str | PathLike[str], old: str, replacement: str) -> None:
    path = check_path(path)
    with open(path, 'r') as f:
        content = f.read()

    content = content.replace(old, replacement)

    with open(path, 'w') as f:
        f.write(content)