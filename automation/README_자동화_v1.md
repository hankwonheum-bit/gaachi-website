# 가치앤같이 사례 자동 게시 시스템 (v1)

하루에 **딱 1건**, 대기열(queue)에 쌓아 둔 감정평가 사례 페이지를
사람 손 없이 홈페이지에 올리는 자동화 장치입니다.
PC를 켜 두기만 하면 됩니다.

---

## 1. 전체 흐름

```
 [사람 또는 작성 AI]
        │  사례 HTML + 카드 메타(.meta.tsv) 를 넣어 둠
        ▼
 automation/queue/            ← 대기열 (001_슬러그.html 처럼 번호 순)
        │  ① 가장 앞 번호 1건 선택 (하루 1건)
        ▼
 ┌──────────────────────────────┐
 │ ② 검증 (하드 게이트)          │  실패 시 ──▶ automation/rejected/
 │   구조 / JSON-LD / canonical │              + .reason.txt (사유)
 │   개인정보 / 금지문구 / 주석   │
 └──────────────────────────────┘
        │ 통과
        ▼
 ③ cases/슬러그.html 생성        (같은 이름이 있으면 -v2, -v3 로 새 파일)
        │
        ├─▶ ④ sitemap.xml  갱신  (백업 후 <url> 1건 추가 + 홈 lastmod 갱신)
        ├─▶ ⑤ index.html   갱신  (백업 후 case-card 1개 추가)
        └─▶ ⑥ queue → automation/published/ 로 이동
        │
        ▼
 ⑦ git add / commit / push origin main
        │   (실패하면 git pull --rebase 후 1회 재시도)
        ▼
 ⑧ Cloudflare Pages 자동 배포  (push 감지 → 1~2분 내 반영)
        │
        ▼
 ⑨ IndexNow 통보 (Bing·Naver·Yandex 등 즉시 색인 요청)
        │
        ▼
 ⑩ automation/state/published_log.tsv 에 결과 1줄 기록
```

> 구글 색인은 IndexNow 대상이 아닙니다. 구글은 기존 방식대로
> `gsc_index.py` 를 쓰거나 sitemap.xml 크롤링을 기다립니다.
> (구글 sitemap ping 은 2023년 폐지, Indexing API 는 채용공고 전용이라
> 일반 페이지에 쓰면 계정 제재 위험이 있어 사용하지 않습니다.)

---

## 2. 파일별 역할

| 경로 | 역할 |
|------|------|
| `automation/publish_case_v1.py` | **핵심 엔진.** 대기열 1건을 검증하고 게시까지 전부 수행 |
| `automation/ping_indexnow_v1.py` | IndexNow 색인 통보 (단독 실행도 가능) |
| `automation/run_daily_v1.bat` | 윈도우 실행 래퍼. python 을 찾아 엔진을 돌리고 로그를 남김 |
| `automation/run_hidden_v1.vbs` | 검은 창이 뜨지 않도록 배치를 숨겨서 실행하는 런처 |
| `automation/register_task_v1.ps1` | 작업 스케줄러에 자동 실행 등록/해제 (몇 번 실행해도 안전) |
| `automation/register_task_v1_사용법.txt` | 위 등록 스크립트의 한글 사용 설명서 |
| `automation/queue/` | **게시 대기열.** 여기에 넣은 파일이 순서대로 올라감 |
| `automation/published/` | 게시 완료된 원본 보관함 |
| `automation/rejected/` | 검증 탈락 원본 + 사유 파일 (git 에 올리지 않음) |
| `automation/logs/` | 실행 로그 (`run-YYYYMMDD.log`, `publish-YYYYMMDD.log`) |
| `automation/state/published_log.tsv` | 게시 이력 대장 (날짜·파일·URL·커밋·결과) |
| `automation/config/blocklist_names_v1.txt` | 이 문자열이 있으면 무조건 게시 거부 (인명 등) |
| `automation/config/forbidden_phrases_v1.txt` | 금지 문구 목록 (수수료·평가수수료·비용은 약) |
| `automation/config/indexnow_key_v1.txt` | IndexNow 키 1줄 |

