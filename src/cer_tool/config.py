import json
import importlib.resources
from jsonschema import validate
from platformdirs import user_config_path
from pathlib import Path

from jsonschema.exceptions import ValidationError
from importlib.resources.abc import Traversable
from typing import Union, List, Tuple, Callable, Type

from cer_tool import util

# includes all settings to be loaded from the config file
_config: dict = {}
# whether the configuration is valid or needs to be checked
_verified: bool = False

type Config_Entry = Union[str, int, bool, List[str]]

_CONFIG_PATH: Path = user_config_path("cer-tool", ensure_exists=True) / "config.json"
_CONFIG_SCHEMA_PATH: Traversable = importlib.resources.files("cer_tool").joinpath("config.schema.json")

_CONFIG_CHECKS : List[Tuple[Callable[[dict], bool], str]] = [
    (lambda c: c["initials"] != "???", "initials not set"),
    (lambda c: "{}" in c["filenames"]["tmp_folder"], "tmp folder filename must include a placeholder"),
    (lambda c: "{}" in "".join(c["moodle"]["feedback_footer"]), "feedback footer must include a placeholder"),
    (lambda c: c["pex"]["text_divider"] != "", "text divider must not be empty"),
    (lambda c: len(c["pex"]["notebook_auto_edit"]["find"]) == len(c["pex"]["notebook_auto_edit"]["replace"]), "find and replace arrays must have the same length"),
]

_default_config: dict = {
    "initials": "???",
    "filenames": {
        "tmp_folder": "__CER_TOOL_TEMP_FOLDER{}__",
        "edit_feedback_file": "__CER_TOOL_TEMP_COMMENT__.txt",
        "feedback_filename_prefix": "Feedback",
        "points_placeholder": " --- "
    },
    "moodle": {
        "submission_keyword": "assignsubmission_file",
        "feedback_footer": [
            "<strong>- {}</strong>"
        ],
        "file_upload_limit_bytes": 24999500
    },
    "pex": {
        "text_divider": "%",
        "html_magic_comment": "<!--%%%-->",
        "docker_group_name": "cer-tool",
        "notebook_auto_edit": {
            "find": ["%matplotlib notebook", "matplotlib.use(\"nbAgg\")"],
            "replace": ["%matplotlib tk", "matplotlib.use('TkAgg')"]
        }
    }
}

def _initialise() -> None:
    global _config, _verified

    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, 'r') as file:
            _config = json.load(file)
    else:
        _config = _default_config
        _save_without_verifying()

    _verified = False


def save() -> None:
    _verify()
    _save_without_verifying()

def _save_without_verifying() -> None:
    with open(_CONFIG_PATH, 'w') as file:
        json.dump(_config, file, indent=4, sort_keys=True)


def set(key_path: str, value: Config_Entry) -> None:
    global _verified

    keys = key_path.split(".")
    data = _config
    for key in keys[:-1]:
        if key not in data or not isinstance(data[key], dict):
            data[key] = {}
        data = data[key]
    data[keys[-1]] = value

    _verified = False


def set_json(key_path: str, value: str) -> None:
    try:
        parsed_value: Config_Entry = json.loads(value)
    except json.JSONDecodeError as err:
        raise ValueError(f"Failed to parse input '{value}': {err.msg}")

    set(key_path, parsed_value)


def get(key_path: str) -> Config_Entry:
    _verify()
    keys = key_path.split('.')
    data = _config

    for key in keys:
        if key not in data.keys():
            util.error(f"Internal error: Config object does not contain key: {key_path}")
        data = data[key]
    return data

def key_exists(key_path: str) -> bool:
    keys = key_path.split('.')
    data = _config

    for key in keys:
        if key not in data.keys():
            return False
        data = data[key]
    return True


def _typeof(key_path: str) -> Type:
    keys = key_path.split('.')
    data = _config

    for key in keys:
        if key not in data.keys():
            util.error(f"Internal error: Config object does not contain key: {key_path}")
        data = data[key]
    return type(data)


def as_str() -> str:
    def rec(path: str, sub_settings: dict) -> str:
        acc = ""
        for key in sorted(sub_settings.keys()):
            if isinstance(sub_settings[key], dict):
                acc += rec(f"{path}{key}.", sub_settings[key])
            else:
                acc += f"{path}{key} = {json.dumps(sub_settings[key])}\n"
        return acc

    return rec("", _config).strip()


def _verify() -> None:
    global _verified

    if _verified:
        return

    with _CONFIG_SCHEMA_PATH.open('r') as schema_file:
        schema = json.load(schema_file)

    # verify schema
    try:
        validate(_config, schema)
    except ValidationError as e:
        util.error(f"Invalid config:\n{e.message}")

    # verify using additional checks
    for check_fun, err_msg in _CONFIG_CHECKS:
        if not check_fun(_config):
            util.error(f"Invalid config: {err_msg}")

    _verified = True



_initialise()