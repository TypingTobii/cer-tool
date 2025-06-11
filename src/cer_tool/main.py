import argparse

from cer_tool import command_handlers, file_mgmt, util
from cer_tool.flags import flags


def main():
    parser_main = argparse.ArgumentParser(prog="cer-tool", description="Simplify grading upload to Moodle.")
    subparsers = parser_main.add_subparsers(required=True,
                                            title="subcommands", description="The following commands are available:",
                                            help="command to be executed")
    parser_main.add_argument("-v", "--verbose", action="store_true", required=False,
                             help="output a message for each change caused by cer-tool")

    # prepare
    parser_prepare = subparsers.add_parser("prepare", aliases=["pp"],
                                           help="gather and rename submission files, s.t. they can be easily graded with a PDF annotator",
                                           description="gather and rename submission files, s.t. they can be easily graded with a PDF annotator")
    parser_prepare.set_defaults(func=command_handlers.prepare)

    parser_prepare_group_input = parser_prepare.add_argument_group("input files")
    parser_prepare_group_input.add_argument("-g", "--groups", required=True,
                                            help="path to text file containing groups to correct")
    parser_prepare_group_input.add_argument("-s", "--submissions", required=True,
                                            help="path to a zip file or a folder containing the submissions")

    parser_prepare.add_argument("-o", "--out", required=False, default="./submissions",
                                help="custom output folder")

    # edit_feedback
    parser_feedback = subparsers.add_parser("edit-feedback", aliases=["efb"],
                                            help="add or edit textual feedback for a given student on the grading sheet",
                                            description="add or edit textual feedback for a given student on the grading sheet")
    parser_feedback_group_input = parser_feedback.add_argument_group("input files")
    parser_feedback_group_input.add_argument("-t", "--grading-sheet", required=True,
                                             help="path to the grading sheet to edit")
    parser_feedback.add_argument("-o", "--out", required=False, help="custom output file (default: overwrite input file)")
    parser_feedback.add_argument("student_name", nargs='+',
                                 help="partial or complete name of the student whose feedback should be edited")
    parser_feedback.set_defaults(func=command_handlers.edit_feedback)

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
    parser_finish.add_argument("-sn", "--submission-name", required=False,
                               help="name of the submission to be included in the feedback file names (default: '')")
    parser_finish.set_defaults(func=command_handlers.finish)

    # grade_pex
    parser_pex = subparsers.add_parser("grade-pex", aliases=["pex"],
                                       help="semi-automatically grade all assigned programming exercise submissions",
                                       description="semi-automatically grade all assigned programming exercise submissions")

    parser_pex_group_input = parser_pex.add_argument_group("input files")
    parser_pex_group_input.add_argument("-p", "--grading-package", required=True,
                                        help="path to an archive or a folder containing the scripts for automatic grading")
    parser_pex_group_input.add_argument("-g", "--groups", required=True,
                                        help="path to text file containing groups to correct")
    parser_pex_group_input.add_argument("-s", "--submissions", required=True,
                                        help="path to an archive or a folder containing the submissions")
    parser_pex_group_input.add_argument("-t", "--grading-sheet", required=True,
                                        help="path to the grading sheet to edit")

    parser_pex.add_argument("-ot", "--out-grading-sheet", required=False,
                            help="custom path for output grading sheet (default: overwrite input file)")
    parser_pex.set_defaults(func=command_handlers.grade_pex)

    # config
    parser_config = subparsers.add_parser("config",
                                          help="view or edit the configuration of this tool",
                                          description="view or edit the configuration of this tool")
    config_subparsers = parser_config.add_subparsers(required=True,
                                                     title="config subcommands", description="The following commands are available:",
                                                     help="command to be executed")

    # config-list
    parser_config_list = config_subparsers.add_parser("list", aliases=["l"],
                                                      help="list the current configuration", description="list the current configuration")
    parser_config_list.set_defaults(func=command_handlers.config_list)

    # config-edit
    parser_config_edit = config_subparsers.add_parser("edit", aliases=["e"],
                                                      help="edit the current configuration",
                                                      description="edit the current configuration")
    parser_config_edit.set_defaults(func=command_handlers.config_edit)


    args = parser_main.parse_args()

    flags["verbose"] = args.verbose
    try:
        args.func(args)
    except KeyboardInterrupt:
        file_mgmt.cleanup()
        util.warning("Aborted by user.", "Some temporary files or folders may have been left.")


if __name__ == '__main__':
    main()