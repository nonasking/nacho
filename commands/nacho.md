---
description: 노션 DB 에 새 행 추가 — 세션 컨텍스트 자동 요약
---

사용자가 `/nacho` 를 호출하면, 지금까지의 세션 대화·작업 내용을 바탕으로 `~/.config/nacho/config.yaml` 에 설정된 노션 DB 에 새 행을 만든다.

## 흐름

1. 세션 컨텍스트에서 다음을 추출:
   - **제목**(`--title`): 한 줄 요약, 명사구 또는 동사구
   - **분류 / 프로젝트 / 상태**: 사용자 DB schema 의 옵션 중에서만 매핑. 적절한 게 없으면 비움
   - **마감일 / 시작일**: 자연어 ("내일까지", "다음주 금요일", "2026-06-15") 또는 명시
   - **링크**: URL 형태로 보이면 그대로
   - **본문**(`--body`, 선택): 마크다운으로 상세 (배경 / 작업 내용 / 완료 조건)
2. 사용자에게 미리보기 (`nacho new --yes --no-prompt --require-session --title ... --category ...` 형태) 출력 + 확인 받기
3. OK 면 `nacho new --yes --no-prompt --require-session ...` 셸 실행
   - `--no-prompt`: 대화형 질문 없이 **명시한 인자만 채우고 나머지는 빈 필드** (제목만 필수)
   - `--require-session`: session_id 필수 — Claude Code 세션 밖이면 에러 (nacho 가 hook 파일에서 자동으로 읽음)

## 사용 예

```
/nacho 방금 발견한 정렬 깨짐 — Project A 운영 건
/nacho 캐싱 도입 작업 — 리팩토링
```

## 같은 세션에서 `/tako` 호출이 있었으면

- 그 결과의 Jira URL (`https://*.atlassian.net/browse/KEY-123` 패턴) 을 `--link <url>` 로 자동 전달
- 결과에 duedate (`2026-06-15` 같은 텍스트) 가 보였으면 `--due-date YYYY-MM-DD` 로 명시
- **nacho 는 Jira 를 모름** — Claude 가 세션에서 추출해서 명시적으로 전달할 책임

## 안전 장치

- **제목·본문은 LLM 이 초안만**. 미리보기 단계에서 사용자가 수정 가능.
- 세션에 토큰·비밀번호·고객 실명 같은 민감 정보가 보이면 본문에서 의식적으로 제외.
- DB schema 에 정의된 옵션 외 값은 임의 생성 금지. nacho 가 거부함 → 미리보기에서 사용자가 직접 채우게.
- 본문 끝에 자동으로 `## Session` + `## 진행 일지` 섹션이 들어감 (nacho 가 처리).

## 비고

- `--no-prompt` 로 `nacho new` 의 대화형 입력을 끄고, Claude 가 추출한 인자만 명시적으로 전달한다 (안 준 항목은 빈 필드).
- 세션 컨텍스트 없이 그냥 `/nacho` 빈 호출이면 인터랙티브 마법사(`nacho new`) 안내.
