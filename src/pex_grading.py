import json
import shutil
from pathlib import Path
import math
from typing import Tuple, List

import util
import file_mgmt
from config import config
import grading_sheet

class PexFeedback:
    test_output: str = ""
    additional_feedback: str = ""
    points: float = 0.0

    def __init__(self, points: str | float, test_output: str, additional_feedback: str) -> None:
        self.test_output = test_output.strip()
        self.additional_feedback = additional_feedback.strip()
        try:
            self.points = float(points)
        except ValueError:
            self.points = float("NaN")


    def __str__(self) -> str:
        return ( f"Test output:\n{self.test_output}\n\n"
                 f"Additional feedback:\n{self.additional_feedback or "(none)"}\n\n"
                 f"Points: {self.points}\n"
                 f"Feedback is {"OK" if self.valid() else "INVALID!"}" )

    def valid(self) -> bool:
        return not math.isnan(self.points) and self.points >= 0 and len(self.test_output) > 0

    def set_points(self, points: float) -> None:
        self.points = points

    def set_test_output(self, test_output: str) -> None:
        self.test_output = test_output

    def set_additional_feedback(self, additional_feedback: str) -> None:
        self.additional_feedback = additional_feedback

    def replace_with(self, other: 'PexFeedback') -> None:
        self.points = other.points
        self.test_output = other.test_output
        self.additional_feedback = other.additional_feedback


    def as_html(self) -> str:
        html = ""
        html += f"<p><span style=\"text-decoration: underline;\">Ausgabe der automatischen Tests</span>:</p>"
        html += f"<pre class=\"language-markup\"><code>{config.get("pex.html_magic_comment")}{self.test_output}{config.get("pex.html_magic_comment")}</code></pre>"

        if self.additional_feedback:
            feedback_html = grading_sheet.encode_comment(self.additional_feedback.splitlines())
            html += f"<p><span style=\"text-decoration: underline;\">Zusätzliches Feedback</span>:</p>"
            html += f"{config.get("pex.html_magic_comment")}{feedback_html}{config.get("pex.html_magic_comment")}"

        return html

    @classmethod
    def from_html(cls, html: str, points: float):
        html = html.split(config.get("pex.html_magic_comment"))
        try:
            test_output = html[1].strip()
        except IndexError:
            test_output = ""

        try:
            encoded_comment = html[3].strip()
            decoded_comment = grading_sheet.decode_comment(encoded_comment)
            additional_feedback = '\n'.join(decoded_comment)
        except IndexError:
            additional_feedback = ""

        return cls(points, test_output, additional_feedback)


    def as_editable_text(self, header: str) -> List[str]:
        text = ""
        if header:
            text += f"{header}\n"
        text += f"# Lines starting with '#' are ignored. Do not remove lines starting with '{config.get("pex.text_divider")}'.\n"
        text += f"\n"
        text += f"# Test Output:\n{config.get("pex.text_divider")}\n{self.test_output}\n{config.get("pex.text_divider")}\n"
        text += f"\n"
        text += f"# Additional Feedback:\n{config.get("pex.text_divider")}\n{self.additional_feedback}\n{config.get("pex.text_divider")}\n"
        text += f"\n"
        text += f"# Points:\n{config.get("pex.text_divider")}\n{self.points}\n{config.get("pex.text_divider")}\n"

        return text.splitlines()

    @classmethod
    def from_editable_text(cls, text: List[str]):
        # filter empty lines and comments
        filtered_lines = filter(lambda l: len(l) > 0 and not l.startswith('#'), text)
        text = '\n'.join(filtered_lines)

        text = text.split(config.get("pex.text_divider"))

        try:
            test_output = text[1].strip()
            additional_feedback = text[3].strip()
            points = text[5].strip()
        except IndexError:
            test_output = additional_feedback = points = ""

        return cls(points, test_output, additional_feedback)


class PexGrader:
    pex_name: str = ""
    grading_package: Path | None = None

    def __init__(self, grading_package: Path) -> None:
        try:
            self.pex_name = grading_package.stem.split("_")[1]
        except IndexError:
            util.error(f"Unexpected name of grading package '{grading_package.name}'. Expected something like 'sc_pexN_grading'.")

        self.grading_package = file_mgmt.unzip_if_not_folder(grading_package)

        util.info("Preparing Docker image ...", always_display=True)
        util.run_command(f"docker build -t {self.pex_name}-docker --build-arg exercise={self.pex_name} {self.grading_package}")


    def grade(self, submission: Path) -> PexFeedback:
        # create folder structure needed for docker container / grading scripts
        grading_folder = file_mgmt.create_temporary_folder()
        grading_source = grading_folder / Path(f"{self.pex_name}/group-{config.get("pex.docker_group_name")}")
        grading_target = grading_folder / Path(f"{self.pex_name}-grading")

        file_mgmt.create_folder(grading_source)
        file_mgmt.create_folder(grading_target)
        shutil.copy2(submission, grading_source / f"sc-{self.pex_name}.ipynb")

        # initiate grading by starting the docker container
        util.info(f"Grading submission '{submission}'...")
        success, stdout = util.run_potentially_failing_command( "docker run --rm "
                         f"--mount type=bind,source={grading_folder.resolve()},target=/submissions "
                         f"--mount type=bind,source={grading_target.resolve()},target=/grading_schemes "
                         f"--name {self.pex_name}-docker-group-{config.get("pex.docker_group_name")} "
                         f"{self.pex_name}-docker {self.pex_name} {config.get("pex.docker_group_name")}")

        if success:
            # re-print stdout
            util.info(stdout, always_display=True, append_full_stop=False)

            # parse feedback file
            feedback_file = file_mgmt.find_single_path('*.json', grading_target)
            with open(feedback_file, 'r') as f:
                d = json.load(f)
            grade_text, reached_points = _json_to_txt(d)
            reached_points = float(reached_points)
        else:
            util.info(f"Automatic grading FAILED:\n\n{stdout}", always_display=True, append_full_stop=False)
            grade_text = f"Failed to run tests:\n{stdout}\n(end of output)"
            reached_points = 0

        # cleanup created folder structure
        file_mgmt.delete_folder(grading_folder)

        # return a new Feedback object
        return PexFeedback(reached_points, grade_text, "")


    def open_solution(self) -> None:
        solution_path = file_mgmt.find_single_path("*.ipynb", self.grading_package / self.pex_name / "python")
        _notebook_vscode_fix(solution_path)
        file_mgmt.open_file(solution_path)

    def cleanup(self) -> None:
        util.info("Cleaning up Docker image ...", always_display=True)
        util.run_command(f"docker rmi {self.pex_name}-docker")
        file_mgmt.cleanup()



