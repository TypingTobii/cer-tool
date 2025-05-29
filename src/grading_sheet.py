import csv
import re
from typing import List

import pandas as pd
from pandas.core.frame import DataFrame

import util


class GradingSheet:
    data: DataFrame = []

    def __init__(self, path: str) -> None:
        self.path = path
        self.data = pd.read_csv(path, index_col=0)
        self.data = self.data.fillna('')

    def save(self, path: str | None = None):
        output_path = path if path else self.path
        self.data.to_csv(output_path, quoting=csv.QUOTE_ALL)

    def __str__(self) -> str:
        return f"<grading scheme @'{self.path}' containing {self.data} entries>"


    def get_name(self, id: int) -> str:
        return self.data.loc[f"Teilnehmer/in{id}", "Vollständiger Name"]

    def set_points(self, id: int, points: float) -> None:
        points_german = str(points).replace('.', ',')
        self.data.loc[f"Teilnehmer/in{id}", "Bewertung"] = points_german
        util.info(f" GRADING SHEET: points for {self.data.loc[f"Teilnehmer/in{id}", "Vollständiger Name"]} set to {points_german}.")

    def get_points(self, id) -> float | None:
        points: str = self.data.loc[f"Teilnehmer/in{id}", "Bewertung"]
        if points == "":
            return None
        else:
            return float(points.replace(',', '.'))

    def get_comment(self, id: int) -> List[str]:
        raw_feedback = str(self.data.loc[f"Teilnehmer/in{id}", "Feedback als Kommentar"])
        return _decode_comment(raw_feedback)

    def set_comment(self, id: int, comment: List[str]) -> None:
        self.data.loc[f"Teilnehmer/in{id}", "Feedback als Kommentar"] = _encode_comment(comment)
        util.info(
            f" GRADING SHEET: feedback for {self.data.loc[f"Teilnehmer/in{id}", "Vollständiger Name"]} set to '{self.data.loc[f"Teilnehmer/in{id}", "Feedback als Kommentar"]}'.")

    def append_comment(self, id: int, comment: List[str]) -> None:
        self.data.loc[f"Teilnehmer/in{id}", "Feedback als Kommentar"] += _encode_comment(comment)
        util.info(
            f" GRADING SHEET: feedback for {self.data.loc[f"Teilnehmer/in{id}", "Vollständiger Name"]} set to '{self.data.loc[f"Teilnehmer/in{id}", "Feedback als Kommentar"]}'.")

    def find_participants(self, keyword: str) -> List[List[str]]:
        selected_cols: DataFrame = self.data[["Vollständiger Name"]]
        filtered: DataFrame = selected_cols[selected_cols["Vollständiger Name"].str.contains(keyword, case=False)]
        filtered = filtered.reset_index()
        filtered = filtered.replace("Teilnehmer\\/in(.*)", "\\1", regex=True)
        return filtered.values.tolist()

    def select_participant(self, keyword: str) -> int:
        results = self.find_participants(keyword)
        if len(results) == 0:
            util.error(f"No participant named '*{keyword}*' found.")
            return 0
        elif len(results) == 1:
            return int(results[0][0])
        else:
            index = util.choose_index(list(map(lambda l: " - ".join(l), results)), "Multiple results found:")
            return int(results[index][0])

    def filter(self, ids: List[int]) -> None:
        # map ids to actual entries within grading sheet
        translated_ids = map(lambda id: f"Teilnehmer/in{id}", ids)
        self.data = self.data.loc[self.data.index.isin(translated_ids)]
        util.info(f" GRADING SHEET: Filtered to these IDs: {ids} ({len(self.data.index)} entries left).")


def _decode_comment(feedback: str) -> List[str]:
    feedback = re.split(r'</?p>', feedback)
    return list(filter(lambda s: len(s) > 0, feedback))


def _encode_comment(feedback: List[str]) -> str:
    feedback = filter(lambda s: len(s) > 0, feedback)
    lines_as_paragraphs = map(lambda s: f"<p>{s}</p>", feedback)
    return ''.join(lines_as_paragraphs)