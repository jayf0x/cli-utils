#!/bin/bash

: '''
USAGE: 
1. Move this file to the home directory.

2. Add an alias in .zprofile (or .basrc)
$ nano ~/.zprofile

Add the following:
alias "blink"="bash ~/blink"



'''

if ! command -v yalc > /dev/null; then
    read -p "Yalc i not yet installed. Wish to install it? [Y/n]" response
    if [[ $response =~ ^(yes|y|Y|'please') ]]; then
        yarn global add yalc
    else
        exit 0 
    fi
fi

# small wrapper for yalc: vite requires up-to-date (/lib) builds & needs --force reload to update it's .vite folder
# yalc: https://github.com/wclr/yalc
{
    case "$1" in
        # package: initialisation
        publish|init|create) 
            yalc publish --private "$2";;

        # package: update the edited package
        push|'-p')
            yarn build
            clear
            yalc push;;


        # project: adds a package
        add|'-a')
            yalc add "$2" --quite
            yarn dev --force;;

        # project: updates all packages
        update|'-u')
            yalc update --all
            yarn dev --force
            ;;

        # project: remove yalc(s) from project
        remove|'-r')
            yalc remove --all;;


        # global: cleanup store
        clean)
            yalc installations clean;;

        # creates file with a flow you can execute to automate these commands
        flow)
            echo "
# first run '...some/package' create
#!/bin/bash

cd ...some/package/
blink push

cd ...some/project/
blink push
" > blink_flow.sh
chmod +x blink_flow.sh
echo "You can now run: blink_flow.sh. Remeber to edit the paths"
            ;;


        *)
            echo blink: "publish|add|push|update|remove|clear|clean";;
    esac
} || {
    printf '\360\237\246\204\360\237\246\204\360\237\246\204\n'
    echo 'something went wrong..'   
}