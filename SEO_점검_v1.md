# SEO / AI 인용 인프라 점검 보고서 v1

- 대상: https://gaachi.co.kr (㈜감정평가법인 가치앤같이)
- 점검일: 2026-09-15
- 호스팅: Cloudflare Pages (GitHub `hankwonheum-bit/gaachi-website` / `main` 자동 배포)
- 목표: ChatGPT · Claude · Perplexity · Google AI Overviews · 네이버에서
  "감정평가", "상속 감정평가", "증여 감정평가", "아파트 감정평가 비용" 질문 시
  본 사이트가 근거로 인용되도록 하는 기술 기반 정비

---

## 🚨 최우선 조치 — Cloudflare가 AI 크롤러를 전면 차단하고 있습니다

### 무슨 일이 벌어지고 있나

저장소의 `robots.txt` 는 모든 크롤러를 허용하고 있었습니다(70 bytes).
그런데 **실제로 서비스되는 `https://gaachi.co.kr/robots.txt` 는 1,902 bytes** 이며,
Cloudflare가 파일 앞에 다음 내용을 **자동 주입**하고 있습니다.

```
# BEGIN Cloudflare Managed content

User-agent: *
Content-Signal: search=yes,ai-train=no,use=reference
Allow: /

User-agent: Amazonbot
Disallow: /

User-agent: Applebot-Extended
Disallow: /

User-agent: Bytespider
Disallow: /

User-agent: CCBot
Disallow: /

User-agent: ClaudeBot
Disallow: /

User-agent: CloudflareBrowserRenderingCrawler
Disallow: /

User-agent: Google-Extended
Disallow: /

User-agent: GPTBot
Disallow: /

User-agent: meta-externalagent
Disallow: /

# END Cloudflare Managed Content
```

즉 **GPTBot(OpenAI), ClaudeBot(Anthropic), Google-Extended(Gemini/AI Overviews),
CCBot(Common Crawl), Applebot-Extended(Apple Intelligence), meta-externalagent(Meta AI),
Amazonbot 이 전부 `Disallow: /` 로 차단**되어 있습니다.
추가로 `Content-Signal: ai-train=no` 가 선언되어 "AI 학습에 쓰지 말라"는 의사까지
명시적으로 표시되고 있습니다.

### 이것이 왜 치명적인가

- 이 프로젝트의 목표(AI가 우리 사례를 읽고 인용하게 하는 것)와 **정반대** 설정입니다.
- **저장소의 `robots.txt` 를 아무리 고쳐도 무력화됩니다.** Cloudflare 주입 블록이
  파일 앞쪽에 오고, robots.txt 는 해당 User-agent 에 가장 구체적으로 매칭되는 그룹을
  따르기 때문에, 뒤에 `Allow: /` 를 아무리 써도 앞의 `Disallow: /` 그룹이 적용됩니다.
- 이번 작업으로 저장소 `robots.txt` 를 전면 개편했지만,
  **아래 대시보드 설정을 끄기 전까지는 효과가 없습니다.**

### 끄는 방법 — 대시보드 경로 (2026년 기준, 공식 문서 확인함)

이 기능의 공식 명칭은 **"Managed robots.txt"** 입니다. 진입 경로가 두 군데 있으며,
**둘 다 확인해서 모두 꺼야** 합니다. (한쪽만 꺼도 다른 쪽이 켜져 있으면 계속 주입됩니다.)

**경로 ① — Security 설정 (주 경로)**

```
Cloudflare 대시보드 (dash.cloudflare.com)
  → 계정 선택
  → 도메인(gaachi.co.kr) 선택
  → 왼쪽 메뉴 [Security] → [Settings]
  → 상단 필터를 "Bot traffic" 으로 선택
  → "Set your preference to block training in robots.txt"
     (또는 "Instruct AI bot traffic with robots.txt") 항목을 찾아
  → 토글을 OFF
```

**경로 ② — AI Crawl Control (신규 UI)**

```
Cloudflare 대시보드
  → 계정 선택 → 도메인(gaachi.co.kr) 선택
  → 왼쪽 메뉴 [AI Crawl Control]
  → [Robots.txt] 탭 (문서에 따라 [Directives] 탭으로 표기되기도 함)
  → 상단 상태 카드의 "Use Cloudflare managed robots.txt" 토글을 OFF
```

