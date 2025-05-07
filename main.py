from argparse import Namespace
from pathlib import Path
from typing import List

import config
import file_mgmt
import grading_sheet
import util
import argparse


def prepare(args: Namespace) -> None:
    path_groups: str = args.groups
    path_submissions: str = args.submissions
    path_target: str = args.target

    file_mgmt.check_path(path_groups)
    file_mgmt.check_path(path_submissions)

    # extract if needed
    extracted = file_mgmt.unzip_if_not_folder(path_submissions)

    # parse groups
    groups = file_mgmt.parse_groups_file(path_groups)

    # copy
    if extracted:
        file_mgmt.extract_submissions(groups, config.FOLDER_NAME_UNZIP, path_target)
        file_mgmt.cleanup()
    else:
        file_mgmt.extract_submissions(groups, path_submissions, path_target)


def edit_feedback(args: Namespace) -> None:
    path_grading_sheet: str = args.grading_sheet
    keyword: str = args.student_name

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
    gs.save()


def finish(args: Namespace) -> None:
    print("Hello from finish")
    print(f"My args are: {args}")
    return


if __name__ == "__main__":
    parser_main = argparse.ArgumentParser(prog="cer-tool", description="Simplify grading upload to Moodle.")
    subparsers = parser_main.add_subparsers(required=True,
                                            title="subcommands", description="The following commands are available:",
                                            help="command to be executed")

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

    parser_prepare.add_argument("-t", "--target", required=False, default="./submissions",
                                help="custom output folder")

    # edit_feedback
    parser_feedback = subparsers.add_parser("edit_feedback", aliases=["efb"],
                                            help="add or edit textual feedback for a given student on the grading sheet",
                                            description="add or edit textual feedback for a given student on the grading sheet")
    parser_feedback_group_input = parser_feedback.add_argument_group("input files")
    parser_feedback_group_input.add_argument("-t", "--grading-sheet", required=True,
                                             help="path to the grading sheet to edit")
    parser_feedback.add_argument("student_name", help="partial or complete name of the student whose feedback should be edited")
    parser_feedback.set_defaults(func=edit_feedback)

    # finish
    parser_finish = subparsers.add_parser("finish", aliases=["f"],
                                          help="export feedback zip and grading sheet to upload to moodle",
                                          description="export feedback zip and grading sheet to upload to moodle")
    # TODO
    # parser_finish.add_argument(...)
    parser_finish.set_defaults(func=finish)

    args = parser_main.parse_args()
    args.func(args)
