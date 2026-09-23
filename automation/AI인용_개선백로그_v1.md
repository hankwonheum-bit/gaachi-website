# AI 인용(GEO) 개선 백로그 v1

> 목적: ChatGPT·Claude·Perplexity·구글 AI 개요가 **gaachi.co.kr 의 감정평가 사례를 인용**하게 만든다.
> 이 문서는 매일 사례를 쌓으면서 **함께 개선해 나갈 과제 목록**입니다. 조치할 때마다 「완료」로 옮기고 날짜를 적으십시오.
> 최초 작성: 2026-09-22 (AI 인용 최적화 감사 결과 반영)

---

## 0. 판단 기준 — 무엇을 먼저 할 것인가

조사에서 확인된 가장 중요한 사실 두 가지입니다. 새 과제를 넣을 때 이 기준으로 우선순위를 매기십시오.

1. **검색 순위·색인이 AI 인용을 압도한다.** C-SEO Bench(arXiv:2506.11097)는 "AI를 겨냥한 기법 대부분은 효과가 없거나 오히려 순위를 떨어뜨린다"고 반증했고, 가장 효과적인 것은 **전통적 색인·순위**였습니다. 인용률은 검색 1위 43~58% vs 7~10위 5~14%로 순위 효과가 마크업 효과를 압도합니다.
   → **색인에 제대로 올라가는 일**(canonical·sitemap·Bing·네이버)이 GEO 전술보다 우선입니다.
2. **문서 구조는 예외적으로 근거가 단단하다.** GEO-SFE(arXiv:2603.29979)는 문서 구조 최적화만으로 6개 생성형 엔진에서 **인용률 +17.3%** 를 보고했습니다. h2/h3 계층, 섹션별 자기완결 청크가 여기 해당합니다.

**반대로, 투자해도 효과가 확인되지 않은 것**: 스키마 추가(인프라일 뿐 성장 레버 아님 — 통제된 연구에서 효과 없음 또는 미세한 음의 효과), llms.txt(Ahrefs 13.7만 도메인 분석에서 **97%가 요청 0건**).

---

## 1. 완료 (2026-09-22)

| # | 항목 | 내용 | 근거 |
|---|------|------|------|
| ✅ | **숨김 텍스트 전면 제거** | `index.html` 의 `seo-content` 숨김 블록 10개 + CSS, `cases/` 6개 파일의 `font-size:1px` 키워드 스팬 제거 | 구글 스팸정책(hidden text) — 사이트 전체 수동조치 위험 |
| ✅ | **게시 엔진의 숨김블록 생성 중단** | `publish_case_v1.py` 의 `build_card()` 가 더 이상 `seo-content` 를 만들지 않음 | 위 조치가 되살아나는 것을 막음 |
| ✅ | **홈 → 사례 크롤 가능 링크** | 카드 10개에 `<a href="/cases/<slug>">` 추가(앵커 텍스트는 사례 설명). 게시 엔진도 신규 카드에 자동 삽입 | AI 크롤러는 JS 미실행 → `onclick` 만으로는 사례 페이지가 발견되지 않음 |
| ✅ | **URL 정본 통일** | `.html`(308 리다이렉트) → 확장자 없는 200 URL 로 전면 변경. canonical·og:url·hreflang·JSON-LD·내부링크·sitemap·feed·llms.txt·게시엔진·검증기 전부 | canonical 이 리다이렉트를 가리키면 안 됨. 크롤 예산 낭비 |
| ✅ | **h2/h3 승격** | 구 템플릿 사례 10건의 `<div class="section-title">` → `<h2>`, FAQ/평가방법 소제목 → `<h3>`. 외관 무변화(CSS 리셋) | GEO-SFE 인용률 +17.3% |
| ✅ | **색인 파일 3종 동기화** | sitemap 13 URL(유령 URL 제거) / feed 12건(3개월 정체 해소) / llms.txt 12건. lastmod 를 페이지 실제 날짜로 재동기화 | 4개 목록이 전부 달랐음 |
| ✅ | **파일 손상 복구** | `gangnam-ilwon-woosungchapt-2025.html`(11,937B), `dongjak-…-sangsok-2026.html`(1,224B) 의 NUL 바이트 제거 | 파서·CDN 오동작 |
| ✅ | **엔터티 정리** | `RealEstateAgent` 중복 노드를 `@type` 배열로 통합, `WebSite` 노드 신설 | 한 회사가 두 엔터티로 분리 인식되던 문제 |
| ✅ | **검증 불가 주장 제거** | JSON-LD FAQ 의 "100% 법원 채택률" 문구 삭제 | 구조화 데이터 신뢰성 |
| ✅ | **RSS 자동발견** | `index.html` `<head>` 에 `rel="alternate" type="application/rss+xml"` 추가 | |
| ✅ | **템플릿 v5 / 필드정의 v4 / 생성지침 v4** | 신규 사례부터 위 개선이 자동 적용. 요약 섹션·표 caption·본문 법령 링크·`citation`(Legislation)·`spatialCoverage`·FAQ 기본 펼침 반영 | |