**함께 확인할 것 — Content Signals Policy 표시**

```
도메인 [Overview] 화면 → "Control AI Crawlers" 영역
  → "Display Content Signals Policy" 체크 해제
```
이것을 해제해야 `Content-Signal: ai-train=no` 선언과 긴 법적 서문이 사라집니다.

**함께 확인할 것 — WAF 레벨 차단 (robots.txt 와 별개입니다)**

Cloudflare의 AI Crawl Control 에서 크롤러를 "Block" 으로 두면 **WAF 커스텀 룰**이
생성되어, robots.txt 와 무관하게 **네트워크 단에서 차단**됩니다.
robots.txt 만 고치면 이 부분이 남아 있을 수 있습니다.

```
[AI Crawl Control] → [Security] 탭 → [Crawlers] 탭
  → 크롤러 목록의 Actions 컬럼에서
    GPTBot / OAI-SearchBot / ChatGPT-User / ClaudeBot / Claude-SearchBot /
    Claude-User / PerplexityBot / Perplexity-User / Google-Extended /
    Applebot-Extended / CCBot / Amazonbot / meta-externalagent
    을 각각 "Allow" 로 변경
```
또한 `[Security] → [WAF] → [Custom rules]` 에서 AI 봇 관련 룰이 생성돼 있으면
비활성화하십시오.

### 끈 뒤 검증 방법

robots.txt 는 `cache-control: public, max-age=14400` (4시간) 으로 캐시됩니다.
설정을 꺼도 즉시 반영되지 않을 수 있으므로 **캐시 퍼지 후** 확인하십시오.

```
[Caching] → [Configuration] → "Purge Everything"
   (또는 Custom Purge 에 https://gaachi.co.kr/robots.txt 지정)
```

그 다음 확인:

```bash
curl https://gaachi.co.kr/robots.txt
```

**성공 판정 기준**

- 출력에 `# BEGIN Cloudflare Managed content` 가 **없어야** 합니다.
- `Disallow: /` 가 붙은 대상이 `Bytespider / SemrushBot / AhrefsBot / DotBot / MJ12bot`
  **다섯 개뿐**이어야 합니다.
- `GPTBot`, `ClaudeBot`, `Google-Extended` 밑에 `Allow: /` 가 보여야 합니다.
- 맨 위 `User-agent: *` 그룹에
  `Content-Signal: search=yes, ai-input=yes, ai-train=yes` 가 있어야 합니다.

크롤러별 실제 접근 여부는 며칠 뒤
`[AI Crawl Control] → [Directives] / [Robots.txt]` 탭에서 크롤러 준수 현황으로
교차 확인할 수 있습니다.

> **참고**: Cloudflare 커뮤니티에 "토글을 껐는데도 주입이 계속된다"는 사례가 보고되어
> 있으며, 원인은 대부분 **캐시**였습니다. 껐는데도 `curl` 결과가 그대로라면
> 4시간 대기 또는 Purge Everything 후 재확인하십시오.

---

## 🚨 두 번째 문제 — 소프트 404 (모든 없는 주소가 HTTP 200 으로 홈페이지를 반환)

### 확인된 증상

```bash
$ curl -o /dev/null -w "%{http_code} %{size_download}\n" \
    https://gaachi.co.kr/this-path-does-not-exist-12345
200 505174
```

존재하지 않는 주소인데도 **HTTP 200** 과 함께 홈페이지(505KB)가 그대로 반환됩니다.
이것을 **소프트 404** 라고 하며 다음 피해를 줍니다.

- Google Search Console 이 "소프트 404" 오류로 분류하고 색인에서 제외합니다.
- 크롤 예산이 존재하지 않는 주소를 긁는 데 낭비됩니다.
- AI 크롤러가 오타·구주소를 "유효한 페이지"로 오인해 **홈페이지 내용을 잘못된 URL에
  귀속**시킵니다. 인용 정확도가 떨어집니다.

### 원인 (추측이 아니라 확인된 사실)

저장소를 전수 조사했습니다.

- `_redirects` — **없음**
- `_headers` — **없음**
- `_routes.json` — **없음**
- `wrangler.toml` / `netlify.toml` / `package.json` / 기타 빌드 설정 — **없음**
- 즉 **저장소 안의 catch-all 리라이트 파일이 원인이 아닙니다.**

