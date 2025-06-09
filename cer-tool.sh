#!/usr/bin/env bash

# Path to config file
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
CONFIG_FILE="$SCRIPT_DIR/cer-tool.paths"

# Exit if config file does not exist
if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Error: Configuration file '$CONFIG_FILE' not found." >&2
  exit 1
fi

# Read and parse config
ENV=""
CMD=""
while IFS='=' read -r key value; do
  case "$key" in
    "ENV") ENV="$value" ;;
    "CMD") CMD="$value" ;;
    *) echo "Error: Invalid line in config: '$key=$value'" >&2; exit 1 ;;
  esac
done < <(grep '=' "$CONFIG_FILE")

# Check for required variables
if [[ -z "$ENV" || -z "$CMD" ]]; then
  echo "Error: Missing ENV or SCRIPT entry in config file." >&2
  exit 1
fi

# Check that activation script exists
ACTIVATE_SCRIPT="$ENV/bin/activate"
if [[ ! -f "$ACTIVATE_SCRIPT" ]]; then
  echo "Error: Activation script not found at '$ACTIVATE_SCRIPT'" >&2
  exit 1
fi

# Activate virtual environment
source "$ACTIVATE_SCRIPT"

# Run the Python script with all forwarded arguments
eval "$CMD" "$@"

# Deactivate the virtual environment
deactivate
