# uncomment to use 'eza' instead of regular ls
alias ls='eza'


alias l='ls -1'
alias ll='ls -l'
alias la='ls -a1'
alias l1='ls -1'
alias sl="ls"
alias lsl="ls -lhFA | less"

alias c='clear'

alias t1='tree -L 1'
alias t2='tree -L 2'
alias t3='tree -L 3'
# usage of file size (only 2levels as it might do insane search otherwise)
alias t2m='tree --du -h -L 2 | grep M]'
#alias tsg='tree --du -h | grep G]'
# alias psg="ps aux | grep -v grep | grep -i -e VSZ -e"

alias python="python3"
alias pip="pip3"
alias py="python3"

alias yd="yarn dev"
alias yqrn="yarn"
alias pn="pnpm"
