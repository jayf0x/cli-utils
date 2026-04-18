: """
Simple wrapper to have scoped access to tokens to minimize leakage and prevent being read in plaintext.

Usage:
wtoken NPM_TOKEN npm publish
wtoken GH_TOKEN gh release create v1.0.0


Setup:
security add-generic-password -a "$USER" -s gh_token -w xxx
security add-generic-password -a "$USER" -s npm_token -w xxx

"""

wtoken() {
  local input="$1"
  shift

  [ -z "$input" ] && { echo "Usage: wtoken <key> <command...>"; return 1; }

  # normalize
  local base=$(echo "$input" | tr '[:upper:]' '[:lower:]')
  base=${base%_token}              # remove suffix if present

  local varname=$(echo "${base}_TOKEN" | tr '[:lower:]' '[:upper:]')
  local service="${base}_token"

  local token=$(security find-generic-password -s "$service" -w 2>/dev/null)

  [ -z "$token" ] && { echo "Token not found for $input"; return 1; }

  env "$varname=$token" "$@"
}