def open_submission(path: Path) -> None:
    _notebook_vscode_fix(path)
    file_mgmt.open_file(path)


def grade_pex_group(group: List[str], group_ids: List[int], path_submissions: Path,
                    grader: PexGrader, gs: grading_sheet.GradingSheet, console_header: str | None = None) -> int:
    sample_id = group_ids[0]
    current_feedback = PexFeedback("", "", "")
    submission = file_mgmt.find_pex_submission(sample_id, path_submissions)
    graded = True
    finished = False
    updated_grades = 0

    def grade():
        util.clear_console(console_header)
        util.info(f"Running automatic tests for group {group} ...", always_display=True)
        new_feedback = grader.grade(submission)
        current_feedback.set_points(new_feedback.points)
        current_feedback.set_test_output(new_feedback.test_output)
        util.wait_for_user()

    def edit_feedback():
        feedback_text = current_feedback.as_editable_text(f"# Editing feedback for group {group}:")
        file_mgmt.create_file(config.get("filenames.edit_feedback_file"), feedback_text)
        file_mgmt.open_file(config.get("filenames.edit_feedback_file"))
        util.wait_for_user("Please edit the feedback, save the file and press ENTER to continue ...")

        new_feedback = PexFeedback.from_editable_text(file_mgmt.read_file(config.get("filenames.edit_feedback_file")))
        file_mgmt.delete_file(config.get("filenames.edit_feedback_file"))
        current_feedback.replace_with(new_feedback)


    for id in group_ids:
        if gs.get_points(id) is None or gs.get_comment(id) is None:
            graded = False

    if graded:
        util.clear_console(console_header)
        util.info(f"Group {group} already has a feedback in the grading scheme.", always_display=True)
        match util.choose_option({"s", "l", "d"}, "s", "The following options are available:\n"
                                                       "  's': skip this group\n"
                                                       "  'l': load feedback from grading scheme\n"
                                                       "  'd': discard feedback from grading scheme and regrade\n"
                                                       "What would you like to do?"):
            case "s":
                return 0

            case "l":
                loaded_feedback = PexFeedback.from_html(gs.get_comment(sample_id, decode=False), gs.get_points(sample_id))
                current_feedback.replace_with(loaded_feedback)

            case "d":
                graded = False

            case _:
                util.error("Internal error: 'choose_option' is misbehaving.")

    if not graded:
        grade()


    while not finished:
        util.clear_console(console_header)
        util.info(f"Current feedback for group {group}:\n\n{current_feedback}\n", always_display=True, append_full_stop=False)
        match util.choose_option({"osol", "osub", "r", "e", "f"}, "f", "The following options are available:\n"
                                                                 "  'osol': open solution\n"
                                                                 "  'osub': open submission\n"
                                                                 "  'r': regrade\n"
                                                                 "  'e': edit feedback\n"
                                                                 "  'f': finish grading and add to grading sheet\n"
                                                                 "What would you like to do?"):
            case "osub":
                open_submission(submission)

            case "osol":
                grader.open_solution()

            case "r":
                grade()

            case "e":
                edit_feedback()

            case "f":
                if not current_feedback.valid():
                    util.warning("Current feedback is invalid.", "Please try regrading or editing the feedback.")
                    util.wait_for_user()
                    continue

                for id in group_ids:
                    gs.set_points(id, current_feedback.points)
                    gs.set_comment(id, current_feedback.as_html(), encode=False)

                    feedback_footer = config.get("moodle.feedback_footer")
                    feedback_footer_with_initials = list(
                        map(lambda s: s.format(config.get("initials")), feedback_footer))
                    gs.append_comment(id, feedback_footer_with_initials)
                    updated_grades += 1
                finished = True

            case _:
                util.error("Internal error: 'choose_option' is misbehaving.")

    return updated_grades


def _json_to_txt(d: dict) -> Tuple[str, str]:
    #group_name = d['group_num']
    reached_pts, total_pts = d['total']['reached'], d['total']['max']
    #grade_text = f'Grade for group {group_name}\n'
    grade_text = f'Total Points: {reached_pts} out of {total_pts}\n'
    for fct in d['tests']:
        for test_case in ['public', 'private']:
            if test_case in d['tests'][fct]['points']:
                pts = d['tests'][fct]['points'][test_case]
                comment = d['tests'][fct][test_case]['comment']
                grade_text += f'[{fct}] {test_case} test: {pts} points'
                if comment:
                    grade_text += f'; comment: {comment}'
                grade_text += '\n'
    return grade_text, reached_pts


def _notebook_vscode_fix(notebook: Path) -> None:
    file_mgmt.replace_in_file(notebook, "%matplotlib notebook", "%matplotlib tk")
    file_mgmt.replace_in_file(notebook, "matplotlib.use(\"nbAgg}\")", "matplotlib.use('TkAgg')")