원인은 **Cloudflare Pages 의 기본 동작**입니다. 공식 문서(Pages → Serving Pages)는
다음과 같이 규정합니다.

> 프로젝트 루트에 `404.html` 이 **없으면** Pages 는 이 프로젝트를 SPA(단일 페이지
> 애플리케이션)로 간주하고, 매칭되지 않는 모든 경로에 대해 `index.html` 을
> **HTTP 200** 으로 반환한다.
>
> 루트에 `404.html` 이 **있으면** Pages 는 SPA 모드에서 빠져나와, 가장 가까운
> `404.html` 을 찾아 **HTTP 404** 로 반환한다.

이 사이트에는 `404.html` 이 없었고, 그래서 SPA 폴백이 작동한 것입니다.

### 적용한 해결책

**루트에 `404.html` 을 생성했습니다.** (이번 작업 산출물 — 아래 목록 참조)
이 파일이 배포되는 순간 Pages 의 SPA 모드가 해제되고, 없는 주소는 정상적으로
HTTP 404 를 반환합니다. **추가 설정 파일은 필요 없습니다.**

`_redirects` 파일은 **의도적으로 만들지 않았습니다.** 원인이 리라이트 규칙이 아니므로
`_redirects` 추가는 문제 해결에 기여하지 않으며, Pages 에서 `/*` 형태의 catch-all
규칙은 정상 페이지 서빙까지 가로챌 위험이 있습니다.

### 사용자가 대시보드에서 확인할 것 (배포 후에도 200이 나온다면)

배포 후에도 소프트 404 가 계속된다면, 저장소 밖 설정이 개입하는 것입니다. 순서대로 확인:

1. `[Workers & Pages] → gaachi-website 프로젝트 → [Settings] → [Build & deployments]`
   빌드 출력 디렉터리(Build output directory)가 저장소 루트를 가리키는지 확인
   (`404.html` 이 배포 산출물에 실제로 포함돼야 합니다).
2. `[Rules] → [Redirect Rules]` / `[Rules] → [Page Rules]`
   `/*` 를 `/` 또는 `/index.html` 로 보내는 catch-all 규칙이 있는지 확인 → 있으면 삭제.
3. `[Rules] → [Transform Rules] → [Rewrite URL]`
   경로를 `/` 로 재작성하는 규칙이 있는지 확인 → 있으면 삭제.
4. `[Workers & Pages]` 에서 `gaachi.co.kr/*` 라우트를 가로채는 **Worker** 가 있는지 확인.

### 검증 명령

```bash
curl -o /dev/null -w "%{http_code}\n" https://gaachi.co.kr/이런페이지는없습니다
# 기대값: 404   (현재: 200)
```

---

## ⚠️ 세 번째 문제 — 사례 3건이 홈페이지에만 있고 실제로 배포되지 않았습니다

`cases/` 폴더의 HTML 10건 중 **3건이 라이브에서 소프트 404** 상태입니다.
(= GitHub `main` 에 올라가 있지 않습니다.)

| 사례 파일 | 로컬 | 라이브 | 원인 |
|---|---|---|---|
| `cases/namyangju-byeollae-ipark-suite-2026.html` | 있음 | ❌ 소프트 404 | **커밋됐으나 push 안 됨** (로컬 커밋 1건 미푸시) |
| `cases/gangseo-magok-2026.html` | 있음 | ❌ 소프트 404 | **git 미추적(untracked)** — 커밋 자체가 안 됨 |
| `cases/dongjak-daebang-epyeonhansesang-sangsok-2026.html` | 있음 | ❌ 소프트 404 | **git 미추적(untracked)** — 커밋 자체가 안 됨 |

`sitemap.xml` 에는 남양주 사례가 이미 등재되어 있는데 실제 페이지는 없는 상태이므로,
검색엔진 입장에서는 **사이트맵이 거짓말을 하고 있는** 셈입니다.

**조치**: `git add` → `commit` → `push` 하여 세 건을 배포하십시오.
(이번 작업에서는 지시에 따라 커밋·푸시를 수행하지 않았습니다.)

---

## ⚠️ 네 번째 문제 — 사이트맵 URL 과 실제 URL 이 한 단계 어긋납니다

Cloudflare Pages 는 `.html` 확장자가 붙은 주소를 **확장자 없는 주소로 308 리다이렉트**합니다.

