# Path to the config file
$SCRIPT_DIR = $PSScriptRoot
$configPath = "$SCRIPT_DIR\cer-tool.paths"

# Check if config file exists
if (-Not (Test-Path $configPath)) {
    Write-Error "Configuration file '$configPath' not found."
    exit 1
}

# Read config lines
$config = Get-Content $configPath | Where-Object { $_ -match '=' }

# Parse config into a hashtable
$settings = @{}
foreach ($line in $config) {
    $key, $value = $line -split '=', 2
    if (-not $key -or -not $value) {
        Write-Error "Invalid line in config: '$line'"
        exit 1
    }
    $settings[$key.Trim()] = $value.Trim()
}

# Validate presence of required keys
if (-not $settings.ContainsKey("ENV") -or -not $settings.ContainsKey("CMD")) {
    Write-Error "Missing ENV or CMD entry in config file."
    exit 1
}

$ENV = $settings["ENV"]
$CMD = $settings["CMD"]

# Check that activate script exists
$activateScript = Join-Path $ENV "Scripts\Activate.ps1"
if (-Not (Test-Path $activateScript)) {
    Write-Error "Activation script not found at '$activateScript'"
    exit 1
}

# Activate virtual environment
& $activateScript

try
{
    # Run the Python script with forwarded arguments
    & $CMD @args
}
finally
{
    # Deactivate the virtual environment
    if (Get-Command deactivate -ErrorAction SilentlyContinue)
    {
        deactivate
    }
}
