#!/bin/bash


if ! command -v code &> /dev/null; then
    echo "You can install it via: Cmd+Shift+P > Shell Command: Install 'code' command in PATH"
    exit 1
fi


extensions=(
    "be5invis.vscode-custom-css"
    "bradlc.vscode-tailwindcss"
    "brandonkirbyson.vscode-animations"
    "dbaeumer.vscode-eslint"
    "eamodio.gitlens"
    "esbenp.prettier-vscode"
    "formulahendry.auto-rename-tag"
    "github.copilot"
    "github.copilot-chat"
    "helgardrichard.helium-icon-theme"
    "hqjs.hq-live-server"
    "jaaxxx.multicursor-casepreserve"
    "josemurilloc.aura-spirit-dracula"
    "kshetline.ligatures-limited"
    "live-servers.liveeserver"
    "mechatroner.rainbow-csv"
    "meganrogge.template-string-converter"
    "miguelsolorio.min-theme"
    "ms-playwright.playwright"
    "ms-python.debugpy"
    "ms-python.python"
    "ms-python.vscode-pylance"
    "ms-python.vscode-python-envs"
    "mylesmurphy.prettify-ts"
    "octref.vetur"
    "peterschmalfeldt.explorer-exclude"
    "richie5um2.vscode-sort-json"
    "seyyedkhandon.firacode"
    "streetsidesoftware.code-spell-checker"
    "subframe7536.custom-ui-style"
    "tomoki1207.pdf"
    "tonybaloney.vscode-pets"
    "vincaslt.highlight-matching-tag"
    "vscode-research-three"
    "vue.volar"
    "waderyan.gitblame"
    "yoavbls.pretty-ts-errors"
    "yzhang.markdown-all-in-one"
    "zhuangtongfa.one-dark-pro"
)


for extension in "${extensions[@]}"; do
    code --install-extension "$extension" --force
    if [ $? -eq 0 ]; then
    else
        echo "Failed to install $extension"
    fi
done