### 건드리지 않는 것
- `cases/` 폴더의 기존 파일 — 절대 덮어쓰지 않습니다(같은 이름이면 `-v2`).
- `index.html` / `sitemap.xml` — 수정 전 `*.bak-YYYYMMDD-HHMMSS` 백업을 먼저 만듭니다.
- `.gitignore`, `gsc_index.py` 등 기존 파일 — 전혀 손대지 않습니다.

---

## 3. 대기열에 사례 추가하는 방법 (수동)

### 3-1. 사례 HTML 넣기
`automation/queue/` 에 아래 이름 규칙으로 저장합니다.

```
NNN_슬러그.html          예) 011_gangnam-daechi-2026.html
```

- `NNN` : 3자리 순번(작은 번호가 먼저 게시됩니다)
- `슬러그` : 실제로 공개될 주소가 `https://gaachi.co.kr/cases/슬러그.html` 가 됩니다.
- 파일 안의 `<link rel="canonical">` 주소가 위 주소와 **정확히 같아야** 합니다.
  (다르면 검증에서 거부됩니다)

### 3-2. 카드 메타 파일 넣기 (선택이지만 권장)
같은 이름에 확장자만 바꿔 `automation/queue/NNN_슬러그.meta.tsv` 로 저장합니다.
`키 <TAB> 값` 형식이며, 메모장이 아니라 엑셀에서 "탭 구분 텍스트"로 저장해도 됩니다.

```
num	09
cat	상속·증여
tag	상속·증여 감정평가
title_line1	서울 강남구 대치동
title_line2	OO아파트 감정평가
purpose	세무서 제출용 · 상속세 신고 시가참고
sijae	서울 강남구 대치동
gijun	2026. 08. 20
method	거래사례비교법
value_text	12억 5,000만원
seo_h2	서울 강남구 대치동 OO아파트 상속 감정평가 사례
seo_p	첫 문단||둘째 문단||셋째 문단
region	강남구
object	OO아파트
purpose_short	상속
```

- `seo_p` 는 `||` 로 문단을 나눕니다.
- `region` / `object` / `purpose_short` 는 커밋 메시지
  `feat: [지역] [물건] [목적] 감정평가 사례 추가 (#번호)` 를 만들 때 쓰입니다.
- 메타 파일이 없으면 `<title>` 과 meta description 으로 카드를 추정하고
  로그에 경고를 남깁니다. (이 경우에도 게시는 계속 진행됩니다)

### 3-3. 검증 기준 (하나라도 걸리면 거부)
1. `<!DOCTYPE html>`, `<html lang="ko">` 존재
2. `<h1>` 정확히 1개, `<h2>` 3개 이상
3. JSON-LD 3종(`Article`, `FAQPage`, `BreadcrumbList`) 존재 + JSON 문법 정상
4. `<link rel="canonical">` 주소가 게시될 주소와 일치
5. 개인정보: `의뢰인/소유자/신청인 : 한글이름` 패턴 금지, 차단 인명 목록 불포함
   (`○○님` 형태는 거부가 아니라 **경고**만 남깁니다)
6. 금지 문구(수수료 등) 불포함
7. 잘못된 주석 표기 `<\!--` 없음

---

## 4. 자동 실행 설정

```
powershell -ExecutionPolicy Bypass -File .\automation\register_task_v1.ps1
```

- 등록되는 작업 이름: **가치앤같이_사례자동게시**
- 트리거 ① 로그온 3분 뒤 (네트워크가 붙을 시간 확보)
- 트리거 ② 매일 09:00
- 09:00 에 PC가 꺼져 있었다면, 켜는 즉시 밀린 실행이 한 번 돌아갑니다.
- 자세한 내용은 `register_task_v1_사용법.txt` 참고.

### 수동 실행
```
cd C:\Users\user\Documents\GitHub\gaachi-website
python automation\publish_case_v1.py --dry-run   :: 점검만 (아무것도 안 바꿈)
python automation\publish_case_v1.py             :: 실제 게시
python automation\publish_case_v1.py --no-push   :: 커밋까지만
python automation\publish_case_v1.py --force     :: 오늘 이미 게시했어도 1건 더
```

---

## 5. 잠시 멈추기 (일시 중지)

| 방법 | 효과 |
|------|------|
| 작업 스케줄러에서 작업 오른쪽 클릭 → **사용 안 함** | 자동 실행 자체가 멈춤 |
| `automation\queue` 폴더 이름을 `queue_off` 로 변경 | 실행은 되지만 "대기열 비어있음" 으로 아무 일도 안 함 |
| 대기열 파일을 다른 폴더로 옮겨 두기 | 위와 동일 |
| `register_task_v1.ps1 -Remove` 실행 | 등록된 작업을 완전히 삭제 |

