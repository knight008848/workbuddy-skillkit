#!/usr/bin/env bash
# 用 git credential helper 里缓存的 GitHub 凭据运行 gh，避免把 token 落到任何文件。
#
#   bash build/gh.sh release list -R <owner>/<repo>
#   bash build/gh.sh release create <tag> build/out/<name>-<version>.zip --title "..." --notes-file <file>
#
# 为什么不用 `gh auth login`：本机 GCM 缓存的是 40 位 classic PAT，没有 read:org，
# gh 的登录校验会直接拒（error validating token: missing required scope 'read:org'）。
# 但通过 GH_TOKEN 传入时 gh 不做这项校验，api / release / repo view 等命令都正常。
#
# 退出码：0 成功 / 4 依赖缺失（gh 没装或凭据没缓存）
set -euo pipefail

GH_BIN="${GH_BIN:-$HOME/.workbuddy/tools/gh/bin/gh.exe}"

if [ ! -x "$GH_BIN" ]; then
  echo "找不到 gh：$GH_BIN" >&2
  echo "下载（国内建议走镜像）：https://github.com/cli/cli/releases/latest" >&2
  exit 4
fi

if [ -z "${GH_TOKEN:-}" ]; then
  cred=$(printf 'protocol=https\nhost=github.com\n\n' | GIT_TERMINAL_PROMPT=0 git credential fill 2>/dev/null || true)
  tok=$(printf '%s\n' "$cred" | sed -n 's/^password=//p')
  if [ -z "$tok" ]; then
    echo "git credential 里没有 github.com 的凭据。先成功 push 一次，让 GCM 缓存后再试" >&2
    exit 4
  fi
  export GH_TOKEN="$tok"
  unset cred tok
fi

exec "$GH_BIN" "$@"
