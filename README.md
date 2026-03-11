# Personal CLI tooling and apps
- ./apps contains some of background processes or apps that are used
- ./bash contains the actual cli utils

# Quick  setup on new machine (`MacOS`) .

Add path:
```sh
echo "\nsource '$(pwd)/bash/__index.sh'" >> ~/.zshrc
# or
echo "\nsource '$HOME/Documents/GitHub/cli-utils/bash/__index.sh'" >> ~/.zshrc
```

Install:
```sh

# note: if not using eza, comment `alias ls='eza'` in [_alias.sh](./_alias.sh).
brew install fzf bat eza

# markdown preview
brew install --cask qlmarkdown
xattr -r -d com.apple.quarantine /Applications/QLMarkdown.app


brew install imagemagick
```

---

**Global git ignore**:
```sh
# can use ~/.config/git/ignore, but same.
global_ignore_path="$HOME/.gitignore-global"

cat << EOF > "$global_ignore_path"
# Global git ignore

**/__pycache__
**/node_modules
**/.cache
**/dist

.DS_Store
.env
EOF

git config --global core.excludesfile "$global_ignore_path"
```


**Customize behavior:**
```sh
# show hidden files in finder by default
defaults write com.apple.finder AppleShowAllFiles true

# disable emojis
# Go to `System Settings - Keyboard - Press "globe" key to - DO NOTHING`
sudo defaults write /Library/Preferences/FeatureFlags/Domain/UIKit.plist emoji_enhancements -dict-add Enabled -bool NO

# disable 2 finger swipe goes back in browsing history
defaults write com.google.Chrome AppleEnableSwipeNavigateWithScrolls -bool FALSE

# disable spotlight indexing - use Raycast
sudo mdutil -a -i off
```

## Keepers
```sh
# can help with flickering vscode on external monitor (not persistent, wip)
code --disable-gpu

# Restart audio core
sudo launchctl kickstart -kp system/com.apple.audio.coreaudiod

#:~:text= for chrome

cp  ~/Library/Application\ Support/Code/User/settings.json  ~/Documents/GitHub/cli-utils/saved-configs/settings.json


#  Thunderbird + Ollama
launchctl setenv OLLAMA_ORIGINS "moz-extension://*"


# TODO, does not work. 
# Disable itunes launcher (pressing f8) - 
# launchctl unload -w /System/Library/LaunchAgents/com.apple.rcd.plist
```


