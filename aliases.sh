# personal-scripts 常用别名
#
# 由 ~/.bashrc 里 source 进来（一次性配置，见 README「服务器别名」）：
#   [ -f /usr/local/personal/apps/personal-scripts/aliases.sh ] && . /usr/local/personal/apps/personal-scripts/aliases.sh
#
# 路径按本文件所在目录推导，仓库克隆到哪个目录都能用；以后加脚本只改这个文件。

_PS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

alias personal_scripts="cd \"$_PS_DIR/\""

alias monkey1="python3 \"$_PS_DIR/monkey.py\""
alias bkmonkey="python3 \"$_PS_DIR/monkey-bk.py\""
alias monkeyjj="python3 \"$_PS_DIR/monkey-jj.py\""
alias querymonkey="python3 \"$_PS_DIR/monkey-name.py\""
alias monkey="python3 \"$_PS_DIR/monkey-hold.py\""
alias monkeytarget="python3 \"$_PS_DIR/monkey-target.py\""
alias qihuo="python3 \"$_PS_DIR/monkey-intl.py\""

unset _PS_DIR
