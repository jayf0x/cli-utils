Sets background picture to your personal todo file so you never forget.

**install**:
```sh
bash apps/todo-as-desktop/install.sh
```

System Settings > Privacy & Security > Accessibility. 
Add "utils/Terminal.app"


**Remove**:
```sh
sudo rm ~/Library/LaunchAgents/custom.todo_wallpaper.plist
launchctl bootout gui/$(id -u)/todo_wallpaper
```