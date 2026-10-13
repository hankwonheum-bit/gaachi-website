#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_cases_index_v1.py — gaachi.co.kr 사례 허브(`cases/index.html`) 동기화 생성기

왜 필요한가
-----------
허브 `cases/index.html` 은 2026-09-23 에 사례 15건으로 **수동 생성**된 뒤
자동 갱신 대상이 아니었다. `tools/make_feed_v1.py`·`make_llms_txt_v1.py` 는
매 게시마다 재생성되지만 허브를 갱신하는 코드는 어디에도 없었고, 그 사이
게시 5건이 쌓여 **허브만 15건 / 색인 3종은 20건** 으로 벌어졌다
(2026-10-06 실측, 백로그 §3). 허브는 사례의 크롤 진입점이므로 최신 사례가
빠지면 내부 링크로 발견되지 않는다.

설계 — 왜 '전체 재생성'이 아니라 '마커 블록 동기화' 인가
--------------------------------------------------------
허브 카드 중 11건은 `meta.tsv` 가 없는 구 사례이고(게시 엔진 도입 전),
카드마다 손으로 쓴 `case-basis` 문장이 들어 있다. 페이지를 통째로 다시 찍으면
그 서술이 사라진다. 그래서 이 생성기는
  * **기존 카드는 글자 그대로 보존**하고(순번 `case-num` 만 다시 매김),
  * 허브에 없는 라이브 사례만 `meta.tsv` 로 **카드를 만들어 뒤에 덧붙이며**,
  * 건수에 따라 달라지는 **파생 블록만** 다시 만든다.
파생 블록은 HTML 주석 마커로 둘러싸여 있다:
  GEN:HEADMETA · GEN:OGMETA · GEN:H1LEAD · GEN:OVERVIEW · GEN:LISTHEAD · GEN:CARDS
여기에 JSON-LD 는 주석을 넣을 수 없으므로 `ItemList` 블록은 내용으로 찾아
통째로 다시 만들고, `CollectionPage` 의 설명 문장은 건수만 치환한다.
마커가 하나라도 없으면 **아무것도 쓰지 않고 2 로 종료**한다(조용한 무동작 방지).

정본 규칙
---------
`<slug>-v2` 처럼 `-v<숫자>` 로 끝나고 접미사 없는 같은 슬러그가 함께 있으면
**비정본 중복으로 보고 허브에서 제외**한다(2026-10-06 소유자 결정:
접미사 없는 주소가 정본). 중복 URL 을 크롤 진입점에 싣지 않기 위함이다.

공개범위
--------
카드 본문은 초안 검증기를 통과한 `meta.tsv` 의 `seo_h2`·`seo_p` 첫 문단과
`sijae`·`method`·`value_text` 만 쓴다. `seo_p` 둘째 문단 이후(결정단가·산출금액·
사정보정 등 산정과정 서술)는 **싣지 않는다**. 기준시점은 `gijun` 에 월·일이
적혀 있어도 **연도만** 표기한다.

사용법
------
    python3 tools/make_cases_index_v1.py             # 동기화(변경 있으면 .bak 후 저장)
    python3 tools/make_cases_index_v1.py --dry-run   # 쓰지 않고 차이만 보고 (exit 0)
    python3 tools/make_cases_index_v1.py --check     # 쓰지 않고, 어긋나 있으면 exit 1

