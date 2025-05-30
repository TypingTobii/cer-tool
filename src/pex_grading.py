import json
import shutil
from pathlib import Path
import math
from typing import Tuple

import util
import file_mgmt
import config
import grading_sheet


class PexFeedback:
    test_output: str = ""
    additional_feedback: str = ""
    points: float = 0.0
    valid: bool = False

    def __init__(self, points: str | float, test_output: str, additional_feedback: str) -> None:
        self.test_output = test_output.strip()
        self.additional_feedback = additional_feedback.strip()
        try:
            self.points = float(points)
        except ValueError:
            self.points = float("NaN")

        self.valid = not math.isnan(self.points) and self.points > 0 and len(test_output) > 0


    def __str__(self) -> str:
        str = "valid" if self.valid else "invalid"
        str += f" feedback: {{ Total points: {self.points}, Test output: '{self.test_output}', Additional feedback: {f"'{self.additional_feedback}'" or "(none)"} }}"
        return str

    def as_html(self) -> str:
        html = ""
        html += f"<p><span style=\"text-decoration: underline;\">Ausgabe der automatischen Tests</span>:</p>"
        html += f"<pre class=\"language-markup\"><code>{config.PEX_HTML_MAGIC_COMMENT}{self.test_output}{config.PEX_HTML_MAGIC_COMMENT}</code></pre>"

        if self.additional_feedback:
            feedback_html = grading_sheet.encode_comment(self.additional_feedback.splitlines())
            html += f"<p><span style=\"text-decoration: underline;\">Zusätzliches Feedback</span>:</p>"
            html += f"{config.PEX_HTML_MAGIC_COMMENT}{feedback_html}{config.PEX_HTML_MAGIC_COMMENT}"

        return html

    @classmethod
    def from_html(cls, html: str, points: float):
        html = html.split(config.PEX_HTML_MAGIC_COMMENT)
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


    def as_editable_text(self, header: str) -> str:
        text = ""
        if header:
            text += f"{header}\n"
        text += f"# Lines starting with '#' are ignored. Do not remove lines starting with '{config.PEX_TEXT_DIVIDER}'.\n"
        text += f"\n"
        text += f"# Test Output:\n{config.PEX_TEXT_DIVIDER}{self.test_output}{config.PEX_TEXT_DIVIDER}\n"
        text += f"\n"
        text += f"# Additional Feedback:\n{config.PEX_TEXT_DIVIDER}{self.additional_feedback}{config.PEX_TEXT_DIVIDER}\n"
        text += f"\n"
        text += f"# Points:\n{config.PEX_TEXT_DIVIDER}{self.points}{config.PEX_TEXT_DIVIDER}\n"

        return text

    @classmethod
    def from_editable_text(cls, text: str):
        # filter empty lines and comments
        filtered_lines = filter(lambda l: len(l) > 0 and not l.startswith('#'), text.splitlines())
        text = '\n'.join(filtered_lines)

        text = text.split(config.PEX_TEXT_DIVIDER)

        try:
            test_output = text[1]
            additional_feedback = text[3]
            points = text[5]
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


    def grade(self, submission: Path, verbose: bool = False) -> PexFeedback:
        # create folder structure needed for docker container / grading scripts
        grading_folder = file_mgmt.create_temporary_folder()
        grading_source = grading_folder / Path(f"{self.pex_name}/group-{config.PEX_DOCKER_GROUP_NAME}")
        grading_target = grading_folder / Path(f"{self.pex_name}-grading")

        file_mgmt.create_folder(grading_source)
        shutil.copy2(submission, grading_source)

        # initiate grading by starting the docker container
        util.info(f"Grading submission '{submission}'...")
        util.run_command( "docker run --rm "
                         f"--mount type=bind,source={grading_folder.resolve()},target=/submissions "
                         f"--mount type=bind,source={grading_target.resolve()},target=/grading_schemes "
                         f"--name {self.pex_name}-docker-group-{config.PEX_DOCKER_GROUP_NAME} "
                         f"{self.pex_name}-docker {self.pex_name} {config.PEX_DOCKER_GROUP_NAME}", show_output=verbose)

        # parse feedback file
        feedback_file = file_mgmt.find_single_path('*.json', grading_target)
        with open(feedback_file, 'r') as f:
            d = json.load(f)
        grade_text, reached_points = _json_to_txt(d)
        reached_points = float(reached_points)

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