> ⚠ **이 변경들은 저장소에만 반영되어 있습니다.** 다음 게시(`publish_case_v1.py` 실행)가 git 커밋·푸시할 때 라이브에 올라갑니다.

---

## 2. 남은 과제 — 사용자 작업 필요 (계정 개설·대시보드)

Claude 가 대신 할 수 없는 항목입니다. 효과 대비 소요 시간이 가장 짧습니다.

| 우선 | 항목 | 왜 | 어떻게 |
|------|------|-----|--------|
| **상** | **Bing Webmaster Tools 등록** | ChatGPT 검색은 **Bing 인덱스 의존도가 높음**. Bing 색인 여부가 Google 순위보다 ChatGPT 가시성의 더 강한 예측 변수 | bing.com/webmasters → 사이트 추가 → sitemap.xml 제출 |
| **상** | **IndexNow 키 발급 + 게시 스크립트 연결** | 매일 발행 모델에서 색인 지연 = 인용 기회 상실. `automation/ping_indexnow_v1.py` 가 이미 있으므로 **키만 발급하면 연결 가능** | bing.com/indexnow 에서 키 발급 → `https://gaachi.co.kr/<key>.txt` 배치 |
| **상** | **네이버 서치어드바이저 등록** | 네이버 블로그가 robots.txt 로 GPTBot·PerplexityBot 을 **전면 차단** → 한국어 감정평가 전문 콘텐츠의 AI 공급이 구조적으로 부족. 개방형 자체 도메인인 이 사이트가 그 공백을 정확히 겨냥 | searchadvisor.naver.com → 소유확인 → sitemap.xml + feed.xml 제출 |
| **상** | **Cloudflare 봇 설정 분기 1회 점검** | 2026-09-15 자로 Cloudflare 가 AI 크롤러 기본 차단을 확대(검색 크롤러는 허용, 학습·mixed-use 는 차단). 대시보드 설정이 robots.txt 를 무력화할 수 있음 | Security → Bots → AI Crawl Control. **2026-09-22 실측 시점에는 전 크롤러 200 정상** |
| 중 | **외부 프로필 개설 후 `sameAs` 채우기** | AI 엔진은 자체 콘텐츠보다 **외부 언급(earned media)에 체계적 편향**(arXiv:2509.08919). 현재 `sameAs` 0개 | 순서: ① 네이버 스마트플레이스 ② Google 비즈니스 프로필 ③ 한국감정평가사협회 법인 페이지. **상호·주소·전화를 홈페이지와 글자 단위로 동일하게** 맞춘 뒤 추가 |
| 낮 | 위키데이터 항목 | 저명성(notability) 기준상 **독립 2차 출처 2건 이상** 필요. 없으면 삭제되고 반복 시 계정 제재 | 국토부 감정평가법인 등록정보·협회 명부를 출처로 붙일 수 있을 때만 |

---

## 3. 남은 과제 — 저장소 작업