> 어떤 방법을 써도 이미 올라간 사례 페이지는 그대로 유지됩니다.

---

## 6. 로그 읽는 법

| 파일 | 내용 |
|------|------|
| `automation\logs\run-YYYYMMDD.log` | 배치가 python 을 찾았는지, 종료 코드는 몇인지 |
| `automation\logs\publish-YYYYMMDD.log` | 검증 결과, 백업 파일명, 커밋 해시, push 성공 여부 |
| `automation\state\published_log.tsv` | 하루 1줄. 날짜 / 파일 / URL / 커밋 / 결과 |

`published_log.tsv` 의 `result` 값 의미

| 값 | 뜻 | 조치 |
|----|-----|------|
| `OK` | 정상 게시 + push 완료 | 없음 |
| `REJECTED` | 검증 탈락 | `automation\rejected\*.reason.txt` 확인 후 수정하여 다시 대기열에 |
| `PUSH_FAIL` | 커밋은 됐지만 push 실패 | 인터넷 확인 후 `git push origin main` 수동 실행 |
| `COMMIT_FAIL` | 커밋 실패 | `git status` 로 상태 확인 |
| `NO_CHANGE` | 바뀐 내용이 없어 커밋 생략 | 대개 재실행 상황. 확인만 |

종료 코드: `0` 정상(게시 없음 포함) / `1` push 등 실패 / `2` 예기치 못한 오류 / `9` python 못 찾음

---

## 7. 문제 해결표

| 증상 | 원인 | 해결 |
|------|------|------|
| 로그에 "대기열 비어있음" 만 반복 | queue 폴더에 `.html` 이 없음 | 사례 파일을 `automation\queue\` 에 넣기 |
| "오늘은 이미 게시됨" | 같은 날 이미 1건 게시함(정상 동작) | 하루 더 기다리거나 `--force` |
| "canonical URL 불일치" | 파일명 슬러그와 canonical 주소가 다름 | 파일명 또는 canonical 중 하나를 맞추기 |
| "개인정보 의심 패턴 발견" | 본문에 실명이 남아 있음 | 이름 삭제 후 다시 대기열에 |
| "금지 문구 발견: 수수료" | 수수료·비용 언급 | 해당 문장 삭제(광고 규정 리스크) |
| "JSON-LD … 파싱 실패" | 구조화 데이터에 쉼표/따옴표 오류 | 해당 `<script type="application/ld+json">` 블록 문법 수정 |
| `PUSH_FAIL` | 인터넷 끊김 / GitHub 인증 만료 | 네트워크 확인 → `git push origin main` 수동 실행 (커밋은 남아 있음) |
| IndexNow `403 키 파일 미배치` | `https://gaachi.co.kr/<키>.txt` 가 아직 배포 안 됨 | 저장소 루트의 `<키>.txt` 가 push 되었는지 확인(엔진이 자동 생성함), 배포 후 1회 재실행 |
| 종료 코드 9 / "python 을 찾을 수 없습니다" | PC에 python 미설치 또는 PATH 누락 | python.org 설치 시 "Add python.exe to PATH" 체크 |
| 카드가 홈페이지에 안 보임 | 메타 파일 누락으로 카드 정보가 빈약하거나 index 삽입 실패 | `publish-*.log` 의 "index.html 카드 추가 실패" 경고 확인 |
| 잘못 올라갔다 | — | `cases/` 파일은 그대로 두고, `index.html.bak-*` / `sitemap.xml.bak-*` 백업으로 복구 |

---

## 8. 안전장치 요약

- 기존 파일 **삭제·덮어쓰기 없음**. 수정은 항상 백업(`.bak-날짜-시각`) 후.
- 같은 날 두 번 실행해도 두 번 올라가지 않음(게시 대장으로 판정).
- 검증 탈락 원본은 `rejected/` 로만 보관하며 **git 에 올리지 않음**(개인정보 보호).
- push 실패해도 커밋을 되돌리지 않음(작업 손실 방지).
- 하루 1건 제한으로 검색엔진이 스팸으로 오인할 위험 최소화.
