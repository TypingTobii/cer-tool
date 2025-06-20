import os
import subprocess
import sys
from typing import List, Set, Any, Tuple

from cer_tool.flags import flags


# handle unrecoverable errors
def error(message: str) -> None:
    message = message + "." if message[-1] != "." else message
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


# print a warning after a recoverable error
def warning(message: str, consequence: str = None) -> None:
    message = message + "." if message[-1] != "." else message
    print(f"WARNING: {message}", file=sys.stderr)

    if consequence:
        consequence = consequence + "." if consequence[-1] != "." else consequence
        print(f" ↪ {consequence}", file=sys.stderr)


def info(message: str, always_display: bool = False, append_full_stop=True) -> None:
    if not (always_display or flags["verbose"]):
        return
    if message and append_full_stop:
        message = message + "." if message[-1] != "." else message
    print(message)


def clear_console(console_header: str | None = None) -> None:
    # disable this functionality if cer-tool is in verbose mode (s.t. no messages get lost)
    if flags["verbose"]:
        return

    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")

    if console_header:
        info(console_header, always_display=True, append_full_stop=False)


def choose_option(options: Set[str], default: str | None = None, message="Select an option:") -> str:
    options = set(map(lambda s: s.lower(), options))
    if default not in options:
        default = None
    else:
        default = default.lower()

    options_print = sorted(map(lambda s: s.upper() if s == default else s, options))
    chosen = None
    while not chosen:
        user_in = input(f"{message} [{', '.join(options_print)}] ").lower()
        if user_in == "" and default is not None:
            chosen = default
        elif user_in in options:
            chosen = user_in
        else:
            print(f"Invalid choice: {user_in}")

    return str(chosen)


def choose_index(list: List[Any], title: str = "", message: str = "Select an option:") -> int:
    if title:
        print(title)

    for index, option in enumerate(list):
        print(f"{index}:\t{option}")

    chosen = None
    while chosen is None:
        user_in = input(f"{message} [0..{len(list)-1}] ")
        try:
            user_in = int(user_in)
        except ValueError:
            print(f"Not a number: {user_in}")
            continue

        if user_in < 0 or user_in >= len(list):
            print(f"Out of range: {user_in}")
        else:
            chosen = user_in

    return chosen


def wait_for_user(message="Press ENTER to continue..."):
    input(message)


def index_to_ascii(index: int, zero_based: bool = True) -> str:
    if index < 0:
        raise IndexError("Index must be non-negative")

    if not zero_based:
        index -= 1

    if index > 25:
        return index_to_ascii(index // 26 - 1, zero_based) + index_to_ascii(index % 26, zero_based)
    else:
        return chr(ord('a') + index)


def run_command(command: str, show_output=True):
    if flags["verbose"] or show_output:
        result = subprocess.run(command, shell=True)
        if result.returncode != 0:
            error(f"Command '{command}' exited unsuccessfully. See the above output for details.")
    else:
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            error(f"Command '{command}' exited unsuccessfully:\n{result.stderr}")


def run_potentially_failing_command(command: str) -> Tuple[bool, str]:
    result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    return result.returncode == 0, result.stdout