upgrade-package() {
    CURRENT=$(node -p "require('./package.json').version")
    MAJOR=$(echo "$CURRENT" | cut -d. -f1)
    MINOR=$(echo "$CURRENT" | cut -d. -f2)
    PATCH=$(echo "$CURRENT" | cut -d. -f3)

    BUMP="${BUMP:-patch}"
    case "$BUMP" in
    major) MAJOR=$((MAJOR+1)); MINOR=0; PATCH=0 ;;
    minor) MINOR=$((MINOR+1)); PATCH=0 ;;
    patch) PATCH=$((PATCH+1)) ;;
    *) echo "Unknown BUMP value: $BUMP (use patch/minor/major)" && exit 1 ;;
    esac

    return "$MAJOR.$MINOR.$PATCH"
}