| 우선 | 항목 | 내용 |
|------|------|------|
| **상** | **`/cases/` 허브 페이지 신설** | 현재 사례 목록 전용 페이지가 없어 `templates/case_template_v5.html` 의 `{{HUB_URL}}` 블록이 매 초안마다 삭제되고 있음. `ItemList` 스키마 + 지역별·목적별 필터. `meta.tsv` 의 `seo_h2`·`seo_p` 를 여기서 활용 |
| **상** | **`index.html` 경량화** | 홈 497KB. 사례가 100건이 되면 5MB. 허브 페이지 신설과 함께 홈에는 최신 3~5건만 |
| 중 | **`yeouido-gwangjang-2025.html` 재작성** | 12건 중 유일하게 JSON-LD 1개(Article만), 본문 1,482자(평균의 1/3), FAQPage·BreadcrumbList·hreflang 없음. **인바운드 링크는 6개로 가장 많은데 품질은 가장 낮음** → v5 템플릿으로 재작성 |
| 중 | **구 사례 10건에 섹션별 자기완결 요약 + 본문 법령 링크 적용** | h2 승격은 끝났으나 내용은 아직 v3 수준. 신규 사례를 만들면서 **하루 1건씩 점진적으로** 손보는 방식 권장 |
| 중 | **`publish_case_v1.py` 가 feed.xml·llms.txt 도 재생성하도록 연결** | 현재 sitemap·index 만 갱신. `tools/make_feed_v1.py`·`make_llms_txt_v1.py` 가 이미 있으나 호출되지 않아 목록이 계속 어긋남 |
| 중 | **화면에 보이는 검증 불가 주장 정리** | JSON-LD 는 정리했으나 히어로 섹션에 `100% 법원 채택률`, `3,000+ 누적 평가 건수` 가 남아 있음. 근거가 있으면 출처를, 없으면 문구 조정 |
| 낮 | **`.bak` 파일 배포 제외** | `cases/` 에 백업 12개, 루트에 다수. 링크·sitemap 어디에도 없어 발견 가능성은 낮지만, **구 버전 숨김 텍스트가 들어 있으므로** robots.txt 차단 또는 배포 제외 설정 권장 |
| 낮 | feed.xml `description` 회사명 표기 통일 | 구 사례 10건 `가치앤같이 감정평가법인.` / 신규 2건 `㈜감정평가법인 가치앤같이.` 혼용 |
| 낮 | `verify_template_v3.py` 파일명 | 이름은 v3 이나 v5 템플릿을 검증. 혼동 소지 |

---

## 4. 하지 말 것 (근거 있는 금지)

| 금지 | 이유 |
|------|------|
| **자사 `aggregateRating`·`review` 마크업** | 구글 공식: 평가 대상이 리뷰를 통제하면 **리치리절트 부적격**이며 구조화 데이터 수동조치 사유. 제3자(네이버 플레이스) 평점을 가져와 마크업하는 것도 동일하게 부적격 → `sameAs` 로 AI가 직접 확인하게 하는 것이 정답 |
| **숨김 텍스트·키워드 스터핑** | 효과가 음(−)이며 사이트 전체 수동조치 대상 |
| **`llms-full.txt` 제작** | 비표준, 소비자 사실상 없음, 중복 콘텐츠 위험만 |
| **llms.txt 에 추가 투자** | 실측 효용 거의 없음. 같은 시간을 문서 구조·색인에 쓰는 편이 기대값이 훨씬 높음. (이미 있으니 유지·동기화만) |
| **`speakable` 스키마** | 뉴스 퍼블리셔 한정 기능. 감정평가법인은 대상 아님 |
| **`Product`/`Offer` 로 감정평가액 마크업** | 감정평가액은 판매가격이 아님. 오해 소지 |
| **Google Indexing API 사용** | JobPosting·BroadcastEvent 전용. 오용 시 계정 제재 (`CLAUDE.md` §8) |
| **템플릿 문구만 바꾼 사례 양산** | 구글 **scaled content abuse**. 각 사례마다 ① 그 건 고유의 방법 선택 근거 ② 실제 비교사례 수치 ③ 그 물건 고유 특수사항 중 최소 1개는 실질 서술이 있어야 안전 |
| **개인정보 공개범위 완화** | 현행 마스킹 정책 유지. E-E-A-T 보강이 필요하면 **개별 사건 담당자 대신 법인 대표 평가사 소개 페이지**(`Person` 스키마 + `Organization.founder`)로 해결 |

---

## 5. 측정 — 효과를 어떻게 확인하는가

측정 없이는 위 조치들의 효과를 알 수 없습니다. **인용 자체를 KPI로 삼고 트래픽은 후행 지표로** 다루십시오
(Perplexity 인용 중 실제 클릭은 12~18%에 불과하고, Google AI Mode 는 `noreferrer` 라 GA4 에 아예 안 잡힙니다).

