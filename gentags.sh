#!/bin/bash

#cd /path/to/framework/library
#-f ~/.vim/mytags/framework 
#--PHP-kinds=+cf 
#-exuberant \
exec ctags \
    -R \
    --fields=+S \
    --exclude="\.svn" \
    --exclude="\.git" \
    --totals=yes \
    --tag-relative=yes \
    .

#    --PHP-kinds=cfiv \
#    -h ".php" \
#no longer needed in ctags 5.7
#    --regex-'PHP=/(abstract)?\s+class\s+([^ ]+)/\2/c/' \
#    --regex-'PHP=/(static|abstract|public|protected|private)\s+function\s+(\&\s+)?([^ (]+)/\3/f/' \
#    --regex-'PHP=/interface\s+([^ ]+)/\1/i/' \
#    --regex-'PHP=/\$([a-zA-Z_][a-zA-Z0-9_]*)/\1/v/' \
#

