# Setup (WIP to make this a package): 
# - `//registry.npmjs.org/:_authToken=$NPM_TOKEN` in ~/.npmrc
# - security add-generic-password -a "$USER" -s npm_token -w "xxxx"
# verify: wtoken bash -c 'echo $NPM_TOKEN | less' 
wtoken() {
    local token
    local key='npm_token'
    
    # MacOS
    if command -v security >/dev/null 2>&1; then
        token=$(security find-generic-password -s "$key" -w)
    # Linux
    elif command -v secret-tool >/dev/null 2>&1; then
        token=$(secret-tool lookup service npm)
    else
        echo "No keyring tool found"
        return 1
    fi

    NPM_TOKEN="$token" "$@"
}