# 가치앤같이 감정평가법인 — 홈페이지 사례 업로드 가이드

새 감정평가 사례 PDF가 들어오면 아래 1~4단계를 순서대로 전부 진행한다.
사용자가 별도 지시를 하지 않아도 각 단계가 끝나면 다음 단계로 이어서 진행한다.

---

## 1단계 — 사례 HTML 작성 (draft)

### 기본 흐름
1. PDF에서 텍스트/OCR 추출 → 감정평가 정보 파악
2. 물건 유형에 따라 기존 사례 파일을 템플릿으로 사용:
   - **집합건물(아파트·오피스텔 등)** → `cases/yangcheon-mokdong-2025.html` 참고
   - **토지·건물** → `cases/seongbuk-dongseondong-2025.html` 참고
   - 가장 최근 작성된 사례를 참고하는 것이 좋음
3. 저장 위치: 작업 폴더 내 `(작업일자)/draft/파일명.html`
4. 파일명 규칙: `구-동-단지명약어-연도.html` (영문 소문자, 하이픈 구분)
   - 예: `dongjak-daebang-epyeonhansesang-2026.html`

### 개인정보 처리 규칙 (반드시 준수)
| 항목 | 처리 방법 |
|------|-----------|
| 의뢰인·소유자 성명 | 완전 삭제 |
| 본건 층수 | `제<span class="addr-mask">█</span>층` |
| 본건 호수 | `<span class="addr-mask">███</span>호` |
| 보고서 번호 | 표시 안 함 |
| 감정평가전례 기준시점 | 연도만 표시 (예: `2025년`) |
| 감정평가전례 목적 | `—` 처리 |
| 비교사례 층수 | 삭제 (동/호만 표시) |

### CSS/레이아웃 규칙
- `comp-table th`, `comp-table td`: `white-space: nowrap` 필수
- 모든 테이블은 `<div style="overflow-x:auto;">` 로 감싸기
- ※ 채택 비교사례 문단: 삭제
- `case-tag` 및 감정평가목적: 실제 목적 반영 (상속/증여/담보 등)
- SEO 키워드 숨김 span: `color:var(--bg); font-size:1px;`
- HTML 주석은 반드시 `<!--` 형식 사용 (`<\!--` 오타 주의, 생성 후 grep으로 확인)

---

## 2단계 — 사이트 파일 업데이트

작업 폴더 내 `(작업일자)/` 폴더에 아래 파일들을 준비한다.

### 업데이트 대상 파일
1. **사례 HTML** → `(작업일자)/cases/파일명.html` 에 저장
2. **index.html** → 새 case-card 추가 (번호 순차)
3. **sitemap.xml** → 새 URL 항목 추가

### index.html case-card 구조
```html
<div class="case-card fade-up" data-cat="상속·증여" onclick="location.href='/cases/파일명.html'">
  <div class="case-card-head">
    <div class="case-num">번호</div>
    <div class="case-tag">목적 감정평가</div>
    <div class="case-title">지역<br>단지명 감정평가</div>
    <div class="case-purpose">목적 및 세무서 제출 목적</div>
  </div>
  <div class="case-card-body">
    <div class="case-meta-row">
      <div class="case-meta"><div class="case-meta-label">소재지</div><div class="case-meta-val">서울 OO구 OO동</div></div>
      <div class="case-meta"><div class="case-meta-label">기준시점</div><div class="case-meta-val">YYYY. MM. DD</div></div>
      <div class="case-meta"><div class="case-meta-label">평가방법</div><div class="case-meta-val">거래사례비교법</div></div>
    </div>
    <div class="case-value-row">
      <div><div class="case-value-label">최종 감정평가액</div><div class="case-value-num">OO억 O,OOO만원</div></div>
      <div class="case-more">상세 보기 →</div>
    </div>
    <div class="case-date-badge">YYYY. MM. DD 업데이트</div>
  </div>
  <!-- SEO: 크롤러용 상세 내용 -->
  <div class="seo-content">
    <h2>사례 제목</h2>
    <p>주요 내용 요약 (소재지, 목적, 면적, 평가방법, 산정단가, 최종평가액, 공법상 제한 등)</p>
    <p>감정평가법인: 가치앤같이 감정평가법인 (서울특별시 서초구 강남대로 86, 5층, 양재동 가람빌딩)</p>
    <p>문의: (02) 572-1900</p>
  </div>
</div>
```

### sitemap.xml 신규 항목
```xml
<url>
  <loc>https://gaachi.co.kr/cases/파일명.html</loc>
  <lastmod>작업일자(YYYY-MM-DD)</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.8</priority>
</url>
```

---

## 3단계 — GitHub 업로드

- 저장소: `hankwonheum-bit/gaachi-website`
- 변경된 파일들을 커밋하고 push
- **주의**: `seraphic-being-493407-k0-e942184375bc.json` (서비스 계정 키)는 `.gitignore`에 등록되어 있으므로 절대 커밋하지 않음
- 커밋 메시지 형식: `feat: [지역] [단지명] [목적] 감정평가 사례 추가 (#번호)`
  - 예: `feat: [동작구] 대방1차이-이편한세상 증여 감정평가 사례 추가 (#06)`

---

## 4단계 — Google Search Console 색인 요청

1. `gsc_index.py` 파일의 `URLS_TO_INDEX` 리스트에 새 URL 추가
2. 저장소 폴더에서 PowerShell 열기 (Shift + 우클릭 → "여기서 PowerShell 창 열기")
3. 실행:
   ```
   python gsc_index.py
   ```
4. "성공!" 메시지 확인
5. Google 색인 반영까지 수일~2주 소요

> **참고**: 페이지 내용을 수정한 경우에도 gsc_index.py를 다시 실행하여 재색인 요청을 보낸다.

---

## 사이트 기본 정보

| 항목 | 내용 |
|------|------|
| 사이트 | gaachi.co.kr |
| GitHub 저장소 | hankwonheum-bit/gaachi-website |
| 사업자등록번호 | 722-81-02543 |
| 대표자 | 김지광 |
| 전화 | (02) 572-1900 / FAX (02) 572-1901 |
| 주소 | 서울특별시 서초구 강남대로 86, 5층 501호 (양재동, 가람빌딩) |
| GSC 서비스 계정 | gaachi-seo@seraphic-being-493407-k0.iam.gserviceaccount.com |
