## Overwrites of existing function ##
code() { 
	# default is mac vs code settings - TODO, fix me
	local file="${1:-$HOME/Library/Application Support/Code/User/settings.json}"
    open -a "Visual Studio Code" --args "$file"
}

cd() {
    if [ $# -eq 0 ]; then
        builtin cd ~
        return
    fi
    target="$1"

    if [[ "$target" =~ ^-[0-9]+$ ]]; then
        index="${target#-}"
        dir=$(dirs -l +$index 2>/dev/null)
        [ -n "$dir" ] && builtin cd "$dir" && return
    fi

    case "$target" in
        ..*)  # anything starting with two or more dots
            up_count=$(( ${#target} - 1 ))
            target=$(printf '../%.0s' $(seq 1 $up_count))
            ;;
    esac


    # If the path is a file, strip it to its containing directory
    if [ -f "$target" ]; then
        target="$(dirname "$target")"
    fi
    # If the path ends with a slash accidentally, trim it (cosmetic)
    target="${target%/}"


    # Then navigate using builtin cd
    builtin cd "$target" || return
}




WIP_mv() {
    local mv_bin
    mv_bin=$(command -v mv)

    if [ "$#" -lt 2 ]; then
        echo "Usage: mv SOURCE... DEST" >&2
        return 1
    fi

    local dest="${@: -1}"
    local sources=("${@:1:$#-1}")

    # make path absolute using realpath if available, otherwise manual
    make_abs() {
        if command -v realpath >/dev/null 2>&1; then
            realpath -m "$1"
        else
            case "$1" in
                /*) echo "$1" ;;
                *)  echo "$(pwd)/$1" ;;
            esac
        fi
    }

    dest=$(make_abs "$dest")

    # handle each source
    for src in "${sources[@]}"; do
        local abs_src
        abs_src=$(make_abs "$src")

        local final_dest="$dest"

        if [[ ! -e "$dest" && -f "$abs_src" && "${#sources[@]}" -eq 1 ]]; then
            # destination doesn't exist and source is a file → reuse filename
            final_dest="$(dirname "$dest")/$(basename "$abs_src")"
        fi

        "$mv_bin" "$abs_src" "$final_dest"
    done
}