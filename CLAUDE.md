# 가치앤같이 감정평가법인 — 홈페이지 사례 업로드 가이드 (v4)

최종 개정: 2026-09-16 · 이전 버전은 `CLAUDE.md.bak-*` 에 보존되어 있습니다.

> **이 문서가 최신 기준입니다.** 아래 "참조 파일 버전"의 최신본과 충돌하는 옛 문서
> (`작성가이드_v2/v3`, `case_template_v2/v3`, `생성지침_v1/v2`, 이전 CLAUDE.md)는 따르지 않습니다.

---

## 0. 목적

ChatGPT · Claude · Perplexity · Google AI Overviews 등에 **"감정평가", "상속 감정평가",
"증여 감정평가"** 를 물었을 때 가치앤같이의 사례 페이지가 인용되도록, 사례를 꾸준히 쌓는 것.
신규 상담 문의 유입이 최종 지표입니다.

---

## 1. 현재 구조 — 자동화되어 있습니다

```
[매일 11:30 KST]  Claude 예약작업
   감정평가서 PDF 판독 → 마스킹 → v4 템플릿 작성 → 검증
   → automation/review/      (최초 10건 승인 대기)
   → automation/queue/       (11건째부터 바로 대기열)

[사용자]  automation\승인_v1.bat  →  review/ 에서 queue/ 로 이동

[로그온 3분 후 + 매일 09:00]  윈도우 작업 스케줄러 `가치앤같이_사례자동게시`
   automation/publish_case_v1.py
   → 검증 게이트 → cases/ 복사 → 게시일 각인 → sitemap.xml·index.html 갱신(.bak 백업)
   → git commit + push → Cloudflare Pages 자동 배포 → IndexNow 통보
```

수동으로 사례를 추가할 일이 있어도 **위 파이프라인을 거치는 것이 원칙**입니다.
`cases/` 에 직접 파일을 넣지 마십시오 — sitemap·index 카드·게시일이 함께 갱신되지 않습니다.

---

## 2. 참조 파일 버전

| 용도 | **최신 (사용)** | 폐기 (사용 금지) |
|---|---|---|
| 작업 절차 | `automation/생성지침_v3.md` | 생성지침_v1.md, v2.md |
| 작성 기준·마스킹 | `templates/작성가이드_v4.md` | 작성가이드_v2.md, v3.md |
| 템플릿 | `templates/case_template_v4.html` | case_template_v2.html, v3.html |
| 토큰 사전 | `templates/필드정의_v3.tsv` | 필드정의_v1.tsv, v2.tsv |
| 기준 예시 | `automation/review/001_gangnam-gaepo-hyundai-2025.html` | 케이스_v2_예시.html |
| 검증 | `automation/validate_draft_v1.py` | — |

---

## 3. 공개 범위 — 반드시 준수 (소유자 확정, 2026-09-16)

### 3-1. 인물
1. **담당 감정평가사 성명 미기재.** JSON-LD `author` 는 `Person` 이 아니라 `Organization`.
2. **의뢰인 · 소유자 · 신청인 성명 금지.** 원본 PDF 파일명에 들어 있는 성명도 어떤 산출물
   (초안 · meta.tsv · 로그 · 커밋 메시지)에도 쓰지 않습니다.

### 3-2. 소재지 — 물건 종류에 따라 다릅니다
| 물건 종류 | 표기 범위 |
|---|---|
| 집합건물 (아파트 · 오피스텔 · 구분상가 등) | `○○구 ○○동 <지번>` **지번까지 표기** |
| 토지 · 일반건물 (단독 · 다가구 · 근린생활시설 등) | `○○구 ○○동` **까지만, 지번 없음** |
- **도로명주소는 어느 경우에도 쓰지 않습니다.**
- **본건의 동(棟) 번호는 미기재.** 항목·문장 어디에도 쓰지 않습니다.
- **본건의 층 · 호는 마스킹 기호로 표기합니다** (2026-09-16 소유자 재확정).
  개요 그리드 「층 / 호」 항목에 `제<span class="addr-mask">█</span>층` ·
  `<span class="addr-mask">███</span>호` 로 쓰고, `.addr-mask` CSS 를 함께 넣습니다.
  **실제 층수 · 호수 숫자는 절대 쓰지 않습니다.** (면적은 그대로 기재)
- 단지명(예: '현대아파트')은 표기합니다.

### 3-3. 비교사례 · 감정평가전례
- **동 번호도 삭제**합니다. 소재지는 동(洞) 단위까지.
- 층 · 호 표기 금지.
- 감정평가전례의 **목적은 `—`** 로 블랭크 처리.