입력
----
  - cases/*.html                         : 라이브 사례 목록(.bak·index.html 제외)
  - cases/index.html                     : 기존 카드·마커
  - automation/published/*.meta.tsv      : 신규 카드 재료(게시 후)
  - automation/queue/*.meta.tsv          : 신규 카드 재료(게시 직전 — 8.5) 호출 시점)
  - automation/state/published_log.tsv   : 신규 카드 덧붙이는 순서
출력
----
  - cases/index.html (변경이 있을 때만 `.bak-YYYYMMDD-HHMMSS` 백업 후 덮어씀)
"""

from __future__ import annotations

import argparse
import glob
import html as H
import io
import os
import re
import shutil
import sys
from datetime import datetime

SITE = "https://gaachi.co.kr"
MARKERS = ("HEADMETA", "OGMETA", "H1LEAD", "OVERVIEW", "LISTHEAD", "CARDS")

# 광역자치단체 표기 → 표에 쓰는 짧은 이름
WIDE = {
    "서울특별시": "서울", "서울": "서울",
    "경기도": "경기", "경기": "경기",
    "인천광역시": "인천", "인천": "인천",
    "부산광역시": "부산", "부산": "부산",
    "대구광역시": "대구", "대구": "대구",
    "광주광역시": "광주", "광주": "광주",
    "대전광역시": "대전", "대전": "대전",
    "울산광역시": "울산", "울산": "울산",
    "세종특별자치시": "세종", "세종": "세종",
    "강원특별자치도": "강원", "강원도": "강원", "강원": "강원",
    "충청북도": "충북", "충북": "충북",
    "충청남도": "충남", "충남": "충남",
    "전북특별자치도": "전북", "전라북도": "전북", "전북": "전북",
    "전라남도": "전남", "전남": "전남",
    "경상북도": "경북", "경북": "경북",
    "경상남도": "경남", "경남": "경남",
    "제주특별자치도": "제주", "제주": "제주",
}

# 평가목적 토큰 → 리드문에 쓰는 이름
PURPOSE_LABEL = {
    "상속": "상속재산 감정평가",
    "증여": "증여재산 감정평가",
    "자산재평가": "자산재평가(재무보고)",
    "경매": "법원경매",
    "임대료": "임대료",
    "담보": "담보",
    "보상": "보상",
}

# 물건종류 추정 — 위에서부터 먼저 걸리는 것을 쓴다
OBJ_RULES = [
    ("입주권", "아파트 입주권"),
    ("지식산업센터", "지식산업센터"),
    ("오피스텔", "오피스텔"),
    ("다가구", "다가구주택"),
    ("다세대", "다세대주택"),
    ("단독주택", "단독주택"),
    ("근린생활시설", "근린생활시설"),
    ("상가", "구분상가"),
    ("숙박시설", "숙박시설"),
    ("공장", "공장"),
    ("창고", "창고"),
    ("집합건물", "집합건물"),
    ("토지·건물", "토지·건물"),
    ("아파트", "아파트"),
    ("토지", "토지"),
    ("건물", "건물"),
]


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_text(path: str) -> str:
    return io.open(path, encoding="utf-8", errors="replace").read()


def esc(s: str) -> str:
    return H.escape(s or "", quote=False)


def att(s: str) -> str:
    return H.escape(s or "", quote=True)


def squeeze(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


# ---------------------------------------------------------------- 입력 수집

def live_slugs(root: str) -> tuple[list[str], list[str]]:
    """cases/*.html 에서 라이브 사례 슬러그를 뽑는다. (정본목록, 제외된중복)"""
    found = []
    for p in sorted(glob.glob(os.path.join(root, "cases", "*.html"))):
        name = os.path.basename(p)
        if name == "index.html" or ".bak" in name:
            continue
        found.append(name[:-5])
    sset = set(found)
    canon, dropped = [], []
    for s in found:
        m = re.match(r"^(?P<base>.+)-v\d+$", s)
        if m and m.group("base") in sset:
            dropped.append(s)
        else:
            canon.append(s)
    return canon, dropped


def parse_meta(path: str) -> dict:
    d = {}
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            d[parts[0].strip()] = "\t".join(parts[1:]).strip()
    return d


def meta_index(root: str) -> dict[str, str]:
    """슬러그 -> meta.tsv 경로. published/ 가 queue/ 보다 우선."""
    out: dict[str, str] = {}
    for sub in ("queue", "published"):
        for p in sorted(glob.glob(os.path.join(root, "automation", sub, "*.meta.tsv"))):
            name = os.path.basename(p)
            m = re.match(r"^(?:\d+_)?(?:\d{8}-\d{6}-)?(?:\d+_)?(.+)\.meta\.tsv$", name)
            if not m:
                continue
            out[m.group(1)] = p
    return out


def publish_order(root: str) -> dict[str, str]:
    """슬러그 -> 최초 게시일(YYYY-MM-DD). 없으면 비어 있음."""
    path = os.path.join(root, "automation", "state", "published_log.tsv")
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    for line in read_text(path).splitlines()[1:]:
        c = line.split("\t")
        if len(c) < 3:
            continue
        date, url = c[0].strip(), c[2].strip()
        m = re.search(r"/cases/([^/?#]+?)(?:\.html)?$", url)
        if m:
            out.setdefault(m.group(1), date)
    return out


# ------------------------------------------------------- 기존 카드 파싱

# 앞쪽 들여쓰기까지 함께 잡아야 보존한 카드를 다시 쓸 때 들여쓰기가 사라지지 않는다
CARD_RE = re.compile(r"[ \t]*<article class=\"case-card\".*?</article>", re.S)


def dd_of(card: str, label: str) -> str:
    m = re.search(
        r"<dt class=\"case-meta-label\">%s</dt><dd class=\"case-meta-val\">(.*?)</dd>"
        % re.escape(label), card, re.S)
    return squeeze(re.sub(r"<[^>]+>", "", m.group(1))) if m else ""


def attr_of(card: str, name: str) -> str:
    m = re.search(r"%s=\"([^\"]*)\"" % re.escape(name), card)
    return m.group(1) if m else ""


def parse_existing(cards_html: str) -> list[dict]:
    out = []
    for card in CARD_RE.findall(cards_html):
        m = re.search(r"href=\"/cases/([^\"#?]+)\"", card)
        slug = m.group(1) if m else ""
        t = re.search(r"<h3 class=\"case-title\"><a [^>]*>(.*?)</a></h3>", card, re.S)
        title = squeeze(re.sub(r"<[^>]+>", "", t.group(1))) if t else slug
        y = re.search(r"<time datetime=\"(\d{4})\"", card)
        sijae = dd_of(card, "소재지")
        toks = sijae.split()
        out.append({
            "slug": slug,
            "html": card,
            "title": H.unescape(title),
            "region": attr_of(card, "data-region"),
            "purposes": attr_of(card, "data-purpose").split(),
            "wide": WIDE.get(toks[0], toks[0]) if toks else "",
            "dong": toks[-1] if toks else "",
            "year": y.group(1) if y else "",
            "method": dd_of(card, "평가방법"),
            "objtype": dd_of(card, "물건종류"),
            "new": False,
        })
    return out


# ------------------------------------------------------- 신규 카드 만들기

def norm_region(meta: dict) -> str:
    """구/시 한 토큰. meta region 이 '서울 금천구 가산동' 처럼 길어도 정규화한다."""
    for raw in (meta.get("region", ""), meta.get("sijae", ""), meta.get("title_line1", "")):
        toks = squeeze(raw).split()
        if not toks:
            continue
        if toks[0] in WIDE and len(toks) > 1:
            toks = toks[1:]
        if len(toks) == 1 and re.search(r"[구시군]$", toks[0]):
            return toks[0]
        for t in toks:
            if re.search(r"[구시군]$", t):
                return t
    return ""


def norm_sijae(meta: dict) -> str:
    toks = squeeze(meta.get("sijae") or meta.get("title_line1") or "").split()
    if toks and toks[0] in WIDE:
        toks[0] = WIDE[toks[0]]
    return " ".join(toks)


def norm_year(meta: dict) -> str:
    m = re.search(r"(\d{4})\s*년", meta.get("gijun", "") or "")
    return m.group(1) if m else ""


def norm_purposes(meta: dict) -> list[str]:
    raw = (meta.get("purpose_short") or meta.get("purpose_branch")
           or meta.get("cat") or "")
    raw = raw.replace("·", " ").replace("/", " ").replace(",", " ")
    toks = [t for t in raw.split() if t]
    fix = []
    for t in toks:
        if t in ("경매공매",):
            t = "경매"
        if t in ("재무보고",):
            t = "자산재평가"
        if t in ("특수관계인",) and (meta.get("purpose_branch") == "임대료"):
            t = "임대료"
        if t not in fix:
            fix.append(t)
    return fix or ["감정평가"]


def norm_objtype(meta: dict) -> str:
    hay = " ".join([meta.get("object", ""), meta.get("title_line2", ""),
                    meta.get("seo_h2", "")])
    for key, label in OBJ_RULES:
        if key in hay:
            return label
    return "부동산"


def split_value(value_text: str) -> tuple[str, str]:
    """'연간 실질임대료 1억 3,700만원' -> ('연간 실질임대료', '1억 3,700만원')"""
    v = squeeze(value_text)
    m = re.match(r"^(?P<label>[^\d]*?)\s*(?P<num>\d[\d,]*\s*(?:억|만원|원).*)$", v)
    if m and m.group("label").strip():
        return m.group("label").strip(), m.group("num").strip()
    return "최종 감정평가액", v


def card_from_meta(slug: str, meta: dict) -> dict:
    title = squeeze(meta.get("seo_h2") or
                    "%s %s" % (meta.get("title_line1", ""), meta.get("title_line2", "")))
    summary = squeeze((meta.get("seo_p", "") or "").split("||")[0])
    region = norm_region(meta)
    sijae = norm_sijae(meta)
    toks = sijae.split()
    vlabel, vnum = split_value(meta.get("value_text", ""))
    return {
        "slug": slug,
        "html": None,
        "title": title,
        "summary": summary,
        "purpose": squeeze(meta.get("purpose", "")),
        "tag": squeeze(meta.get("tag", "")) or "감정평가",
        "region": region,
        "purposes": norm_purposes(meta),
        "wide": WIDE.get(toks[0], toks[0]) if toks else "",
        "dong": toks[-1] if toks else "",
        "sijae": sijae,
        "year": norm_year(meta),
        "method": squeeze(meta.get("method", "")),
        "objtype": norm_objtype(meta),
        "vlabel": vlabel,
        "vnum": vnum,
        "new": True,
    }


def card_from_page(root: str, slug: str) -> dict:
    """meta.tsv 가 없을 때의 최소 폴백 — 링크가 빠지는 일은 없게 한다."""
    src = read_text(os.path.join(root, "cases", slug + ".html"))
    t = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
    # 태그를 공백으로 바꿔야 <br>·<span> 경계에서 낱말이 붙지 않는다
    title = squeeze(re.sub(r"<[^>]+>", " ", t.group(1))) if t else slug
    d = re.search(r"<meta name=\"description\" content=\"(.*?)\"", src, re.S)
    return {
        "slug": slug, "html": None, "title": H.unescape(title),
        "summary": H.unescape(squeeze(d.group(1))) if d else "",
        "purpose": "", "tag": "감정평가", "region": "", "purposes": ["감정평가"],
        "wide": "", "dong": "", "sijae": "", "year": "", "method": "",
        "objtype": "부동산", "vlabel": "최종 감정평가액", "vnum": "",
        "new": True, "fallback": True,
    }


def render_card(c: dict, num: int) -> str:
    L = []
    L.append('  <article class="case-card" data-region="%s" data-purpose="%s">'
             % (att(c["region"]), att(" ".join(c["purposes"]))))
    L.append('    <div class="case-card-head">')
    L.append('      <div class="case-num">%02d</div>' % num)
    L.append('      <div class="case-tag">%s</div>' % esc(c["tag"]))
    L.append('      <h3 class="case-title"><a href="/cases/%s">%s</a></h3>'
             % (att(c["slug"]), esc(c["title"])))
    if c.get("purpose"):
        L.append('      <p class="case-purpose">%s</p>' % esc(c["purpose"]))
    L.append('    </div>')
    L.append('    <div class="case-card-body">')
    if c.get("summary"):
        L.append('      <p class="case-summary">%s</p>' % esc(c["summary"]))
    L.append('      <dl class="case-meta-row">')
    rows = []
    if c.get("sijae"):
        rows.append(("소재지", esc(c["sijae"])))
    if c.get("year"):
        rows.append(("기준시점", '<time datetime="%s">%s년</time>' % (c["year"], c["year"])))
    if c.get("method"):
        rows.append(("평가방법", esc(c["method"])))
    if c.get("objtype"):
        rows.append(("물건종류", esc(c["objtype"])))
    for label, val in rows:
        L.append('        <div class="case-meta"><dt class="case-meta-label">%s</dt>'
                 '<dd class="case-meta-val">%s</dd></div>' % (label, val))
    L.append('      </dl>')
    if c.get("vnum"):
        L.append('      <div class="case-value-row">')
        L.append('        <div><div class="case-value-label">%s</div>'
                 '<div class="case-value-num">%s</div></div>'
                 % (esc(c["vlabel"]), esc(c["vnum"])))
        L.append('      </div>')
    L.append('      <a class="case-link" href="/cases/%s">%s 전문 읽기</a>'
             % (att(c["slug"]), esc(c["title"])))
    L.append('    </div>')
    L.append('  </article>')
    return "\n".join(L)


def renumber(card_html: str, num: int) -> str:
    return re.sub(r'(<div class="case-num">)[^<]*(</div>)',
                  lambda m: "%s%02d%s" % (m.group(1), num, m.group(2)),
                  card_html, count=1)


# ---------------------------------------------------------------- 집계

def counts(cards: list[dict]) -> dict:
    n = len(cards)
    region: dict[str, int] = {}
    region_wide: dict[str, str] = {}
    region_dong: dict[str, list[str]] = {}
    purpose: dict[str, int] = {}
    year: dict[str, int] = {}
    obj: dict[str, int] = {}
    obj_method: dict[str, list[str]] = {}
    for c in cards:
        r = c.get("region") or "미분류"
        region[r] = region.get(r, 0) + 1
        region_wide.setdefault(r, c.get("wide") or "")
        d = c.get("dong") or ""
        if d and d not in region_dong.setdefault(r, []):
            region_dong[r].append(d)
        for p in c.get("purposes") or []:
            purpose[p] = purpose.get(p, 0) + 1
        if c.get("year"):
            year[c["year"]] = year.get(c["year"], 0) + 1
        o = c.get("objtype") or "부동산"
        obj[o] = obj.get(o, 0) + 1
        mth = c.get("method") or ""
        if mth and mth not in obj_method.setdefault(o, []):
            obj_method[o].append(mth)
    return {"n": n, "region": region, "region_wide": region_wide,
            "region_dong": region_dong, "purpose": purpose, "year": year,
            "obj": obj, "obj_method": obj_method}


def by_count(d: dict[str, int]) -> list[tuple[str, int]]:
    return sorted(d.items(), key=lambda kv: (-kv[1], kv[0]))


def region_phrase(g: dict) -> str:
    """'서울 11개 자치구 · 경기 남양주시 · 충남 천안시'"""
    groups: dict[str, list[str]] = {}
    for r, _ in by_count(g["region"]):
        groups.setdefault(g["region_wide"].get(r, ""), []).append(r)
    parts = []
    for wide, regs in sorted(groups.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if wide == "서울" and len(regs) > 1:
            parts.append("서울 %d개 자치구" % len(regs))
        else:
            parts.append(" · ".join(("%s %s" % (wide, r)).strip() for r in sorted(regs)))
    return " · ".join(p for p in parts if p)


def purpose_phrase(g: dict) -> str:
    items = ["%s %d건" % (PURPOSE_LABEL.get(p, "%s 감정평가" % p), c)
             for p, c in by_count(g["purpose"])]
    return ", ".join(items)


def purpose_note(g: dict) -> str:
    """목적이 둘인 사례(예: 상속·증여 병행) 때문에 목적별 합계가 전체와 다를 때의 각주."""
    if sum(g["purpose"].values()) == g["n"]:
        return ""
    return " 평가목적이 둘인 사례가 있어 목적별 건수의 합은 전체 건수와 다릅니다."


def purpose_words(g: dict) -> str:
    return "·".join(p for p, _ in by_count(g["purpose"]))


def year_phrase(g: dict) -> str:
    return "·".join("%s년 %d건" % (y, c) for y, c in sorted(g["year"].items()))


# ---------------------------------------------------------------- 블록 생성

def blk_headmeta(g: dict) -> str:
    n = g["n"]
    return "\n".join([
        "<title>감정평가 사례 모음 — 지역별·평가목적별 %d건 | 가치앤같이 감정평가법인</title>" % n,
        '<meta name="description" content="%s">' % att(
            "㈜감정평가법인 가치앤같이가 수행한 감정평가 사례 %d건의 목록입니다. "
            "%s 등 지역별, %s 등 평가목적별로 기준시점(연도)·적용 감정평가방법·"
            "최종 감정평가액을 확인할 수 있습니다." % (n, region_phrase(g), purpose_words(g))),
    ])


def blk_ogmeta(g: dict) -> str:
    n = g["n"]
    return "\n".join([
        '<meta property="og:title" content="%s">' % att(
            "감정평가 사례 모음 — 지역별·평가목적별 %d건 | 가치앤같이" % n),
        '<meta property="og:description" content="%s">' % att(
            "㈜감정평가법인 가치앤같이가 수행한 감정평가 사례 %d건. "
            "지역·평가목적·기준시점(연도)·감정평가방법·최종 감정평가액을 "
            "한 페이지에서 비교할 수 있습니다." % n),
    ])


def blk_h1lead(g: dict) -> str:
    n = g["n"]
    return "\n".join([
        "    <h1>감정평가 사례 모음 — 지역별·평가목적별 감정평가 사례 %d건</h1>" % n,
        '    <p class="lead-answer">㈜감정평가법인 가치앤같이(서울특별시 서초구 강남대로 86, 5층 501호)가 '
        "실제로 수행한 <strong>감정평가 사례 %d건</strong>을 한 곳에 모은 목록입니다. "
        "%s이며, 기준시점은 %s입니다. 각 사례에서 소재지(구·동)·기준시점(연도)·"
        "적용한 감정평가방법·최종 감정평가액을 확인할 수 있고, 사례 제목을 누르면 "
        "비교사례와 산정과정까지 담긴 개별 사례 페이지로 이동합니다.%s</p>"
        % (n, purpose_phrase(g), year_phrase(g), purpose_note(g)),
    ])


def blk_overview(g: dict) -> str:
    n = g["n"]
    L = []
    L.append('    <p class="section-summary">㈜감정평가법인 가치앤같이의 감정평가 사례 %d건은 '
             "%s에 걸쳐 있습니다. 아래 두 표는 그 %d건이 지역과 물건종류에 따라 "
             "어떻게 나뉘는지 보여 줍니다.</p>" % (n, region_phrase(g), n))
    L.append("")
    L.append("    <table>")
    L.append("      <caption>표 1. 지역별 감정평가 사례 분포 (총 %d건, "
             "소재지는 구·동 단위까지만 표기)</caption>" % n)
    L.append('      <thead><tr><th scope="col">지역</th><th scope="col">사례 수</th>'
             '<th scope="col">수록된 동</th></tr></thead>')
    L.append("      <tbody>")
    for r, c in by_count(g["region"]):
        name = ("%s %s" % (g["region_wide"].get(r, ""), r)).strip()
        dongs = " · ".join(sorted(g["region_dong"].get(r, []))) or "—"
        L.append('        <tr><th scope="row">%s</th><td>%d건</td><td>%s</td></tr>'
                 % (esc(name), c, esc(dongs)))
    L.append("      </tbody>")
    L.append("    </table>")
    L.append("")
    L.append("    <table>")
    L.append("      <caption>표 2. 물건종류별 감정평가 사례 분포와 적용한 감정평가방법</caption>")
    L.append('      <thead><tr><th scope="col">물건종류</th><th scope="col">사례 수</th>'
             '<th scope="col">적용한 감정평가방법</th></tr></thead>')
    L.append("      <tbody>")
    for o, c in by_count(g["obj"]):
        mth = " / ".join(g["obj_method"].get(o, [])) or "—"
        L.append('        <tr><th scope="row">%s</th><td>%d건</td><td>%s</td></tr>'
                 % (esc(o), c, esc(mth)))
    L.append("      </tbody>")
    L.append("    </table>")
    return "\n".join(L)


def btn_label(purpose: str) -> str:
    """필터 버튼 라벨. '자산재평가 감정평가' 같은 겹말을 만들지 않는다."""
    return purpose if purpose.endswith("평가") else "%s 감정평가" % purpose


def blk_listhead(g: dict) -> str:
    n = g["n"]
    L = []
    L.append("    <h2>감정평가 사례 전체 목록 (%d건)</h2>" % n)
    L.append('    <p class="section-summary">㈜감정평가법인 가치앤같이의 감정평가 사례 %d건 '
             "전체입니다. 아래 버튼으로 지역이나 평가목적을 골라 좁혀 볼 수 있으며, "
             "버튼을 쓰지 않아도 %d건이 모두 이 자리에 그대로 표시됩니다.</p>" % (n, n))
    L.append("")
    L.append('    <div class="cat-filter">')
    L.append('      <span class="cat-filter-label">지역</span>')
    L.append('      <button type="button" class="cat-btn active" data-filter="region" '
             'data-value="전체">전체 <span class="cnt">%d</span></button>' % n)
    for r, c in by_count(g["region"]):
        L.append('      <button type="button" class="cat-btn" data-filter="region" '
                 'data-value="%s">%s <span class="cnt">%d</span></button>'
                 % (att(r), esc(r), c))
    L.append("    </div>")
    L.append('    <div class="cat-filter">')
    L.append('      <span class="cat-filter-label">평가목적</span>')
    L.append('      <button type="button" class="cat-btn active" data-filter="purpose" '
             'data-value="전체">전체 <span class="cnt">%d</span></button>' % n)
    for p, c in by_count(g["purpose"]):
        L.append('      <button type="button" class="cat-btn" data-filter="purpose" '
                 'data-value="%s">%s <span class="cnt">%d</span></button>'
                 % (att(p), esc(btn_label(p)), c))
    L.append("    </div>")
    L.append('    <p class="filter-note">지역·평가목적 버튼은 보기 편하도록 목록을 좁히는 '
             "보조 기능입니다. 버튼을 쓰지 않거나 스크립트가 동작하지 않는 환경에서도 "
             "사례 %d건과 각 사례 링크는 이 페이지에 모두 들어 있습니다.</p>" % n)
    L.append('    <p class="filter-status" id="filterStatus" role="status">'
             "사례 %d건을 모두 보고 있습니다.</p>" % n)
    return "\n".join(L)


def blk_itemlist(cards: list[dict], g: dict) -> str:
    L = ['<script type="application/ld+json">', "{",
         '  "@context": "https://schema.org",',
         '  "@type": "ItemList",',
         '  "@id": "%s/cases/#caselist",' % SITE,
         '  "name": "㈜감정평가법인 가치앤같이 감정평가 사례 목록",',
         '  "description": "지역별·평가목적별 감정평가 사례 %d건.",' % g["n"],
         '  "numberOfItems": %d,' % g["n"],
         '  "itemListOrder": "https://schema.org/ItemListOrderAscending",',
         '  "itemListElement": [']
    for i, c in enumerate(cards, 1):
        L.append("    {")
        L.append('      "@type": "ListItem",')
        L.append('      "position": %d,' % i)
        L.append('      "url": "%s/cases/%s",' % (SITE, c["slug"]))
        L.append('      "name": "%s"' % c["title"].replace('"', '\\"'))
        L.append("    }" + ("," if i < len(cards) else ""))
    L += ["  ]", "}", "</script>"]
    return "\n".join(L)


# ---------------------------------------------------------------- 치환

def replace_marker(src: str, name: str, body: str) -> str:
    s = "<!-- GEN:%s:START -->" % name
    e = "<!-- GEN:%s:END -->" % name
    i, j = src.index(s), src.index(e)
    return src[:i + len(s)] + "\n" + body + "\n" + src[j:]


ITEMLIST_RE = re.compile(
    r'<script type="application/ld\+json">\s*\{[^<]*?"@type":\s*"ItemList".*?</script>',
    re.S)


def main() -> int:
    ap = argparse.ArgumentParser(description="gaachi.co.kr 사례 허브 동기화")
    ap.add_argument("--check", action="store_true",
                    help="쓰지 않고 검사만. 어긋나 있으면 exit 1")
    ap.add_argument("--dry-run", action="store_true",
                    help="쓰지 않고 차이만 보고. exit 0")
    args = ap.parse_args()

    root = repo_root()
    hub = os.path.join(root, "cases", "index.html")
    if not os.path.exists(hub):
        print("[error] cases/index.html 이 없습니다.", file=sys.stderr)
        return 1
    src = read_text(hub)

    missing_marker = [m for m in MARKERS if ("<!-- GEN:%s:START -->" % m) not in src
                      or ("<!-- GEN:%s:END -->" % m) not in src]
    if missing_marker:
        print("[error] cases/index.html 에 생성기 마커가 없습니다: %s\n"
              "        (허브를 손으로 고쳤다면 마커를 복원한 뒤 다시 실행하십시오)"
              % ", ".join(missing_marker), file=sys.stderr)
        return 2
    if not ITEMLIST_RE.search(src):
        print("[error] ItemList JSON-LD 블록을 찾지 못했습니다.", file=sys.stderr)
        return 2

    canon, dropped = live_slugs(root)
    for s in dropped:
        print("  [skip] 비정본 중복 슬러그 제외: %s" % s)

    i = src.index("<!-- GEN:CARDS:START -->") + len("<!-- GEN:CARDS:START -->")
    j = src.index("<!-- GEN:CARDS:END -->")
    existing = parse_existing(src[i:j])
    print("기존 허브 카드 %d건 / 라이브 사례 %d건" % (len(existing), len(canon)))

    kept, stale = [], []
    for c in existing:
        (kept if c["slug"] in canon else stale).append(c)
    for c in stale:
        print("  [warn] 라이브에 없는 카드 제거: %s" % c["slug"])

    have = {c["slug"] for c in kept}
    order = publish_order(root)
    metas = meta_index(root)
    todo = [s for s in canon if s not in have]
    todo.sort(key=lambda s: (order.get(s, "9999-99-99"), s))

    added = []
    for s in todo:
        if s in metas:
            c = card_from_meta(s, parse_meta(metas[s]))
            print("  [add] %s  (meta: %s)" % (s, os.path.basename(metas[s])))
        else:
            c = card_from_page(root, s)
            print("  [add] %s  (meta.tsv 없음 — 사례 페이지에서 최소 카드 구성)" % s)
        added.append(c)

    cards = kept + added
    if not cards:
        print("[error] 카드가 0건입니다. 중단합니다.", file=sys.stderr)
        return 1

    g = counts(cards)
    body = "\n".join(
        (renumber(c["html"], n) if c.get("html") else render_card(c, n))
        for n, c in enumerate(cards, 1))

    out = src
    out = replace_marker(out, "CARDS", body)
    out = replace_marker(out, "HEADMETA", blk_headmeta(g))
    out = replace_marker(out, "OGMETA", blk_ogmeta(g))
    out = replace_marker(out, "H1LEAD", blk_h1lead(g))
    out = replace_marker(out, "OVERVIEW", blk_overview(g))
    out = replace_marker(out, "LISTHEAD", blk_listhead(g))
    out = ITEMLIST_RE.sub(lambda m: blk_itemlist(cards, g), out, count=1)
    # CollectionPage 의 설명 문장(JSON 안이라 마커를 둘 수 없다) — 건수만 맞춘다
    out = re.sub(r"감정평가 사례 \d+건의 목록입니다",
                 "감정평가 사례 %d건의 목록입니다" % g["n"], out)

    print("\n허브 사례 %d건 / 지역 %d / 평가목적 %d / 물건종류 %d"
          % (g["n"], len(g["region"]), len(g["purpose"]), len(g["obj"])))
    print("  지역: %s" % ", ".join("%s %d" % (k, v) for k, v in by_count(g["region"])))
    print("  목적: %s" % ", ".join("%s %d" % (k, v) for k, v in by_count(g["purpose"])))

    if out == src:
        print("변경 없음 — cases/index.html 은 이미 동기 상태입니다.")
        return 0

    if args.check:
        print("[check] cases/index.html 이 라이브 사례와 어긋나 있습니다. "
              "`python3 tools/make_cases_index_v1.py` 로 동기화하십시오.")
        return 1
    if args.dry_run:
        print("--dry-run: 쓰지 않았습니다. (카드 추가 %d · 제거 %d)"
              % (len(added), len(stale)))
        return 0

    bak = hub + datetime.now().strftime(".bak-%Y%m%d-%H%M%S")
    shutil.copy2(hub, bak)
    print("기존 허브 백업 -> cases/%s" % os.path.basename(bak))
    io.open(hub, "w", encoding="utf-8", newline="\n").write(out)
    print("생성 완료: %s (%d bytes, 카드 추가 %d · 제거 %d)"
          % (hub, os.path.getsize(hub), len(added), len(stale)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
