Sets background picture to your personal todo file so you never forget.

```sh
npm install -g markdown-to-png-cli


sudo cp ./apps/todo-as-desktop/custom.todo_wallpaper.plist ~/Library/LaunchAgents/custom.todo_wallpaper.plist
launchctl load ~/Library/LaunchAgents/custom.todo_wallpaper.plist
```


**stop**:
```sh
launchctl unload ~/Library/LaunchAgents/custom.todo_wallpaper.plist
```