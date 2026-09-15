# org_schema_v1.html 적용법

작성일: 2026-09-15 / 대상 파일: `snippets/org_schema_v1.html`

> **이 문서는 안내서입니다. 자동화 스크립트가 `index.html` 을 대신 수정하지 않았습니다.**
> 아래 절차에 따라 직접 편집하십시오. 편집 전 반드시 백업을 만드십시오.

---

## 0. 먼저 알아야 할 것 — 그냥 "추가"하면 안 됩니다

`index.html` 에는 **이미 JSON-LD 블록이 존재합니다** (아래 "현재 상태" 참조).
그 안에 `"@id": "https://gaachi.co.kr/#organization"` 를 가진
`ProfessionalService` 노드가 이미 들어 있습니다.

여기에 새 스니펫을 **추가**하면 같은 `@id` 를 가진 노드가 두 개가 되어
Google·Bing 이 어느 쪽을 정본으로 볼지 판단하지 못합니다.

따라서 **추가가 아니라 교체**입니다.

---

## 1. 현재 상태 (2026-09-15 기준 `index.html`)

```
 241  <script type="application/ld+json">
 242  {
 243    "@context": "https://schema.org",
 244    "@graph": [
 245      {
 246        "@type": "ProfessionalService",        ← 교체 대상 ①
 247        "@id": "https://gaachi.co.kr/#organization",
 ...
 264      },
 265      {
 266        "@type": "FAQPage",                    ← 그대로 보존 (건드리지 말 것)
 ...
 309      },
 310      {
 311        "@type": "RealEstateAgent",            ← 교체 대상 ② (삭제)
 ...
 315      }
 316    ]
 317  }
 318  </script>
 319  </head>
 320  <body>
```

- **241~318행** 이 기존 JSON-LD 블록 전체입니다.
- **245~264행** = 낡은 `ProfessionalService` 노드 (전화번호 국제표기 없음, 팩스 없음,
  `priceRange` 없음, `areaServed` 가 문자열 하나, `knowsAbout` 7개, `founder` 없음).
- **265~309행** = `FAQPage` 노드. **홈페이지 FAQ 리치결과의 근거이므로 반드시 보존합니다.**
- **310~315행** = `RealEstateAgent` 노드. 감정평가법인은 부동산 중개업자(`RealEstateAgent`)가
  아니므로 부정확합니다. `ProfessionalService` 로 일원화하면서 **삭제**합니다.

> ⚠ 행 번호는 `index.html` 을 다른 작업으로 수정하면 밀립니다.
> 편집 직전에 에디터에서 `"@type": "ProfessionalService"` 를 검색해 실제 위치를 다시 확인하십시오.

---

## 2. 적용 절차

### 2-1. 백업

편집 전 `index.html` 을 같은 폴더에 백업합니다. (기존 백업 관례와 동일한 이름 규칙)

```
index.html  →  index.html.bak-YYYYMMDD
```

### 2-2. 편집

1. `snippets/org_schema_v1.html` 을 텍스트 에디터로 엽니다.
2. `<script type="application/ld+json">` 부터 `</script>` 까지 **JSON 본문만** 복사합니다.
   (파일 맨 위 `<!-- ... -->` HTML 주석은 안내문이므로 복사하지 않습니다.)
3. `index.html` 에서 다음과 같이 병합합니다.

   - **삭제**: 기존 `ProfessionalService` 노드 (위 표의 245~264행, `{` 부터 `},` 까지)
   - **삭제**: 기존 `RealEstateAgent` 노드 (310~315행, 앞의 콤마 포함)
   - **삽입**: 새 스니펫의 `@graph` 안에 있는 **`ProfessionalService` 노드**와
     **`WebSite` 노드** 두 개를, 기존 `@graph` 배열의 `FAQPage` 노드 **앞과 뒤**에 넣습니다.

### 2-3. 최종적으로 완성되어야 하는 형태

`index.html` 의 `</head>` 바로 위 JSON-LD 블록이 다음 구조가 되면 정상입니다.

```
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    { "@type": "ProfessionalService", "@id": ".../#organization", ... },   ← 새 스니펫에서 가져옴
    { "@type": "FAQPage", "mainEntity": [ ... ] },                          ← 기존 것 그대로 보존
    { "@type": "WebSite", "@id": ".../#website", "publisher": { "@id": ".../#organization" } }
                                                                            ← 새 스니펫에서 가져옴
  ]
}
</script>
</head>
```

**JSON 문법 체크포인트**

- `@graph` 배열의 각 노드 사이에는 콤마(`,`)가 있어야 합니다.
- **마지막 노드 뒤에는 콤마가 없어야 합니다.** (가장 흔한 실수)
- JSON 에는 주석(`//`, `/* */`)을 쓸 수 없습니다.
  스니펫 파일의 안내 주석은 `<script>` **바깥**의 HTML 주석이므로 복사하지 마십시오.

### 2-4. 대안 — 병합이 부담스러운 경우

