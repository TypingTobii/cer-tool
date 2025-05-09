import itertools
import re
from argparse import Namespace

import config
import file_mgmt
import grading_sheet
import util
import argparse


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
    out_grading_sheet: str = args.out_grading_sheet or re.sub(r"(.*).csv", r"_out_\1.csv", path_grading_sheet)

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
        if not points:
            util.warning(f"Got not points for student '{member}' (id: {id}).", "Student will be skipped.")
            continue

        # process feedback file/s
        files_copied = file_mgmt.copy_feedback_files(str(id), path_feedback, config.FOLDER_NAME_ZIP)
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
    file_mgmt.zip_folder(config.FOLDER_NAME_ZIP, out_feedback)
    file_mgmt.cleanup()


if __name__ == "__main__":
    parser_main = argparse.ArgumentParser(prog="cer-tool", description="Simplify grading upload to Moodle.")
    subparsers = parser_main.add_subparsers(required=True,
                                            title="subcommands", description="The following commands are available:",
                                            help="command to be executed")
    parser_main.add_argument("-v", "--verbose", action="store_true", required=False,
                             help="output a message if a change to the file system is caused")

    # prepare
    parser_prepare = subparsers.add_parser("prepare", aliases=["pp"],
                                           help="gather and rename submission files, s.t. they can be easily graded with Notability",
                                           description="gather and rename submission files, s.t. they can be easily graded with Notability")
    parser_prepare.set_defaults(func=prepare)

    parser_prepare_group_input = parser_prepare.add_argument_group("input files")
    parser_prepare_group_input.add_argument("-g", "--groups", required=True,
                                            help="path to text file containing groups to correct")
    parser_prepare_group_input.add_argument("-s", "--submissions", required=True,
                                            help="path to a zip file or a folder containing the submissions")

    parser_prepare.add_argument("-o", "--out", required=False, default="./submissions",
                                help="custom output folder")

    # edit_feedback
    parser_feedback = subparsers.add_parser("edit_feedback", aliases=["efb"],
                                            help="add or edit textual feedback for a given student on the grading sheet",
                                            description="add or edit textual feedback for a given student on the grading sheet")
    parser_feedback_group_input = parser_feedback.add_argument_group("input files")
    parser_feedback_group_input.add_argument("-t", "--grading-sheet", required=True,
                                             help="path to the grading sheet to edit")
    parser_feedback.add_argument("-o", "--out", required=False, help="custom output file (default: overwrite input file)")
    parser_feedback.add_argument("student_name", nargs='+',
                                 help="partial or complete name of the student whose feedback should be edited")
    parser_feedback.set_defaults(func=edit_feedback)

    # finish
    parser_finish = subparsers.add_parser("finish", aliases=["fs"],
                                          help="export feedback zip and grading sheet to upload to moodle",
                                          description="export feedback zip and grading sheet to upload to moodle")

    parser_finish_group_input = parser_finish.add_argument_group("input files")
    parser_finish_group_input.add_argument("-g", "--groups", required=True,
                                           help="path to text file containing groups to correct")
    parser_finish_group_input.add_argument("-t", "--grading-sheet", required=True,
                                           help="path to the grading sheet to edit")
    parser_finish_group_input.add_argument("-f", "--feedback", required=False, default="./submissions",
                                           help="path to the folder containing the corrected submissions")

    parser_finish.add_argument("-of", "--out-feedback", required=False, default="./_out_feedback.zip",
                               help="custom path for output feedback zip (default: ./_out_feedback.zip)")
    parser_finish.add_argument("-ot", "--out-grading-sheet", required=False,
                               help="custom path for output grading sheet (default: ./_out_GRADING_SHEET.csv)")
    parser_finish.set_defaults(func=finish)

    args = parser_main.parse_args()

    config.VERBOSE = args.verbose
    args.func(args)