| 계층 | 방법 | 무엇을 보는가 |
|------|------|--------------|
| **1. 서버 로그 (가장 신뢰도 높음)** | Cloudflare **AI Crawl Control** 대시보드 또는 Logpush | `ChatGPT-User`·`Claude-User`·`Perplexity-User` 히트 = **지금 누군가의 AI 답변에 우리 페이지가 들어갔다**는 거의 직접 증거. `*-SearchBot` = 색인 커버리지 |
| 2. GA4 | 채널 그룹 "AI Search" 신설, Referral source 정규식 `chatgpt\.com\|perplexity\.ai\|claude\.ai\|gemini\.google\.com\|copilot\.microsoft\.com` | 클릭 유입만. 모바일 앱 유입은 Direct 로 섞임 |
| 3. GSC / Bing WMT | 색인 상태·노출 | AI Overviews 노출은 일반 오가닉에 섞여 분리 불가 |
| **4. 월 1회 수동 감사 (30분)** | 고정 프롬프트 20개를 ChatGPT/Claude/Perplexity/구글 AI 모드/네이버 AI 에 매월 같은 날 질의 | **인용 여부·인용된 URL·경쟁사 인용 수** 를 기록. 로그아웃·시크릿 모드로 개인화 제거 |

**고정 프롬프트 예시**: 상속 감정평가 비용 / 강남 아파트 상속세 감정평가 사례 / 증여 감정평가 기준시점 / 세무서 제출용 시가인정액 감정평가 / 감정평가법인 추천 서울 / 아파트 상속 감정평가 어떻게 / 상속재산 감정평가 언제까지 / 시가인정액 이란

---

## 6. 정기 점검 루틴 (권장 주기)

| 주기 | 할 일 |
|------|------|
| 매일 | 사례 초안 생성(자동). 여유가 있으면 **구 사례 1건을 v5 수준으로 보강** |
| 주 1회 | 색인 파일 3종(sitemap·feed·llms) ↔ `cases/` 실제 파일 대조 |
| 월 1회 | §5 의 고정 프롬프트 감사. AI 크롤러 히트 수 추이 확인 |
| 분기 1회 | Cloudflare 봇 설정 실측(`curl -A "…OAI-SearchBot…"` 으로 200 확인). robots.txt 라이브 서빙 확인 |
| 수시 | AI 검색 정책·크롤러 변경 뉴스 확인 → 이 문서에 반영 |

**실측 명령 (분기 점검용)**
```bash
for ua in "OAI-SearchBot/1.0" "Claude-SearchBot/1.0" "PerplexityBot/1.0" "Googlebot/2.1"; do
  echo -n "$ua : "
  curl -sS -o /dev/null -w '%{http_code}\n' --max-time 20 -A "Mozilla/5.0 (compatible; $ua)" https://gaachi.co.kr/
done
```
전부 `200` 이어야 합니다.

---

## 7. 참고 자료

- GEO 원논문 — arXiv:2311.09735 (인용·통계·인용구 추가가 가시성 최대 40% 상승)
- **반증** — C-SEO Bench, arXiv:2506.11097 (AI 겨냥 기법 대부분 무효·역효과, 전통 SEO 우위)
- 문서 구조 — GEO-SFE, arXiv:2603.29979 (구조 최적화로 인용률 +17.3%)
- 외부 언급 편향 — arXiv:2509.08919
- 스키마↔인용 증거 리뷰 — https://www.danielkcheung.com/musings/schema-ai-citations-evidence-review
- llms.txt 실측 — https://www.mecanik.dev/en/posts/does-llms-txt-do-anything-yet/
- 구글 스팸정책 — https://developers.google.com/search/docs/essentials/spam-policies
- 구글 리뷰 스니펫 정책(자사 리뷰 금지) — https://developers.google.com/search/docs/appearance/structured-data/review-snippet
- 구글 AI 기능 대응 — https://developers.google.com/search/docs/appearance/ai-features
- OpenAI 크롤러 — https://developers.openai.com/api/docs/bots
- Anthropic 크롤러 — https://support.claude.com/en/articles/8896518
- Perplexity 크롤러 — https://docs.perplexity.ai/guides/bots
