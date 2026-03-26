name="$1"
fileToExecute="$2"
interval="${3:-600}"
serviceName="com.custom.$name"
serviceFileName="com.custom.$name.plist"


_usage_createPlist() {
  echo "Usage: $0 <name> <fileToExecute> [interval]"
  echo "  <name>         : The name (non-empty string)"
  echo "  <fileToExecute>: The path to the file to execute (must exist)"
  echo "  [interval]     : Optional. Interval (in seconds, integer, default: 600)"
  echo "Example: $0 John /path/to/script.sh 300"
  exit 1
}

# Validate inputs
if [ -z "$name" ]; then
    echo "Error: Name is required."
    _usage_createPlist
    exit 1
fi

if [ ! -f "$fileToExecute" ]; then
    echo "Error: File '$fileToExecute' does not exist."
    _usage_createPlist
    exit 1
fi

if ! [[ "$interval" =~ ^[0-9]+$ ]]; then
    echo "Error: Interval must be a valid integer."
    _usage_createPlist
    exit 1
fi

# Check if the LaunchAgent already exists
if test -f ~/Library/LaunchAgents/$serviceName; then
    echo "Exit - Job already exists at: ~/Library/LaunchAgents/$serviceName"
    exit
fi

# Ensure the LaunchAgents directory exists
mkdir -p ~/Library/LaunchAgents

# Create the plist content
content=$(cat <<-END
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.custom.$name</string>

        <key>ProgramArguments</key>
        <array>
        <string>bash</string>
        <string>$fileToExecute</string>
        </array>

        <key>StartInterval</key>
        <integer>$interval</integer>

        <key>StandardOutPath</key>
        <string>/tmp/$name.log</string>
        <key>StandardErrorPath</key>
        <string>/tmp/$name.err</string>
    </dict>
</plist>
END
)

# Write the plist file
echo "$content" > ~/Library/LaunchAgents/$serviceFileName
chmod 644 ~/Library/LaunchAgents/$serviceFileName

# Load the service
launchctl load ~/Library/LaunchAgents/$serviceFileName
launchctl enable "$serviceName"
launchctl start "$serviceName"

echo "[V] Created & loaded ~/Library/LaunchAgents/$serviceFileName"
echo "to stop the service use: launchctl stop $serviceName"



: "
To stop a service:

sudo launchctl bootout user/$(id -u) ~/Library/LaunchAgents/com.custom.$serviceFileName

Key Differences:
stop: Stops a running service but keeps it loaded. If you want to stop a service temporarily without permanently unloading it, use stop.

bootout: Completely unloads and stops the service, ensuring it no longer runs and is not available for restart unless explicitly reloaded.

"