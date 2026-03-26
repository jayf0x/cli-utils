

plist=./apps/todo-as-desktop/custom.todo_wallpaper.plist

# use file name without suffix as ID for plist 
ID=$(basename ${plist%.*})

if [ ! -f $plist ]; then
    echo 'Plist not found, make sure to run from root dir'.
elif ! plutil -lint $plist | grep '.plist: OK' &> /dev/null; then
    echo 'invalid plist.'
fi


if launchctl list | grep $ID &> /dev/null; then
    echo 'Plist already exists, first unload before reloading. Try:'
    echo "launchctl bootout gui/$(id -u)/$ID"
    exit 0
fi

npm install -g markdown-to-png-cli
clear


sudo cp "$plist" ~/Library/LaunchAgents/$ID.plist
launchctl load ~/Library/LaunchAgents/$ID.plist
echo 'Should be loaded in'.

# Stop using:
# launchctl unload ~/Library/LaunchAgents/custom.todo_wallpaper.plist