### 3-4. 날짜
| 항목 | 표기 |
|---|---|
| 기준시점 | **연도만** (예: `2025년`) |
| 거래시점 · 전례 기준시점 | **연도만** |
| 감정평가서 작성일 | 연 · 월 · 일 (`class="report-date"`) |
| 게시일 | 연 · 월 · 일 (`class="publish-date"`) — 게시 스크립트가 실제 게시일로 각인 |
| 최종 업데이트 | 연 · 월 · 일 (`class="modified-date"`) |
| 사용승인일 | 연 · 월 · 일 (건물 공부 정보라 무방) |

> 기준시점을 연도만 쓰는 이유: 상속 사건의 기준시점은 **상속개시일(피상속인 사망일)** 이라
> 그 자체가 개인정보이며, 단지 · 면적과 결합하면 유족이 특정될 수 있습니다.

**날짜 3종의 `class` 이름은 반드시 위와 같이 씁니다.** 게시 스크립트가 이 class 로
게시일 · 최종 업데이트를 찾아 실제 게시일로 다시 쓰고, 감정평가서 작성일 · 기준시점은 건드리지 않습니다.

### 3-5. 산정과정
- **가치형성요인(단지외부 · 단지내부 · 호별 · 기타) 표와 요인치를 싣지 않습니다.**
- **사정보정치 · 시점수정률 · 시점수정에 쓴 지수명도 싣지 않습니다.**
- 산정과정은 **`결정단가 × 면적 = 산출금액 → 감정평가액`** 까지만 보여줍니다.
- 비교사례 표(면적 · 거래시점 연도 · 거래가액 · 단가)는 유지합니다.
- 비교사례 단가와 결정단가의 차이는 설명하지 않고, "개별 보정 내역은 감정평가서 본문에
  기재되어 있으며 이 페이지에는 싣지 않습니다" 로 갈음합니다.

---

## 4. 콘텐츠 금지사항

1. **수수료 · 보수 금액 기재 금지.** 감정평가액에 따라 달라진다는 설명까지만.
   (자동 검증기가 `수수료` 단어를 차단하므로 필요 시 법정 용어 **`보수`** 를 씁니다)
2. **소급감정을 시사하는 문구 금지.** 예: "신고기한을 역산하여 평가기간 내에 감정평가서가
   완성되도록 일정을 관리합니다" — 임의 소급감정 논란을 부릅니다. 신고기한 · 평가기간은
   **법령 내용을 객관적으로 설명하는 선까지만**.
3. 감정평가액이 공시가격보다 낮다는 취지의 서술 금지. 적정 시장가치 범위를 반영한다고 씁니다.
4. 상속은 상속개시일 **전후 6개월**, 증여는 증여일 **전 6개월 · 후 3개월**.
5. **추측한 숫자 금지.** 원본이 스캔 이미지라 OCR 오류가 잦습니다. 감정평가액 · 면적 · 단가는
   페이지 이미지를 직접 보고 확인하고, 곱셈은 검산합니다. 확신이 없으면 그 블록을 통째로
   빼고 로그에 남깁니다. **잘못된 감정평가액 게시가 최악의 실패입니다.**
6. 분량은 완성본 텍스트 **5,000자 이내**. 일반론 · 정의 블록 · 법령 원문 장문 인용은 넣지 않고
   이 사례에 관한 서술만 씁니다.

---

## 5. SEO / AI 인용

### 5-1. 숨김 텍스트 금지 (← 이전 버전에서 폐기된 규칙)
`color:var(--bg)`, `font-size:1px`, `display:none`, 화면 밖 배치 등으로 키워드를 숨기지 않습니다.
- 구글 스팸정책 "Hidden text and links" 위반 → **사이트 전체 수동조치** 대상
- 실측상 역효과: 키워드 스터핑 17.7% < 기준선 19.3% (GEO, KDD 2024)

기존 사례 페이지에 남아 있는 `seo-content` 숨김 span 은 정리 대상입니다.

### 5-2. 대신 구조화 데이터로 키워드를 싣습니다
화면에 보이지 않으면서 정식 규격인 경로입니다.
- Article JSON-LD `keywords` — 지역 · 물건 · 목적 조합
- Article `about`(RealEstateListing) · `mentions` 배열
- `publisher` Organization `knowsAbout` 배열
- `<meta name="keywords">` · `description` · og 태그
- FAQ 질문문을 실제 검색어 형태로