```bash
$ curl -I https://gaachi.co.kr/cases/gangdong-seongnae-2025.html
HTTP/2 308
location: /cases/gangdong-seongnae-2025
```

그런데 현재:

- `sitemap.xml` 은 `.../gangdong-seongnae-2025.html` (리다이렉트되는 주소)를 등재
- 각 사례 페이지의 `<link rel="canonical">` 도 `.html` 주소를 지정
- 즉 **정규 URL 로 선언한 주소가 그 자신을 다른 주소로 리다이렉트**하고 있습니다.

Google 은 canonical 이 리다이렉트되는 경우 리다이렉트 목적지를 정본으로 선택하므로
치명적이지는 않지만, **신호가 흐려지고 크롤 한 번이 낭비**됩니다.

**조치(선택, 별도 작업 필요)**: 아래 중 하나로 통일하십시오.
- (A) `sitemap.xml` 과 모든 `canonical` 을 확장자 없는 주소로 변경 — Pages 기본 동작과 일치. 권장.
- (B) 그대로 두되, 리다이렉트 1홉이 존재함을 인지 — 현상 유지도 허용 가능.

> 이번 작업에서는 `sitemap.xml` 과 `cases/` 가 수정 금지 대상이었으므로 손대지 않았습니다.
> 다만 이번에 생성한 `feed.xml` 과 `llms.txt` 는 **각 페이지의 canonical 값을 그대로
> 따르도록** 만들었으므로, canonical 을 바꾸면 스크립트 재실행만으로 자동 동기화됩니다.

`sitemap.xml` 에 등재된 `https://gaachi.co.kr/cases/yeouido-gwangjang.html`(연도 없음)은
**실물 파일이 없습니다.** 사이트맵에서 제거 대상입니다.

---

## 📦 이번에 생성·변경한 파일

| 파일 | 상태 | 역할 |
|---|---|---|
| `robots.txt` | **교체** (백업: `robots.txt.bak-20260915-075614`) | AI 인용 크롤러 20종을 각각 개별 `User-agent` 블록으로 명시 허용. `Content-Signal: search=yes, ai-input=yes, ai-train=yes` 선언. SEO 경쟁정보 크롤러 5종만 차단. |
| `404.html` | **신규** | 사이트 디자인(크림 `#F7F5F0` / 골드 `#B8935A` / Noto Serif KR + Noto Sans KR / 860px 단일 컬럼)을 그대로 따르는 한국어 404 페이지. `noindex, follow`. **이 파일의 존재 자체가 소프트 404 를 해결합니다.** |
| `feed.xml` | **신규(생성물)** | RSS 2.0 피드. 사례 10건, 최신순. `atom:link rel="self"`, `lastBuildDate`, 각 item 에 `title`/`link`/`guid isPermaLink`/`pubDate`(RFC-822)/`description`(CDATA) 포함. |
| `tools/make_feed_v1.py` | **신규** | `feed.xml` 생성기. `cases/*.html` 의 `<title>`·메타 설명·`article:published_time` 을 읽고, 없으면 `sitemap.xml` 의 `<lastmod>` 로 대체. `--check` 로 미리보기 가능. |
| `llms.txt` | **신규(생성물)** | LLM 대상 사이트 요약. 사례 10건 + 서비스 12종 + 문의처. |
| `tools/make_llms_txt_v1.py` | **신규** | `llms.txt` 생성기. 사례 추가 시 재실행만 하면 됩니다. |
| `snippets/org_schema_v1.html` | **신규** | 붙여넣기용 JSON-LD. `ProfessionalService`(`#organization`) + `WebSite`(`#website`) `@graph`. `knowsAbout` 12종, `founder` 김지광, E.164 전화·팩스, `priceRange ₩₩`, `areaServed` 3종. |
| `snippets/org_schema_v1_적용법.md` | **신규** | 위 스니펫을 `index.html` 어디에 어떻게 넣는지(= 기존 노드 **교체**) 상세 안내. |
| `SEO_점검_v1.md` | **신규** | 이 문서. |

**수정하지 않은 파일**: `index.html`, `sitemap.xml`, `cases/*`, `CLAUDE.md`, `.gitignore`,
`automation/*` (전부 수정 금지 대상이었습니다.)

**생성하지 않은 파일**:
- `_redirects` — 원인이 리라이트 규칙이 아니므로 불필요. (위 "두 번째 문제" 참조)
- `llms-full.txt` — 중복 콘텐츠 유발 + 유지비 대비 효익 없음.

