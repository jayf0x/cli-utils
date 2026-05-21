# CLI Utils

Personal CLI tooling and background apps for macOS.

- `./bash` — shell utilities and aliases, sourced into `~/.zshrc`
- `./apps` — background processes and standalone apps

## Setup on a new machine

Source the index file:

```sh
echo "\nsource '$HOME/Documents/GitHub/cli-utils/bash/__index.sh'" >> ~/.zshrc
```

Install dependencies:

```sh
# note: if not using eza, comment `alias ls='eza'` in _alias.sh
brew install fzf bat eza imagemagick

# Markdown preview in Quick Look
brew install --cask qlmarkdown
xattr -r -d com.apple.quarantine /Applications/QLMarkdown.app
```

## Global git ignore

```sh
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

## macOS defaults

```sh
# Show hidden files in Finder
defaults write com.apple.finder AppleShowAllFiles true

# Disable two-finger swipe navigation in Chrome
defaults write com.google.Chrome AppleEnableSwipeNavigateWithScrolls -bool FALSE

# disable emoji popup
sudo defaults write /Library/Preferences/FeatureFlags/Domain/UIKit.plist emoji_enhancements -dict-add Enabled -bool NO   

# no hot corners
defaults write com.apple.dock wvous-tl-corner -int 0
defaults write com.apple.dock wvous-tr-corner -int 0
defaults write com.apple.dock wvous-bl-corner -int 0
defaults write com.apple.dock wvous-br-corner -int 0

# no dictionary long press
defaults write -g ApplePressAndHoldEnabled -bool false

# Disable Spotlight indexing (use Raycast instead!)
sudo mdutil -a -i off
```

## Useful snippets

```sh
# Fix VSCode flickering on external monitor
code --disable-gpu

# Restart Core Audio
sudo launchctl kickstart -kp system/com.apple.audio.coreaudiod

# Allow Ollama requests from Thunderbird extension
launchctl setenv OLLAMA_ORIGINS "moz-extension://*"

# Backup VSCode settings
cp ~/Library/Application\ Support/Code/User/settings.json ~/Documents/GitHub/cli-utils/saved-configs/settings.json
```