핵심 키워드군: `감정평가` `상속 감정평가` `증여 감정평가` `<동명> 감정평가`
`<구명> 아파트 감정평가` `세무서 제출용 감정평가` `시가인정액` `상속세 신고` `증여세 신고`
`감정평가법인` `가치앤같이`

### 5-3. 구조
- 소제목은 `<div class="...title">` 이 아니라 **`<h2>` · `<h3>`** 로 씁니다. 질문형으로.
- 본문 FAQ `<h3>` 와 FAQPage JSON-LD 질문문이 **글자 단위로 일치**해야 합니다.
- JSON-LD 3종(Article · FAQPage · BreadcrumbList) 필수.

---

## 6. index.html case-card 구조 (게시 스크립트가 자동 삽입)

`automation/queue/<파일명>.meta.tsv` 의 12키로 생성됩니다.
`num cat tag title_line1 title_line2 purpose sijae gijun method value_text seo_h2 seo_p`

```html
<div class="case-card fade-up" data-cat="상속·증여" onclick="location.href='/cases/파일명.html'">
  <div class="case-card-head">
    <div class="case-num">번호</div>
    <div class="case-tag">목적 감정평가</div>
    <div class="case-title">지역<br>단지명 감정평가</div>
    <div class="case-purpose">목적</div>
  </div>
  <div class="case-card-body">
    <div class="case-meta-row">
      <div class="case-meta"><div class="case-meta-label">소재지</div><div class="case-meta-val">서울 OO구 OO동</div></div>
      <div class="case-meta"><div class="case-meta-label">기준시점</div><div class="case-meta-val">YYYY년</div></div>
      <div class="case-meta"><div class="case-meta-label">평가방법</div><div class="case-meta-val">거래사례비교법</div></div>
    </div>
    <div class="case-value-row">
      <div><div class="case-value-label">최종 감정평가액</div><div class="case-value-num">OO억 O,OOO만원</div></div>
      <div class="case-more">상세 보기 →</div>
    </div>
    <div class="case-date-badge">YYYY. MM. DD 업데이트</div>
  </div>
</div>
```

> 카드 안 `seo-content` 숨김 div 는 **더 이상 쓰지 않습니다** (5-1 참조).

### sitemap.xml 항목 (자동 추가)
```xml
<url>
  <loc>https://gaachi.co.kr/cases/파일명.html</loc>
  <lastmod>게시일(YYYY-MM-DD)</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.8</priority>
</url>
```

---

## 7. 파일 안전 규칙

1. **기존 파일을 삭제하지 않습니다.** 모든 작업은 신규 파일로.
2. 불가피하게 기존 파일을 고칠 때는 **반드시 `.bak-YYYYMMDD-HHMMSS` 백업 후**.
3. 개정은 파일명 버전을 올려 가며 (`_v2`, `_v3` …). 옛 버전은 남겨 둡니다.
4. `.gitignore` 가 `*.json` 을 제외합니다. 커밋이 필요한 데이터는 `.tsv` / `.txt` / `.md` 로.
5. `seraphic-being-*.json` (서비스 계정 키)와 `automation/sources/*.tsv`
   (의뢰인 성명이 포함된 파일 경로) 는 **절대 커밋 금지** — 이미 `.gitignore` 처리됨.
6. 한글이 들어간 `.bat` 파일 금지 — `chcp 65001` 상태에서 cmd.exe 파서가 바이트 오프셋을
   놓쳐 다음 줄을 명령으로 잘못 실행합니다. 한글 출력은 Python 이 담당하고 `.bat` 은 ASCII 로.

---

## 8. 사이트 기본 정보

| 항목 | 내용 |
|---|---|
| 사이트 | gaachi.co.kr (Cloudflare Pages) |
| GitHub | hankwonheum-bit/gaachi-website · 브랜치 main |
| 법인명 | ㈜감정평가법인 가치앤같이 |
| 사업자등록번호 | 722-81-02543 |
| 대표자 | 김지광 |
| 전화 | (02) 572-1900 / FAX (02) 572-1901 |
| 주소 | 서울특별시 서초구 강남대로 86, 5층 501호 (양재동, 가람빌딩) |
| 문의 폼 | Web3Forms → hankh129@gaachi.co.kr |

### 색인 요청
- **IndexNow** (Bing · 네이버 · Yandex) — 게시 스크립트가 자동 통보
- **Google** — sitemap.xml 갱신 + Search Console. 구글 sitemap ping 엔드포인트는 2023년
  폐기되었고, Indexing API 는 JobPosting · BroadcastEvent 전용이라 **사례 페이지에 사용 금지**
  (오용 시 계정 제재). `gsc_index.py` 는 참고용으로만 남겨 둡니다.