---

## 📡 왜 `feed.xml` 이 `llms.txt` 보다 중요한가

78일간 서버 로그를 분석한 연구에서, **AI 크롤러가 RSS 피드를 519회 가져간 반면
llms.txt 는 7회**에 그쳤습니다. 약 74배 차이입니다.

- `llms.txt` 는 아직 **어떤 주요 AI 업체도 공식 지원을 선언하지 않은 제안 표준**입니다.
  → **낮은 확신도(low-confidence) / 보험성 파일**로 분류하십시오.
    만드는 데 15분 이상 쓰지 말고, 유지도 스크립트 재실행으로만 하십시오.
- 반면 **RSS 는 크롤러가 실제로 반복 조회하는 검증된 경로**입니다.
  신규 사례를 빠르게 알리는 실질적 수단은 `sitemap.xml` + `feed.xml` 조합입니다.

### 사례를 새로 올릴 때마다 할 일

```bash
python3 tools/make_feed_v1.py        # feed.xml 갱신
python3 tools/make_llms_txt_v1.py    # llms.txt 갱신
```
두 스크립트 모두 저장소 어느 위치에서 실행해도 동작합니다.

### 아직 하지 않은 일 (권장 후속 작업)

`index.html` 의 `<head>` 에 피드 자동발견(autodiscovery) 링크를 추가하면
크롤러가 피드를 스스로 찾아냅니다. `index.html` 이 수정 금지였으므로 넣지 않았습니다.

```html
<link rel="alternate" type="application/rss+xml"
      title="가치앤같이 감정평가법인 — 감정평가 사례"
      href="https://gaachi.co.kr/feed.xml">
```

---

## ✅ 다음 배포 후 검증 체크리스트

배포 완료(보통 1~2분) 후 순서대로 실행하십시오.

### 1. robots.txt — AI 크롤러 차단이 풀렸는가 (⚠ 대시보드 설정을 먼저 꺼야 함)

```bash
curl https://gaachi.co.kr/robots.txt
```
- [ ] `# BEGIN Cloudflare Managed content` 가 **보이지 않는다**
- [ ] `GPTBot` 아래가 `Allow: /` 이다
- [ ] `ClaudeBot` 아래가 `Allow: /` 이다
- [ ] `Google-Extended` 아래가 `Allow: /` 이다
- [ ] `Content-Signal: search=yes, ai-input=yes, ai-train=yes` 가 있다
- [ ] `Disallow: /` 는 Bytespider / SemrushBot / AhrefsBot / DotBot / MJ12bot 에만 있다

### 2. 소프트 404 해소 확인

```bash
curl -o /dev/null -w "%{http_code}\n" https://gaachi.co.kr/no-such-page-xyz
```
- [ ] **404** 가 나온다 (200 이 아니다)

```bash
curl -o /dev/null -w "%{http_code}\n" https://gaachi.co.kr/404.html
```
- [ ] 200 또는 404 로 페이지가 존재한다 (홈페이지 505KB 가 아니다)
- [ ] 브라우저로 없는 주소를 열었을 때 **가치앤같이 디자인의 404 페이지**가 보인다

### 3. feed.xml

```bash
curl -s https://gaachi.co.kr/feed.xml | head -20
```
- [ ] `<rss version="2.0"` 로 시작한다 (홈페이지 HTML 이 아니다)
- [ ] 브라우저 또는 https://validator.w3.org/feed/ 에서 오류 없이 검증된다
- [ ] item 개수가 실제 배포된 사례 수와 일치한다

### 4. llms.txt

```bash
curl -s https://gaachi.co.kr/llms.txt | head -5
```
- [ ] `# ㈜감정평가법인 가치앤같이` 로 시작한다

### 5. 구조화데이터 (`snippets/org_schema_v1.html` 적용 후)

- [ ] https://search.google.com/test/rich-results 에서 `https://gaachi.co.kr` 검사 → 오류 0
- [ ] `ProfessionalService`, `FAQPage`, `WebSite` 세 가지가 모두 인식된다
- [ ] `@id: https://gaachi.co.kr/#organization` 가 **중복되지 않는다**

### 6. 미배포 사례 3건

