from argparse import Namespace
from pathlib import Path
from typing import List

import config
import file_mgmt
import util
import argparse

from file_mgmt import check_path


def prepare(args: Namespace) -> None:
    path_groups: str = args.groups
    path_submissions: str = args.submissions
    path_target: str = args.target

    check_path(path_groups)
    check_path(path_submissions)

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
    print("Hello from feedback")
    return


def finish(args: Namespace) -> None:
    print("Hello from finish")
    return


if __name__ == "__main__":
    parser_main = argparse.ArgumentParser(prog="cer-tool", description="Simplify grading upload to Moodle.")
    subparsers = parser_main.add_subparsers(required=True,
                                            title="subcommands", description="The following commands are available:",
                                            help="command to be executed")

    # prepare
    parser_prepare = subparsers.add_parser("prepare", aliases=["pp"],
                                           help="gather and rename submission files, s.t. they can be easily graded with Notability")
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
                                            help="add or edit textual feedback for a given student on the grading sheet")
    # TODO
    # parser_feedback.add_argument(...)
    parser_feedback.set_defaults(func=edit_feedback)

    # finish
    parser_finish = subparsers.add_parser("finish", aliases=["f"],
                                          help="export feedback zip and grading sheet to upload to moodle")
    # TODO
    # parser_finish.add_argument(...)
    parser_finish.set_defaults(func=finish)

    args = parser_main.parse_args()
    args.func(args)
