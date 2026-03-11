#### general custom functions ####

# Ever committed an .env file, nuke git history.
:git-nuke() {
    msg=${1-'Initial commit'}

    echo "This nukes ALL git history. Force push. Gone forever."

    printf "Type YES to burn it: "
    read confirm

    [ "$confirm" != "YES" ] && echo "Coward!" && return 0

    git checkout --orphan temp_nuke_branch
    git add -A
    git commit -m "$msg"

    git branch -D main 2>/dev/null || true
    git branch -m main
    git push -f origin main

    echo "Gone."
}



:llm() {
	if [[ "$1" = 's' ]]; then
		ollama serve
		return
	fi
	models=($(ollama list | awk 'NR>1' | cut  -wf 1))

	for ((i = 0; i < ${#models[@]}; i++)); do
		printf "%d) %s\n" $((i+1)) "${models[i+ 1]}"
	done

    model_index=-1
    if [[ $1 =~ ^[+-]?[0-9]+$ ]]; then
        model_index=$1
	else
        read -r res
        model_index=$(( $res + 0 ))
    fi
	model=${models[$model_index]}

	if [[ $model ]]; then
		clear
		ollama show "$model"
		echo ""
		echo "Running: $model"
		ollama run "$model"
		return 1
	fi
}

# kodo aka Kodokushi (孤独死)
:kodo() (
	if [[ $1 ]]; then
		newtab
		clear
	fi
	:sui
	:close
)

:sui() {
	kill -9 $$
}

# closes current terminal
:close() (
	v="green-mile"
	echo -n -e "\033]0;$v\007"
	osascript -e 'tell application "Terminal" to close (every window whose name contains "'$v'")' &
	#   osascript -e 'tell application "Terminal" to close (every window whose frontmost is true)' &
)

:close-all() (
    osascript -e 'tell application "Terminal" to close (every window)'
)

# easy mkdir -p
:mkdir() {
    mkdir -p $1
    cd $1
}


:clearcache() {
	rm -rf ~/Library/Application\ Support/CrashReporter/*
	rm -rf ~/Library/Application\ Support/stremio-server/stremio-cache
	# rm -rf ~/Library/Caches/*
	rm -rf ~/Library/Logs/*
	yarn cache clean
	
	if [[ $1 ]]; then
		rm -rf ~/Library/Application\ Support/Adobe/Common/Media\ Cache\ Files/*
		rm -rf ~/Library/Application\ Support/Adobe/Common/Analyzer\ Cache\ Files/*
		rm -rf ~/Library/Application\ Support/Adobe/Common/Peak\ Files/*
		# rm -rf ~/Library/Application\ Support/Code/Cache/Cache_Data
	fi
	clear
	echo "Cache cleared!"
}

:gen-files(){
    # Number of files to generate (default: 10)
    NUM_FILES=${1:-10}

    for ((i = 0; i < NUM_FILES; i++)); do
        HASH=$(head -c 32 /dev/urandom | sha256sum | cut -d' ' -f1)
        echo "Whololo" > "${HASH}.txt"
    done

    echo "$NUM_FILES files generated."
}


:download-spotify() {
	local URL="${1:-'https://open.spotify.com/playlist/6xycakrzgflOZ8Ru1yvHK6'}"
	spotdl $URL
}



:llm2() { # WIP
    [[ "$1" == "s" ]] && { ollama serve; return; }


    mapfile -t models < <(ollama list | awk 'NR>1 {print $1}')


    if [[ ! $1 =~ ^[+-]?[0-9]+$ ]]; then
        echo "Choose a model:"
        for i in "${!models[@]}"; do
            printf "%2d) %s\n" $((i+1)) "${models[i]}"
        done
        echo -n "Index [1-${#models[@]}]: "
        read -r choice
        [[ -n $choice ]] && set -- "$choice" "${@:2}"
    fi


    local idx=${1:-1}
    (( idx < 1 || idx > ${#models[@]} )) && {
        echo "❌  Invalid index."
        return 1
    }
    local model=${models[$((idx-1))]}

    shift   # drop the index argument
    local prompt=""
    for f in "$@"; do
        if [[ -f $f ]]; then
            prompt+=$(printf "\n--- %s ---\n" "$f")
            prompt+=$(cat "$f")
        else
            prompt+=$'\n'"⚠️  File not found: $f"
        fi
    done


    clear
    echo "▶  Running model: $model"
    echo "─────────────────────────────────────"
    ollama show "$model"
    echo

    if [[ -n $prompt ]]; then
        # Send the concatenated file content once, then hand over to interactive mode
        printf "%s" "$prompt" | ollama run "$model"
    else
        ollama run "$model"
    fi
}


