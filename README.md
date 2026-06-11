# nacho

노션 데이터베이스를 셸 / Claude Code 슬래시 커맨드로 다루는 자동화 도구.
업무 트래킹용 노션 DB 에 새 행 추가, 진행 일지 누적, 일별 브리핑, Claude 세션 ID 자동 캡처.

## 사전 요구사항

- macOS / Linux
- Python ≥ 3.10
- Notion **Internal Integration** ([my-integrations](https://www.notion.so/my-integrations))
- 사용할 노션 DB 의 ... 메뉴 → Connections 에 위 Integration 추가
- 선택: [Claude Code](https://docs.anthropic.com/claude-code) — 슬래시 커맨드 / 세션 컨텍스트 모드 쓸 때만

## 설치

```bash
git clone <repo-url> nacho && cd nacho

# 격리된 venv 권장
python3 -m venv .venv
.venv/bin/pip install -e .

# 어디서든 호출 가능하게 (선택)
mkdir -p ~/.local/bin
ln -sf "$PWD/.venv/bin/nacho" ~/.local/bin/nacho
```

## 첫 실행

```bash
nacho init
```

마법사가 차례로 묻는다:

1. **Notion Integration Token** (getpass — 화면에 안 보임)
2. **DB URL** — DB 페이지 우상단 Share → Copy link
3. **DB schema 조회** + **필드 자동 매핑** (한·영 패턴 휴리스틱)
4. **status 자동 분류** (Notion status group 활용 — To-do/In progress = active, Complete = inactive)
5. **기본값** (status, assignee)

결과:
- `~/.config/nacho/config.yaml` — DB ID, 필드 매핑, 기본값
- `~/.config/nacho/credentials.json` — token (chmod 0600)

수동 작성하려면 [`config.example.yaml`](./config.example.yaml) 참고.

## 사용 — 셸에서 직접

### 새 행 생성

```bash
# 인터랙티브 (권장) — 본인 DB 의 옵션이 동적으로 메뉴로 나옴
nacho new

# 인자 미리 지정 + 확인 단계 건너뛰기
nacho new \
  --title "정렬 깨짐 버그" \
  --category 운영 \
  --project "Project A" \
  --link https://example.atlassian.net/browse/KEY-123 \
  --yes
```

- 매핑 안 된 필드 (`config.yaml` 에 비어있는 키) 는 prompt 도 안 함 → 본인 DB 구조에 맞게 작동
- 옵션 값은 DB schema 의 실제 옵션만 허용 (자유 입력 거부)
- `--link auto` → 시스템 클립보드에서 URL 자동 추출
- `--session-id` 미지정 시 `~/.cache/nacho/current-session` 에서 자동 (Claude Code SessionStart hook 셋업 필요 — 아래 참고)

### 행 조회

```bash
nacho list --active                    # 활성 상태만 (status_categories.active)
nacho list --status "진행 중"           # 특정 상태
nacho list --json                      # 자동화·LLM 용
```

### 진행 일지 (현황 메모) 추가

```bash
nacho note "큐레이션" "스테이징 모니터링 후 배포 예정"
```
- DB 행의 본문 `## 진행 일지` 섹션에 `- YYYY-MM-DD HH:MM: 메모` append
- 동시에 `status_note` 필드 (예: "현황 요약") 를 그 메모로 덮어쓰기 → DB list view 의 한 컬럼으로 한 눈에

### 브리핑

```bash
nacho brief                                          # stdout 으로
nacho brief --to-file ~/Desktop/today-brief.md       # 파일 저장
```
- 마감 임박 (~7일) / 진행 중 / 대기·보류 그룹으로 정리
- 각 행마다 `[프로젝트]` prefix + `status_note` 현황 메모 표시

### 세션 재개

```bash
nacho resume "큐레이션"          # 해당 행의 session_id → 'claude --resume <id>' 출력
nacho resume "큐레이션" --exec   # 직접 claude --resume 실행
```

## 사용 — Claude Code 슬래시 커맨드

```bash
./install.sh
```
→ `~/.claude/commands/` 에 심볼릭 링크 등록.

세 가지 슬래시:

| 슬래시 | 용도 | 가공 정도 |
|---|---|---|
| `/nacho` | 새 행 생성 (세션 컨텍스트 자동 요약) | 풀 자동 — 본문 LLM 작성 |
| `/nacho-quick` | 새 행 생성 (사용자 명시만, session_id 만 자동) | 본문 가공 X (보안 우선) |
| `/nacho-note` | 기존 행에 메모 한 줄 + 현황 요약 갱신 | 듀얼 모드 |

각 슬래시의 동작·안전 가드는 `commands/*.md` 참고.

## SessionStart hook (선택) — Claude 세션 ID 자동 캡처

`~/.claude/settings.json` 의 SessionStart hook 배열에 추가:

```json
{
  "type": "command",
  "command": "mkdir -p ~/.cache/nacho && jq -r .session_id > ~/.cache/nacho/current-session"
}
```

→ Claude Code 세션 시작 시 session_id 가 파일에 기록. 이후 `nacho new` 가 자동으로 본문 `## Session` 섹션에 삽입.

## 설계 — 왜 Notion MCP 가 아니라 CLI + 얇은 스킬인가

(oobs · tako 와 공통 설계 원칙)

MCP 의 컨텍스트 비용은 호출이 아니라 **상주**에서 나간다. 공식 Notion MCP 를 붙이면 도구
20개 안팎의 스키마가 모든 세션의 시스템 프롬프트에 실려, *노션을 안 쓰는 세션에서도*
수천~만 토큰을 차지할 수 있다. nacho 는 그 상주 비용을 호출 시점 비용으로 바꾼 구조다:

- **상주 비용**: 스킬 설명 한 줄(수십 토큰)뿐. 사용법은 `/nacho` 호출 순간에만 로드
- 호출당 비용은 MCP 와 비슷 — 절약분은 전적으로 상주 스키마
- **세션 밖 셸 직접 호출 = 토큰 0** (보안 메모의 audit 우회와도 일치) + 결정적 동작

정직한 트레이드오프:

- 최신 Claude Code 는 MCP 도구를 지연 로딩(ToolSearch)하므로 상주 격차가 예전만큼 크지 않다
- MCP 가 이기는 지점 — 타입 스키마로 잘못된 호출 감소, 인증을 서버가 관리, 그리고
  **벤더 유지보수**: Notion API 가 바뀌면 nacho 는 직접 고쳐야 한다. 필드 매핑을 설정에
  직접 등록하는 것도 MCP 의 런타임 조회 대비 수동 비용

## 보안 메모

- 토큰은 `~/.config/nacho/credentials.json` 에 평문 저장 (chmod 0600).
- `Claude Code` 안에서 nacho 를 호출하면 명령 + 인자 + 결과가 Anthropic API 응답에 포함될 수 있음 → 회사 Team Plan 등에서 audit 우려 있으면 **cmux 다른 패널에서 셸 직접 호출** 권장.
- `/nacho-quick` 은 본문 LLM 가공을 막아 노출을 줄이지만, 슬래시 호출 자체는 audit log 에 잡힘 — 가장 안전한 건 Claude Code 우회.

## 디렉토리

```
nacho/
├── commands/
│   ├── nacho.md             /nacho 슬래시
│   ├── nacho-quick.md       /nacho-quick 슬래시
│   └── nacho-note.md        /nacho-note 슬래시
├── nacho/                   Python 패키지
│   ├── auth.py              credentials 로드
│   ├── notion_client.py     REST 진입점
│   ├── page_draft.py        properties 빌더 + 미리보기
│   ├── prompts.py           인터랙티브 입력
│   ├── schema.py            DB schema 옵션 추출
│   ├── session.py           Claude session id
│   ├── progress.py          진행 일지 섹션
│   ├── clipboard.py         클립보드 URL 추출
│   ├── config.py            설정 + init 마법사
│   └── main.py              CLI 진입점
├── config.example.yaml      설정 예시 (수동 작성용)
└── install.sh               슬래시 커맨드 등록 (선택)
```

## 문제 해결

- `nacho: command not found` — `~/.local/bin/nacho` 심볼릭 링크 안 됐거나 PATH 에 `~/.local/bin` 없음
- `설정 파일이 없습니다` — `nacho init` 먼저
- `credentials 없음` — 같음
- `400 ... validation error` — DB schema 옵션과 안 맞는 값. `~/.config/nacho/config.yaml` 의 `fields` 매핑 확인, 또는 `nacho init --force` 로 재셋업
- `401 unauthorized` — token 만료/잘못됨. `nacho init --force` 로 재입력
- `404 ... database not found` — Integration 이 그 DB 에 권한 없음. DB 페이지 ... → Connections 에 Integration 추가