```bash
for f in namyangju-byeollae-ipark-suite-2026 gangseo-magok-2026 dongjak-daebang-epyeonhansesang-sangsok-2026; do
  curl -o /dev/null -w "$f %{http_code}\n" "https://gaachi.co.kr/cases/$f.html"
done
```
- [ ] 세 건 모두 **308**(→ 확장자 없는 주소) 또는 200 실제 페이지가 나온다
- [ ] 홈페이지 크기(505174 bytes)가 반환되지 않는다

### 7. 검색엔진 재수집 요청

- [ ] Google Search Console → 사이트맵 재제출, 주요 URL "색인 생성 요청"
- [ ] 네이버 서치어드바이저 → 사이트맵 제출 + 웹 수집 요청
- [ ] Bing Webmaster Tools → 사이트맵 제출 (IndexNow 는 `automation/ping_indexnow_v1.py` 담당)

### 8. 며칠 뒤 — AI 크롤러가 실제로 들어오는지 확인

- [ ] `[AI Crawl Control] → [Directives]` 또는 `[Robots.txt]` 탭에서
      GPTBot / ClaudeBot / PerplexityBot 의 요청 기록이 잡히는지 확인
- [ ] ChatGPT·Claude·Perplexity 에 직접 "상속 감정평가 사례"를 질문해
      gaachi.co.kr 이 인용되는지 관찰 (반영에 수 주 소요)

---

## 📌 사용자가 직접 채워야 하는 미확정 값

| 항목 | 위치 | 상태 |
|---|---|---|
| 네이버 플레이스 URL | `snippets/org_schema_v1.html` 의 `sameAs` | **미확인 — 직접 확인 필요** |
| 카카오맵 업체 페이지 URL | 같음 | **미확인 — 직접 확인 필요** |
| 유튜브 채널 URL | 같음 | **미확인 — 직접 확인 필요** |

추측한 URL 을 넣으면 엔티티 신뢰도가 오히려 떨어집니다. 실제 접속해 확인한 것만
넣고, 없으면 `sameAs` 키 자체를 생략하십시오. 자세한 절차는
`snippets/org_schema_v1_적용법.md` 4장을 참조하십시오.

> **네이버 플레이스 등록이 아직이라면, 그것이 이 목록에서 가장 우선순위 높은 과제입니다.**
> 국내 감정평가 문의의 상당수가 네이버에서 출발하며, 네이버 플레이스는 AI 모델이
> "실재하는 사업체"를 판정하는 강력한 제3자 근거가 됩니다.

---

## 우선순위 요약

| 순위 | 조치 | 담당 | 소요 |
|---|---|---|---|
| 1 | Cloudflare **Managed robots.txt** OFF + Content Signals 해제 + WAF AI 봇 Allow | 대시보드 | 10분 |
| 2 | 이번 생성 파일들 커밋 & 푸시 (특히 `404.html`) | git | 5분 |
| 3 | 미배포 사례 3건 커밋 & 푸시 | git | 5분 |
| 4 | `snippets/org_schema_v1.html` 을 `index.html` 에 적용 | 수동 편집 | 15분 |
| 5 | 네이버 플레이스 / 카카오맵 확인 후 `sameAs` 채우기 | 조사 | 20분 |
| 6 | `index.html` `<head>` 에 RSS autodiscovery `<link>` 추가 | 수동 편집 | 2분 |
| 7 | `sitemap.xml` 정리 (없는 `yeouido-gwangjang.html` 제거, 미등재 사례 추가, URL 형식 통일) | 별도 작업 | 15분 |

---

### 참고 자료

- Cloudflare — Managed robots.txt: https://developers.cloudflare.com/bots/additional-configurations/managed-robots-txt/
- Cloudflare — AI Crawl Control: https://developers.cloudflare.com/ai-crawl-control/
- Cloudflare — AI Crawl Control / robots.txt 추적: https://developers.cloudflare.com/ai-crawl-control/features/track-robots-txt/
- Cloudflare — AI 크롤러 관리(Allow/Block, WAF 연동): https://developers.cloudflare.com/ai-crawl-control/features/manage-ai-crawlers/
- Cloudflare Pages — Serving Pages (404 / SPA 폴백 규칙): https://developers.cloudflare.com/pages/configuration/serving-pages/
- Cloudflare 블로그 — AI 학습 콘텐츠 이용 통제: https://blog.cloudflare.com/control-content-use-for-ai-training/
