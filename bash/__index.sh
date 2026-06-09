#!/bin/bash
# Please import me :)

# path to this repo
export PATH_CLI_UTILS="$HOME/Documents/GitHub/cli-utils/bash"

source "$PATH_CLI_UTILS/_alias.sh"
source "$PATH_CLI_UTILS/_scripts.sh"
source "$PATH_CLI_UTILS/_functions.sh"
source "$PATH_CLI_UTILS/_overwrites.sh"

# import custom bash files
for f in $PATH_CLI_UTILS/packages/*.sh; do source $f; done


#### global var overwrites ####

export HOMEBREW_INSTALL_BADGE="☕️"
export PATH="/usr/local/bin:$PATH"
