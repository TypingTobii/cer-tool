import itertools
from argparse import Namespace
from functools import reduce
from pathlib import Path

from cer_tool import config, file_mgmt, grading_sheet, util, pex_grading


def prepare(args: Namespace) -> None:
    path_groups: str = args.groups
    path_submissions: str = args.submissions
    path_out: str = args.out

    file_mgmt.check_path(path_groups)
    file_mgmt.check_path(path_submissions)

    # extract if needed
    extracted_submissions = file_mgmt.unzip_if_not_folder(path_submissions)

    # parse groups
    groups = file_mgmt.parse_groups_file(path_groups)

    # copy
    extracted = file_mgmt.extract_theoretical_submissions(groups, extracted_submissions, path_out)
    file_mgmt.cleanup()
    util.info(f"Successfully extracted {len(extracted)} of {reduce(lambda acc, group: acc + len(group), groups, 0)} submissions to '{path_out}'", always_display=True)


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
    info_line = f"# Editing comment for {gs.get_name(id)} (id: {id}, {gs.get_points(id) or 'N/A'} points):\n"
    file_mgmt.create_file(config.get("filenames.edit_feedback_file"), [info_line] + feedback_current)

    # open text editor to edit feedback
    file_mgmt.open_file(config.get("filenames.edit_feedback_file"))
    file_mgmt.open_file(config.get("filenames.edit_feedback_file"))

    # wait until the user has finished
    util.wait_for_user("Please edit the comment, save the file and press ENTER to continue...")

    # retrieve changes
    feedback_new_raw = file_mgmt.read_file(config.get("filenames.edit_feedback_file"))
    feedback_new = list(filter(lambda l: len(l) > 0 and not l.startswith('#'), feedback_new_raw))
    file_mgmt.delete_file(config.get("filenames.edit_feedback_file"))
    if grading_sheet.encode_comment(feedback_new) == grading_sheet.encode_comment(feedback_current):
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
    feedback_folder = file_mgmt.create_temporary_folder()

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
        files_copied = file_mgmt.copy_feedback_files(str(id), path_feedback, feedback_folder, submission_name)
        if files_copied == 0:
            util.warning(f"No feedback files copied for student '{member}' (id: {id}).", "Student will be skipped.")
            continue

        # insert points and feedback into the grading sheet
        gs.set_points(id, points)
        feedback_footer = config.get("moodle.feedback_footer")
        feedback_footer_with_initials = list(map(lambda s: s.format(config.get("initials")), feedback_footer))
        gs.append_comment(id, feedback_footer_with_initials)

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
    created_zips = file_mgmt.zip_folder_with_limit(feedback_folder, out_feedback)
    util.info(f"{created_zips} zip files created.", True)
    file_mgmt.cleanup()


def grade_pex(args: Namespace) -> None:
    path_grading_package: Path = file_mgmt.check_path(args.grading_package)
    path_groups: Path = file_mgmt.check_path(args.groups)
    path_submissions: Path = file_mgmt.check_path(args.submissions)
    path_grading_sheet: Path = file_mgmt.check_path(args.grading_sheet)
    if args.out_grading_sheet:
        out_grading_sheet: Path = Path(args.out_grading_sheet)
    else:
        out_grading_sheet: Path = path_grading_sheet

    grader = pex_grading.PexGrader(path_grading_package)
    gs = grading_sheet.GradingSheet(path_grading_sheet)
    groups = file_mgmt.parse_groups_file(path_groups)
    member_ids = dict(map(lambda name: (name, gs.select_participant(name)), list(itertools.chain(*groups)) ))
    gs.filter(list(member_ids.values()))

    # extract submissions
    path_submissions = file_mgmt.unzip_if_not_folder(path_submissions)
    file_mgmt.extract_all_within(path_submissions)

    updated_grades = 0
    for i, group in enumerate(groups):
        title = f"Grading group {i + 1} of {len(groups)} ({i / len(groups) * 100:.0f} % done)"
        updated_grades += pex_grading.grade_pex_group(group,
                                                      list(map(lambda name: member_ids[name], group)),
                                                      path_submissions, grader, gs,
                                                      console_header=f"{title}\n{len(title) * '─'}")

        gs.save(out_grading_sheet)
        if i != len(groups) - 1:
            util.info("", always_display=True)
            answer = util.choose_option({"y", "n"}, "y", "Continue with the next group?")
            if answer != "y":
                break

    util.clear_console()
    util.info(f"Grading finished. Updated {updated_grades} of {len(member_ids)} grades.", always_display=True)
    util.info("", always_display=True)

    util.wait_for_user("Please close all opened submission/grading files and press ENTER to continue ...")
    grader.cleanup()
    file_mgmt.cleanup()


def config_list(_: Namespace):
    util.info(f"Current configuration:\n\n{config.as_str()}", always_display=True, append_full_stop=False)

def config_edit(_: Namespace):
    util.info(f"Current configuration:\n\n{config.as_str()}", always_display=True, append_full_stop=False)
    util.info("", always_display=True)

    while True:
        util.info("Enter a setting to edit or press ENTER to finish", always_display=True)
        key = input("  key = ")
        if not key:
            break
        if not config.key_exists(key):
            util.warning(f"Setting '{key}' does not exist.", "Please try again.")
            util.info("", always_display=True)
            continue

        util.info("Enter the new value for the setting. Please use JSON notation, i.e. double-quote strings", always_display=True)
        val = input("value = ")
        try:
            config.set_json(key, val)
        except ValueError as err:
            util.warning(f"{err.args[0]}", "Please try again.")
            util.info("", always_display=True)
            continue

        util.info("", always_display=True)

    config.save()
    util.info("", always_display=True)
    util.info("Configuration saved.", always_display=True)
    util.info(f"Updated configuration:\n\n{config.as_str()}", always_display=True, append_full_stop=False)