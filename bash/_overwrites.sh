## Overwrites of existing function ##

code() { 
	local target="${1:-$HOME/Library/Application Support/Code/User/settings.json}"
    open -a "Visual Studio Code" "$target"
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
        ..*)  # anything starting with 2+ dots
            up_count=$(( ${#target} - 1 ))
            target=$(printf '../%.0s' $(seq 1 $up_count))
            ;;
    esac
    if [ -f "$target" ]; then
        target="$(dirname "$target")"
    fi
    target="${target%/}"

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


    for src in "${sources[@]}"; do
        local abs_src
        abs_src=$(make_abs "$src")

        local final_dest="$dest"

        if [[ ! -e "$dest" && -f "$abs_src" && "${#sources[@]}" -eq 1 ]]; then
            final_dest="$(dirname "$dest")/$(basename "$abs_src")"
        fi

        "$mv_bin" "$abs_src" "$final_dest"
    done
}