#!/usr/bin/env bash
# 슬래시 커맨드 등록 — commands/*.md → ~/.claude/commands/ 심볼릭 링크.
# Claude Code 에서 /nacho, /nacho-quick 슬래시 쓸 때만 필요.
# 셸 직접 사용 (nacho new / nacho list 등) 은 install.sh 안 돌려도 됨.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="$REPO_ROOT/commands"
TARGET_DIR="$HOME/.claude/commands"

# 등록할 슬래시 커맨드 파일 목록.
SOURCES=("nacho.md" "nacho-quick.md" "nacho-note.md")

say() { printf "  %s\n" "$*"; }
warn() { printf "  [!] %s\n" "$*" >&2; }
fail() { printf "  [x] %s\n" "$*" >&2; exit 1; }

link_one() {
  local name="$1"
  local src="$SOURCE_DIR/$name"
  local tgt="$TARGET_DIR/$name"

  [[ -f "$src" ]] || fail "원본 없음: $src"

  if [[ -L "$tgt" ]]; then
    local current_link
    current_link="$(readlink "$tgt")"
    if [[ "$current_link" == "$src" ]]; then
      say "이미 연결됨: $tgt"
    else
      warn "다른 위치 가리키는 중: $current_link → 재연결"
      ln -sfn "$src" "$tgt"
      say "재연결: $tgt"
    fi
  elif [[ -e "$tgt" ]]; then
    fail "같은 이름의 일반 파일이 이미 있음: $tgt (옮기거나 삭제 후 재실행)"
  else
    ln -s "$src" "$tgt"
    say "링크 생성: $tgt"
  fi
}

printf "nacho 슬래시 커맨드 등록\n"
mkdir -p "$TARGET_DIR"
for name in "${SOURCES[@]}"; do
  link_one "$name"
done

printf "\n슬래시:\n"
say "  /nacho        풀 자동 — 세션 컨텍스트 요약해서 제목·본문 LLM 작성 (편의 우선)"
say "  /nacho-quick  본문 가공 X — 사용자 입력만, session_id 만 자동 (보안 우선)"
say "  /nacho-note   업무 진행 일지에 메모 한 줄 추가 + 현황 요약 갱신"
say ""
printf "셸 직접 사용 (Claude Code 우회 — 가장 안전):\n"
say "  nacho new --title \"...\" --category 운영 --yes"
say "  nacho list --active"
say "  nacho note \"<업무>\" \"<메모>\""
say "  nacho brief [--to-file ~/Desktop/today-brief.md]"
say "  nacho resume \"<업무>\""
