#!/bin/bash

# path to this repo
export PATH_CLI_UTILS="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"

source "$PATH_CLI_UTILS/_alias.sh"
source "$PATH_CLI_UTILS/_scripts.sh"
source "$PATH_CLI_UTILS/_functions.sh"
source "$PATH_CLI_UTILS/_overwrites.sh"

# import custom bash files
for f in $PATH_CLI_UTILS/packages/*.sh; do source $f; done

# linux-only standalone executables (e.g. add-app)
export PATH="$PATH_CLI_UTILS/linux:$PATH"


#### global var overwrites ####

export HOMEBREW_INSTALL_BADGE="☕️"
export PATH="/usr/local/bin:$PATH"
