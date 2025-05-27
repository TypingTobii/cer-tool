import itertools
import argparse
from argparse import Namespace
from pathlib import Path

import config
import file_mgmt
import grading_sheet
import util


def prepare(args: Namespace) -> None:
    path_groups: str = args.groups
    path_submissions: str = args.submissions
    path_out: str = args.out

    file_mgmt.check_path(path_groups)
    file_mgmt.check_path(path_submissions)

    # extract if needed
    extracted = file_mgmt.unzip_if_not_folder(path_submissions)

    # parse groups
    groups = file_mgmt.parse_groups_file(path_groups)

    # copy
    if extracted:
        file_mgmt.extract_submissions(groups, config.FOLDER_NAME_ZIP, path_out)
        file_mgmt.cleanup()
    else:
        file_mgmt.extract_submissions(groups, path_submissions, path_out)


def edit_feedback(args: Namespace) -> None:
    path_grading_sheet: str = args.grading_sheet
    keyword: str = ' '.join(args.student_name)
    out: str = args.out or args.grading_sheet

    file_mgmt.check_path(path_grading_sheet)

    gs = grading_sheet.GradingSheet(path_grading_sheet)

    # find/select student
    id = gs.select_participant(keyword)

    # create a new file with current feedback
    feedback_current = gs.get_comment(id)
    info_line = f"# (DO NOT DELETE THIS LINE) Editing comment for {gs.get_name(id)} (id: {id}, {gs.get_points(id) or 'N/A'} points):\n"
    file_mgmt.create_file(config.FILE_NAME_COMMENT, [info_line] + feedback_current)

    # open text editor to edit feedback
    file_mgmt.open_file(config.FILE_NAME_COMMENT)

    # wait until the user has finished
    util.wait_for_user("Please edit the comment, save the file and press ENTER to continue...")

    # retrieve changes
    feedback_new = file_mgmt.read_file(config.FILE_NAME_COMMENT)[1:]
    file_mgmt.delete_file(config.FILE_NAME_COMMENT)
    if grading_sheet._encode_comment(feedback_new) == grading_sheet._encode_comment(feedback_current):
        util.warning("No changes to the comment.")
        return

    # save changes
    gs.set_comment(id, feedback_new)
    gs.save(out)


def finish(args: Namespace) -> None:
    path_groups: str = args.groups
    path_grading_sheet: str = args.grading_sheet
    path_feedback: str = args.feedback
    out_feedback: str = args.out_feedback
    submission_name: str = args.submission_name
    out_grading_sheet: str = args.out_grading_sheet
    if not out_grading_sheet:
        p = Path(path_grading_sheet)
        out_grading_sheet = str(p.with_stem(f"_out_{p.stem}"))

    file_mgmt.check_path(path_groups)
    file_mgmt.check_path(path_grading_sheet)
    file_mgmt.check_path(path_feedback)

    gs = grading_sheet.GradingSheet(path_grading_sheet)
    groups = file_mgmt.parse_groups_file(path_groups)
    members = list(itertools.chain(*groups))

    # create a temporary folder for feedback files
    file_mgmt.create_folder(config.FOLDER_NAME_ZIP)

    processed_successfully = 0
    updated_ids = []
    for member in members:
        # get member's id
        id = gs.select_participant(member)

        # process member's points
        points = file_mgmt.get_points_from_path(str(id), path_feedback)
        if points is None:
            util.warning(f"Got not points for student '{member}' (id: {id}).", "Student will be skipped.")
            continue

        # process feedback file/s
        files_copied = file_mgmt.copy_feedback_files(str(id), path_feedback, config.FOLDER_NAME_ZIP, submission_name)
        if files_copied == 0:
            util.warning(f"No feedback files copied for student '{member}' (id: {id}).", "Student will be skipped.")
            continue

        # insert points and feedback into the grading sheet
        gs.set_points(id, points)
        gs.append_comment(id, config.MOODLE_FEEDBACK_STANDARD_TEXT)

        processed_successfully += 1
        updated_ids.append(id)
        util.info(f"Successfully processed student {member:>25} (id: {id}): Found {points:6.2f} points, copied {files_copied} file/s.", True)

    util.info("", True)
    util.info(f"{processed_successfully} of {len(members)} students processed successfully.", True)

    # save changes to the grading sheet
    gs.filter(updated_ids)
    gs.save(out_grading_sheet)

    # create a zip file with feedback files and cleanup
    util.info("", True)
    util.info("Creating zip file/s...", True)
    created_zips = file_mgmt.zip_folder_with_limit(config.FOLDER_NAME_ZIP, out_feedback)
    util.info(f"{created_zips} zip files created.", True)
    file_mgmt.cleanup()