기존 블록을 건드리지 않고, **`</head>` 바로 앞(319행 직전)에 새 `<script>` 블록을 통째로
추가**하는 방법도 가능합니다. 다만 그 경우에도 **기존 `ProfessionalService` 노드와
`RealEstateAgent` 노드는 반드시 삭제**해야 `@id` 중복이 생기지 않습니다.
두 개의 `<script type="application/ld+json">` 블록이 한 페이지에 있는 것 자체는 유효합니다.

---

## 3. 새 스니펫이 기존 대비 개선하는 점

| 항목 | 기존 | 신규 |
|---|---|---|
| `name` | 가치앤같이 감정평가법인 | ㈜감정평가법인 가치앤같이 (법인 정식 상호) |
| `alternateName` | 영문 사명 | 가치앤같이 감정평가법인 (실제 통용 별칭) |
| `telephone` | `02-572-1900` | `+82-2-572-1900` (E.164 국제표기 — 해외 크롤러 파싱용) |
| `faxNumber` | 없음 | `+82-2-572-1901` |
| `streetAddress` | 강남대로 86, 5층 | 강남대로 86, 5층 501호 (양재동, 가람빌딩) |
| `priceRange` | 없음 | `₩₩` (구글 로컬 리치결과 권장 필드) |
| `areaServed` | `"서울특별시"` 문자열 1개 | 서울특별시 / 경기도 / 대한민국 (구조화 객체 3개) |
| `knowsAbout` | 7개 | 12개 (상속·증여·취득세·특수관계인·법원촉탁·담보·경매·보상·재개발·무형자산·기계기구) |
| `contactPoint` | 없음 | 있음 (문의 URL 연결) |
| `founder` | 없음 | 대표자 김지광 (`Person`, jobTitle 대표) |
| `WebSite` 노드 | 없음 | 있음 (`inLanguage: ko`, `publisher` → `#organization`) |
| `RealEstateAgent` | 있음 (부정확) | 제거 |

---

## 4. ⚠ 사용자가 직접 확인해서 채워야 하는 값 — `sameAs`

새 스니펫에는 `sameAs` 가 **의도적으로 빠져 있습니다.**
확인되지 않은 URL 을 넣으면 오히려 엔티티 신뢰도를 떨어뜨리기 때문입니다.

다음 URL 을 **실제로 접속해 확인한 뒤에만** 추가하십시오.

| # | 채널 | 상태 | 확인 방법 |
|---|---|---|---|
| 1 | 네이버 플레이스(네이버 지도 업체 페이지) | **미확인** | 네이버 지도에서 "가치앤같이 감정평가법인" 검색 → 업체 페이지 URL 복사 |
| 2 | 카카오맵 업체 페이지 | **미확인** | 카카오맵에서 상호 검색 → 상세 페이지 URL 복사 |
| 3 | 유튜브 채널 | **미확인** | 채널이 있을 경우에만 |
| 4 | 네이버 블로그 / 인스타그램 등 (선택) | **미확인** | 운영 중인 경우에만 |

추가 위치: `"founder"` 객체의 닫는 `}` 다음에 콤마를 찍고 아래를 삽입합니다.

```json
      ,
      "sameAs": [
        "https://map.naver.com/... (실제 네이버 플레이스 URL)",
        "https://place.map.kakao.com/... (실제 카카오맵 URL)"
      ]
```

**해당 채널이 없다면 `sameAs` 키 자체를 넣지 않는 것이 맞습니다.**

`sameAs` 는 AI 인용 관점에서 중요도가 높은 필드입니다.
네이버 플레이스·카카오맵 같은 공신력 있는 제3자 페이지와 홈페이지를 같은 엔티티로
묶어 주면, AI 모델이 "이 법인은 실재하는 사업체"라고 판정할 근거가 됩니다.
**네이버 플레이스 등록이 아직이라면 등록 자체가 최우선 과제입니다.**

---

## 5. 적용 후 검증

배포(Cloudflare Pages 자동 배포) 완료 후:

1. **구조화데이터 오류 검사**
   https://search.google.com/test/rich-results 에 `https://gaachi.co.kr` 입력
   → `ProfessionalService`, `FAQPage`, `WebSite` 가 모두 인식되고 오류 0건이어야 합니다.

2. **스키마 문법 검사**
   https://validator.schema.org/ 에 같은 URL 입력 → Errors 0.

3. **JSON 파싱 확인 (로컬, 배포 전에도 가능)**
   ```
   python3 -c "import re,json,io; s=io.open('index.html',encoding='utf-8').read(); [json.loads(m) for m in re.findall(r'<script type=\"application/ld\+json\">(.*?)</script>', s, re.S)]; print('JSON-LD OK')"
   ```
   오류 없이 `JSON-LD OK` 가 출력되어야 합니다. 콤마 실수를 가장 빨리 잡는 방법입니다.

4. **Google Search Console** → 페이지 → 구조화된 데이터 항목에서 며칠 후 재확인.
