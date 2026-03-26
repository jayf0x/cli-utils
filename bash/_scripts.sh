## function that trigger other scripts/files ##

cli_pth_scripts="$PATH_CLI_UTILS/scripts"
cli_pth_configs="$PATH_CLI_UTILS/saved-configs"
cli_pth_vendors="$PATH_CLI_UTILS/vendor"


# only use for legal public data
:download-yt() {
    if ! command -v ffmpeg &> /dev/null; then
        echo "Error: ffmpeg not installed"
        return 1
    fi

    url=$(:urlencode "$1" )

    "$cli_pth_vendors/yt-dlp_macos" \
        -x \
        --audio-format m4a \
        --audio-quality 0 \
        -f bestaudio \
        "$1"

    # $cli_pth_vendors/yt-dlp_macos -x --audio-format mp3 --audio-quality best "$1"
}

:blink() {
    bash "$cli_pth_scripts/fn-blink.sh" "$@"
}

:random-bg() {
	local URL="${1:-'$HOME/Documents/ai-quotes'}"
	python3 "$cli_pth_scripts/fn-setRandomBackground.py" $URL
}

:compress(){
	python3 "$cli_pth_scripts/fn-compress-screenrecordings.py" "$1"
}

:grep-component() {
    python3 "$cli_pth_scripts/fn-grep-react-component.py" "$@"
}
