#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 감정평가법인 — 초안(draft) 검증기 v2
================================================
v1(`validate_draft_v1.py`)을 복사·확장한 것으로, **v1 이 막던 것은 전부 그대로 막는다.**
여기에 목적 확장(상속·증여 외 4개 분기)에 필요한 게이트를 더했다.

근거
  automation/_spec/목적확장_규칙확정_20260928.md  (소유자 결정서 — 최상위 근거)
  automation/생성지침_v5.md                        (작업지시서)

v1 게이트 (그대로 유지)
  - publish_case_v1.py 의 validate() 재사용 (import 실패 시 내장 fallback)
  - 미치환 토큰 {{ }} 0건
  - <h1> 정확히 1개 / <h2> 3개 이상 / <h3> 1개 이상
  - JSON-LD 3블록 전부 파싱 + FAQPage 질문 == 본문 <h3> FAQ 질문 (글자 단위)
  - canonical == og:url == JSON-LD mainEntityOfPage.@id == /cases/<slug> (확장자 없음)
  - 숨김 키워드 스팬 0건 / 수수료 금액 표현 0건 / 인명 패턴 0건 / <\!-- 오타 0건
  - meta.tsv 사이드카 존재 + 12개 키 전부 존재

v2 에서 새로 막는 것
  1. 목적별 법령 오염
     - 상속증여가 아닌 분기: 「상속세 및 증여세법」·제49조·평가기간·상속개시일·증여일  -> 오류
     - 재무보고: '시장가치' -> 오류 (기준가치는 공정가치)
     - 전 목적: K-IFRS·제1016호·재평가모형·장부금액 -> 오류 (감정서에 없는 용어)
  2. 임대료 건의 총괄수치 게재 (결정 1 — 2026-09-28 소유자 지시로 개정)
     ★ 제정판(오전)의 「기대이율/필요제경비/기초가액/보증금 뒤에 수치가 붙으면 오류」 검사는 **삭제**했다.
       기초가액 총액·기대이율(단일 %)·필요제경비 총액은 게재 허용. 다만 **보증금·보증금환원율(전환이율)은 미게재**(2026-09-28 소유자 지시).
     대신 **종별 내역**을 잡는다(임대료 분기에서만, 오탐을 피해 **경고**):
       - 필요제경비 근처에 요율이 2개 이상 나열     -> 경고
       - 토지/건물/기계기구가 각각 기초가액 금액을 달고 2종 이상 -> 경고
       - 임차인별 배분/안분 표기                    -> 경고
  3. MASK_LEVEL=range 건 (결정 3)
     정확 금액·결정단가·산출금액·필지수·동수·소수점 면적·about.price·VALUE_NUMERIC -> 오류
  4. 법인 마스킹 (결정 4)
     지번·단지명·건물명·회사명 -> 오류 / 유동화 차수·신탁회사명 패턴 -> 오류 또는 경고
  5. 기준시점 월·일 — 임대료 목적만 허용, 그 외 분기는 오류 (결정 2)
  6. 생성지침 4-Z 스윕에만 있던 항목의 승격
     h2 9개 / <caption> 2개 / 본문 법령 링크 2개 이상 / id="summary" 1개 /
     금지 스키마 0 / .html URL 0 / .date-note·.calc-note·푸터 안내문(law-note)·case-cta-desc 존재 /
     층·호 마스킹 기호(집합건물) / 실제 층·호 0 / 비교사례 동 번호 0 /
     사정보정·시점수정·가격지수 0 / 가시 본문 5,100자 이하 / 날짜형 datetime 3종 이하

목적 분기 판정
  초안 옆 `.meta.tsv` 를 읽는다.  purpose_branch > cat > 본문 추정 순.
  cat 이 없거나 알 수 없으면 **경고만 내고 나머지 검사는 그대로 수행**한다.
  .meta.tsv 신설 키(생성지침 v5 Step 7-C):
      purpose_branch  상속증여 | 재무보고 | 임대료 | 경매공매 | 구조화금융 | 기타
      mask_level      exact(기본) | range
      owner_type      개인(기본) | 법인 | 부동산신탁회사 | 유동화전문회사 | 법원

구 게시본 예외
  automation/review/ · automation/queue/ 안의 초안은 위 6번을 **오류**로 막는다.
  그 밖의 위치(automation/published/ · cases/)에 있는 **이미 게시된 구 템플릿 사례**는
  6번을 **경고**로 완화한다(v4 이전 템플릿은 h2 8개·caption 0개로 만들어졌다).
  마스킹·규칙 B·금지 스키마는 위치와 무관하게 언제나 오류다.

사용법
  python validate_draft_v2.py                       # review/ + queue/ 전체
  python validate_draft_v2.py automation/review/011_....html
  python validate_draft_v2.py --dir automation/published
  python validate_draft_v2.py templates/케이스_v2_예시.html --slug ... --no-meta

종료 코드
  0 = 오류 0건(경고는 있을 수 있음)
  1 = 오류 1건 이상
  2 = 실행 자체가 실패
"""
import argparse
import io
import json
import os
import re
import sys
import unicodedata
from html import unescape

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SITE = "https://gaachi.co.kr"

# publisher 가 build_card() 에서 실제로 읽는 12개 키
META_REQUIRED = ("num", "cat", "tag", "title_line1", "title_line2", "purpose",
                 "sijae", "gijun", "method", "value_text", "seo_h2", "seo_p")

CONFIG_DIR = os.path.join(HERE, "config")
BLOCKLIST_FILE = os.path.join(CONFIG_DIR, "blocklist_names_v1.txt")
FORBIDDEN_FILE = os.path.join(CONFIG_DIR, "forbidden_phrases_v1.txt")

# '○○님/○○씨' 오탐 제외 목록 (호칭 일반명사)
NIM_ALLOW = {"고객님", "회원님", "선생님", "사장님", "어머님", "아버님",
             "여러분", "담당자님", "대표님"}

# 수수료 금액 표현 (forbidden_phrases 로 못 거르는 변형)
FEE_PATTERNS = [
    r"수수료",
    r"보수료",
    r"평가\s*비용",
    r"비용은\s*약",
    r"(수수료|보수|비용)[^\n]{0,20}?[0-9][0-9,]*\s*(만원|원|천원)",
    r"[0-9][0-9,]*\s*(만원|원)[^\n]{0,10}?(수수료|보수료)",
]


# ---------------------------------------------------------------- 공통 유틸
def read_text(path):
    with io.open(path, "r", encoding="utf-8", errors="strict") as f:
        return f.read()


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def norm_ws(s):
    return re.sub(r"\s+", " ", nfc(unescape(s or ""))).strip()


def read_lines_cfg(path):
    if not os.path.exists(path):
        return []
    out = []
    for ln in read_text(path).splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append(ln)
    return out


# ---------------------------------------------------------------- publisher 재사용
def load_publisher():
    """publish_case_v1.py 를 모듈로 로드한다. 실패하면 None."""
    path = os.path.join(HERE, "publish_case_v1.py")
    if not os.path.exists(path):
        return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("publish_case_v1", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if not hasattr(mod, "validate"):
            return None
        return mod
    except Exception:
        return None


PUB = load_publisher()


def _fallback_validate(html, base_slug):
    """publish_case_v1.py 를 못 읽었을 때만 쓰는 최소 복제본."""
    errs, warns = [], []
    if "<!doctype html>" not in html.lower():
        errs.append("<!DOCTYPE html> 선언이 없습니다.")
    # v6 템플릿은 <html lang="ko" data-purpose="…" data-mask-level="…"> 형태라 속성을 허용한다.
    if not re.search(r'<html\b[^>]*\blang="ko"', html):
        errs.append('<html lang="ko"> 태그가 없습니다.')
    h1 = len(re.findall(r"<h1[\s>]", html))
    if h1 != 1:
        errs.append("<h1> 개수가 %d개입니다(정확히 1개여야 함)." % h1)
    h2 = len(re.findall(r"<h2[\s>]", html))
    if h2 < 3:
        errs.append("<h2> 개수가 %d개입니다(3개 이상 필요)." % h2)
    m = re.search(r"(의뢰인|소유자|신청인)\s*[:：]\s*[가-힣]{2,4}", html)
    if m:
        errs.append("개인정보 의심 패턴 발견: '%s'" % m.group(0))
    for name in read_lines_cfg(BLOCKLIST_FILE):
        if name in html:
            errs.append("차단 인명 발견: '%s'" % name)
    for ph in read_lines_cfg(FORBIDDEN_FILE):
        if ph in html:
            errs.append("금지 문구 발견: '%s'" % ph)
    if "<\\!--" in html:
        errs.append("HTML 주석 오타 '<\\!--' 가 있습니다.")
    warns.append("publish_case_v1.py 를 불러오지 못해 내장 fallback 규칙으로 검사했습니다.")
    return errs, warns


def base_validate(html, base_slug):
    if PUB is not None:
        return PUB.validate(html, base_slug)
    return _fallback_validate(html, base_slug)


# ---------------------------------------------------------------- 추출기
def jsonld_blocks(html):
    return re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I)


def iter_nodes(data):
    """JSON-LD 객체를 @graph 까지 펼쳐서 dict 를 순회한다."""
    stack = [data]
    while stack:
        cur = stack.pop()
        if isinstance(cur, list):
            stack.extend(cur)
        elif isinstance(cur, dict):
            yield cur
            if isinstance(cur.get("@graph"), list):
                stack.extend(cur["@graph"])


def faq_questions_from_jsonld(html):
    """FAQPage mainEntity 의 Question.name 목록."""
    out = []
    for b in jsonld_blocks(html):
        try:
            data = json.loads(b.strip())
        except Exception:
            continue
        for node in iter_nodes(data):
            if str(node.get("@type")) == "FAQPage":
                me = node.get("mainEntity")
                if isinstance(me, dict):
                    me = [me]
                for q in (me or []):
                    if isinstance(q, dict) and q.get("name"):
                        out.append(norm_ws(str(q["name"])))
    return out


def faq_questions_from_html(html):
    """본문에 보이는 FAQ <h3> 질문 텍스트 목록 (배지 Q · 화살표 ▾ 제거)."""
    inners = re.findall(r'<h3[^>]*class=["\'][^"\']*faq-q-heading[^"\']*["\'][^>]*>(.*?)</h3>',
                        html, re.S | re.I)
    if not inners:
        inners = [m for m in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S | re.I)
                  if "faq-q" in m]
    out = []
    for inner in inners:
        s = re.sub(r'<span[^>]*class=["\'][^"\']*(q-badge|faq-arrow)[^"\']*["\'][^>]*>.*?</span>',
                   "", inner, flags=re.S | re.I)
        s = re.sub(r"<[^>]+>", "", s)
        s = norm_ws(s)
        # 배지/화살표 span 이 없는 변형 대비
        s = re.sub(r"^Q\s*", "", s)
        s = re.sub(r"\s*[▾▴▼▲]\s*$", "", s).strip()
        out.append(s)
    return out


def attr_href(html, pattern):
    m = re.search(pattern, html, re.I)
    if not m:
        return None
    hm = re.search(r'(?:href|content)=["\']([^"\']+)["\']', m.group(0))
    return hm.group(1).strip() if hm else None


def mainentity_id(html):
    for b in jsonld_blocks(html):
        try:
            data = json.loads(b.strip())
        except Exception:
            continue
        for node in iter_nodes(data):
            meop = node.get("mainEntityOfPage")
            if isinstance(meop, dict) and meop.get("@id"):
                return str(meop["@id"]).strip()
            if isinstance(meop, str) and meop.strip():
                return meop.strip()
    return None


def find_meta_path(html_path):
    stem = os.path.splitext(html_path)[0]
    for cand in (stem + ".meta.tsv", html_path + ".meta.tsv"):
        if os.path.exists(cand):
            return cand
    return stem + ".meta.tsv"


def read_meta(path):
    meta = {}
    if not os.path.exists(path):
        return meta
    for ln in read_text(path).splitlines():
        if not ln.strip() or ln.lstrip().startswith("#"):
            continue
        if "\t" in ln:
            k, v = ln.split("\t", 1)
        elif "=" in ln:
            k, v = ln.split("=", 1)
        else:
            continue
        meta[k.strip()] = v.strip()
    return meta


def slug_from_filename(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    return stem.split("_", 1)[1] if re.match(r"^\d+_", stem) else stem


# ---------------------------------------------------------------- 초안 전용 게이트
def draft_checks(html, html_path, base_slug, check_meta=True):
    errs, warns = [], []

    # 1) 미치환 토큰
    toks = re.findall(r"\{\{[^}\n]{0,80}\}\}", html)
    if toks:
        errs.append("미치환 토큰 %d건: %s" % (len(toks), ", ".join(sorted(set(toks))[:10])))
    stray = len(re.findall(r"\{\{", html)) + len(re.findall(r"\}\}", html))
    if stray and not toks:
        errs.append("짝이 맞지 않는 '{{' / '}}' 가 %d건 남아 있습니다." % stray)

    # 2) 제목 계층
    h1 = len(re.findall(r"<h1[\s>]", html))
    h2 = len(re.findall(r"<h2[\s>]", html))
    h3 = len(re.findall(r"<h3[\s>]", html))
    if h3 < 1:
        errs.append("<h3> 개수가 %d개입니다(1개 이상 필요)." % h3)

    # 3) JSON-LD 3블록
    blocks = jsonld_blocks(html)
    if len(blocks) < 3:
        errs.append("JSON-LD 블록이 %d개입니다(Article·FAQPage·BreadcrumbList 3개 필요)." % len(blocks))
    for i, b in enumerate(blocks, 1):
        try:
            json.loads(b.strip())
        except Exception as e:
            errs.append("JSON-LD 블록 %d 파싱 실패: %s" % (i, e))

    # 4) FAQ 질문 동기화
    jq = faq_questions_from_jsonld(html)
    hq = faq_questions_from_html(html)
    if not jq:
        errs.append("FAQPage JSON-LD 에서 Question.name 을 하나도 찾지 못했습니다.")
    elif not hq:
        errs.append("본문에서 FAQ <h3> 질문을 하나도 찾지 못했습니다.")
    elif len(jq) != len(hq):
        errs.append("FAQ 질문 개수 불일치: JSON-LD %d개 vs 본문 <h3> %d개" % (len(jq), len(hq)))
        for i in range(min(len(jq), len(hq))):
            if jq[i] != hq[i]:
                errs.append("  Q%d JSON-LD : %s" % (i + 1, jq[i]))
                errs.append("  Q%d 본문h3  : %s" % (i + 1, hq[i]))
    else:
        for i, (a, b) in enumerate(zip(jq, hq), 1):
            if a != b:
                errs.append("FAQ Q%d 질문이 글자 단위로 다릅니다." % i)
                errs.append("  JSON-LD : %s" % a)
                errs.append("  본문 h3 : %s" % b)

    # 5) canonical == og:url == mainEntityOfPage.@id
    canon = attr_href(html, r'<link[^>]+rel=["\']canonical["\'][^>]*>')
    ogurl = attr_href(html, r'<meta[^>]+property=["\']og:url["\'][^>]*>')
    meid = mainentity_id(html)
    want = "%s/cases/%s" % (SITE, base_slug)
    trio = {"canonical": canon, "og:url": ogurl, "mainEntityOfPage.@id": meid}
    for k, v in trio.items():
        if not v:
            errs.append("%s 값을 찾지 못했습니다." % k)
    vals = set(v.rstrip("/") for v in trio.values() if v)
    if len(vals) > 1:
        errs.append("canonical / og:url / mainEntityOfPage.@id 가 서로 다릅니다: %s"
                    % "  |  ".join("%s=%s" % (k, v) for k, v in trio.items()))
    if canon and canon.rstrip("/") != want:
        errs.append("canonical URL 이 파일명 슬러그와 다릅니다: %s (기대값 %s)" % (canon, want))

    # 6) 숨김 키워드 스팬
    hid = len(re.findall(r"font-size\s*:\s*1px", html, re.I))
    hid += len(re.findall(r"color\s*:\s*var\(\s*--bg\s*\)", html, re.I))
    if hid:
        errs.append("숨김 키워드 스팬(font-size:1px / color:var(--bg)) %d건이 남아 있습니다." % hid)

    # 7) 수수료 금액 표현
    for pat in FEE_PATTERNS:
        m = re.search(pat, html)
        if m:
            errs.append("수수료·비용 금액 표현 발견: '%s'" % norm_ws(m.group(0))[:60])
            break

    # 8) 인명 패턴 (최종 스윕)
    for m in re.finditer(r"(?<![가-힣])([가-힣]{2,4})(님|씨)(?![가-힣])", html):
        word = m.group(0)
        if word in NIM_ALLOW:
            continue
        errs.append("인명 의심 패턴 발견: '%s' — 실명이면 삭제하십시오." % word)
        break
    for kw in ("의뢰인", "소유자", "신청인"):
        if kw in html:
            warns.append("'%s' 단어가 본문에 있습니다. 성명이 함께 노출되지 않는지 확인하십시오." % kw)

    # 9) 주석 오타
    if "<\\!--" in html:
        errs.append("HTML 주석 오타 '<\\!--' 가 있습니다.")

    # 10) meta.tsv 사이드카
    if check_meta:
        mpath = find_meta_path(html_path)
        if not os.path.exists(mpath):
            errs.append("meta.tsv 사이드카가 없습니다: %s" % os.path.basename(mpath))
        else:
            meta = read_meta(mpath)
            missing = [k for k in META_REQUIRED if not meta.get(k)]
            if missing:
                errs.append("meta.tsv 에 빠진 키 %d개: %s"
                            % (len(missing), ", ".join(missing)))

    # 11) 참고 경고
    if not re.search(r'rel=["\']alternate["\'][^>]*application/rss\+xml', html, re.I):
        warns.append('<link rel="alternate" type="application/rss+xml" ...> 가 없습니다.')
    for m in re.finditer(r'href=["\']/cases/([a-z0-9\-]+)(?:\.html)?["\']', html):
        p = os.path.join(REPO, "cases", m.group(1) + ".html")
        if not os.path.exists(p):
            warns.append("관련 사례 링크 대상 파일이 없습니다: /cases/%s" % m.group(1))
    firm = html.count("㈜감정평가법인 가치앤같이")
    if firm < 6:
        warns.append("법인 정식명칭 '㈜감정평가법인 가치앤같이' 가 %d회입니다(6회 이상 권장)." % firm)
    for bad in ("본 법인", "당사", "저희 법인"):
        if bad in html:
            warns.append("모호한 자칭 '%s' 사용 — 법인 정식명칭으로 바꾸십시오." % bad)

    return errs, warns, dict(h1=h1, h2=h2, h3=h3, jsonld=len(blocks),
                             faq=len(hq), canonical=canon)


# ================================================================ v2 신설 — 목적 확장
# 근거: automation/_spec/목적확장_규칙확정_20260928.md (소유자 결정서)
#       automation/생성지침_v5.md

BRANCHES = ("상속증여", "재무보고", "임대료", "경매공매", "구조화금융", "기타")

# .meta.tsv 의 cat -> 목적 분기. None 이면 본문에서 자동 판정한다.
CAT2BRANCH = {
    "상속·증여": "상속증여",
    "재무보고": "재무보고",
    "부동산컨설팅": None,          # 임대료 / 매수검토(기타) 혼재
    "소송·경매": "경매공매",
    "구조화금융": "구조화금융",
    "특수관계인": "기타",
    "재개발·분담금": "기타",
    "무형자산": "기타",
}

# 상증세법 계열 용어를 쓰면 안 되는 분기 (결정서 「목적별 근거 법령」)
LAW_STRICT_BRANCHES = ("재무보고", "임대료", "경매공매", "구조화금융")

SANGJEUNG_TERMS = [
    ("「상속세 및 증여세법」", r"상속세\s*및\s*증여세법"),
    ("제49조", r"제\s*49\s*조"),
    ("평가기간", r"평가기간"),
    ("상속개시일", r"상속개시일"),
    ("증여일", r"증여일"),
]

# 감정서 어디에도 인쇄되지 않은 용어 — 전 목적 금지 (결정서 재무보고 항)
KIFRS_ERR = r"K\s*-?\s*IFRS|제\s*1016\s*호|재평가모형|장부금액"
KIFRS_WARN = r"한국채택국제회계기준"

# 임대료 총괄수치 게재 (결정 1 — 2026-09-28 개정)
#   제정 당시의 RENT_NUM_PATTERNS(기대이율·필요제경비·기초가액·보증금 뒤에 수치가 붙으면 오류)는
#   소유자 지시("기대이율 및 필요제경비 수치는 넣어줘.(총괄수치로)")로 **폐기**되었다.
#   이제 총괄수치는 허용이고, 막아야 할 것은 **종별 내역**이다.
#     ❌ 종별 기초가액 내역(토지 39억 / 건물 517억 / 기계기구 118억)
#     ❌ 종별 필요제경비 요율(0.50% · 2.50% · 9.00%)
#     ❌ 임차인별 배분표
#   오탐(상속·재무보고 건의 정상적인 토지/건물 내역)을 피하려고 **임대료 분기에서만** 돌리고 경고로 낸다.
RENT_KIND_WORDS = ("토지", "건물", "기계기구", "기계·기구", "기계기구류")
RENT_BREAKDOWN_WARNS = [
    ("종별 필요제경비 요율 나열",
     r"필요(?:제)?경비[^\n<]{0,120}?\d+(?:\.\d+)?\s*(?:%|％)[^\n<]{0,80}?\d+(?:\.\d+)?\s*(?:%|％)"),
    ("임차인별 배분",
     r"임차인[^\n<]{0,40}?(?:배분|안분|분담|별\s*임대료)"),
]
# 종별 기초가액 내역: '토지 …원' · '건물 …원' · '기계기구 …원' 중 2종 이상이 금액을 달고 나오는 경우
RENT_KIND_AMOUNT_RE = r"(토지|건물|기계기구|기계·기구)[^\n<]{0,12}?(\d[\d,]{6,}\s*원|\d+(?:\.\d+)?\s*억)"

# 보증금·보증금환원율 (2026-09-28 소유자 지시: "보증금 보증금환원율은 빼줘")
#   기대이율·필요제경비는 총괄수치로 게재하지만, 보증금 계열은 **미게재**로 확정되었다.
#   FAQ 의 「실질임대료와 지불임대료(보증금+월세)는 무엇이 다른가요?」처럼 용어를 설명하는 것은 허용하고,
#   **금액이나 요율이 붙은 경우만** 오류로 잡는다.
DEPOSIT_ERR_PATTERNS = [
    ("보증금환원율", r"보증금\s*환원율"),
    ("전환이율", r"전환\s*이율"),
    ("보증금 금액", r"보증금[^\n<]{0,20}?(?:\d[\d,]{5,}\s*원|\d+(?:\.\d+)?\s*억)"),
    ("보증금 요율", r"보증금[^\n<]{0,20}?\d+(?:\.\d+)?\s*(?:%|％)"),
]

# MASK_LEVEL=range 에서 금지 (결정 3)
RANGE_PATTERNS = [
    ("정확 금액(쉼표 3자리 이상)", r"\d{1,3}(?:,\d{3}){2,}\s*원"),
    ("결정단가", r"결정단가"),
    ("산출금액", r"산출금액"),
    ("필지 수", r"\d+\s*필지"),
    ("동 수", r"\d+\s*개?\s*동(?![산시일안])"),
    ("소수점 면적", r"\d+\.\d+\s*㎡"),
    ("VALUE_NUMERIC 잔존", r"VALUE_NUMERIC"),
]

# 법인 마스킹 (결정 4)
CORP_OWNERS = ("법인", "부동산신탁회사", "유동화전문회사", "재단", "법원")
# 지번: 행정동/읍/면/리 + 숫자, 또는 '○○동5가 123' 형태.
# 소수점 면적(84.98㎡)·연도(2000년)가 걸리지 않도록 뒤따르는 문자를 제한한다.
JIBEON_RE = (r"(?:[가-힣]{2,6}(?:동|읍|면|리)|[가-힣]{2,6}\d{1,2}가)"
             r"\s*\d{1,5}(?:-\d{1,4})?(?=\s*(?:번지|외\s*\d|[,)\s<]|$))")
BUILDING_RE = (r"([가-힣A-Za-z]{2,10})(빌딩|타워|프라자|플라자|캐슬|자이|푸르지오|래미안"
               r"|아이파크|힐스테이트|더샵|센터|아파트|오피스텔)")
BUILDING_OK_PREFIX = {"지식산업", "물류", "판매", "고객", "상담", "데이터", "업무", "유통",
                      "복합", "근린", "도시형생활", "생활형", "주상복합", "산업", "연구",
                      "쇼핑", "컨벤션", "전시", "체육", "문화"}
SINTAK_RE = r"([가-힣A-Za-z]{2,8})(부동산신탁|자산신탁|신탁)"
SINTAK_OK_PREFIX = {"부동산", "관리형토지", "차입형토지", "관리형", "차입형", "담보", "처분",
                    "분양관리", "개발", "토지", "자산", "금전", "특정금전", "유언대용",
                    "공익", "수익권", "우선수익", "위탁자", "수탁자"}
CORP_SUFFIX_RE = r"(?:주식회사|㈜|\(주\)|유한회사|주식회사\s*[가-힣A-Za-z]{2,12})"
# 자사 표기 — 법인 마스킹 검사 전에 지운다
SELF_STRINGS = ("㈜감정평가법인 가치앤같이", "감정평가법인 가치앤같이", "가치앤같이",
                "가람빌딩", "강남대로 86", "5층 501호", "5층501호")
# 자사 본사 주소(서초구 강남대로 86, 5층 501호)에서 나오는 값 — 본건 층·호가 아니다
SELF_FLOOR_HO = {"5층", "501호", "5 층", "501 호"}

# 기준시점 월·일 (임대료 외 금지 / 결정 2)
GIJUN_MD_PATTERNS = [
    r"기준시점[^0-9]{0,10}\d{4}\s*년\s*\d{1,2}\s*월",
    r"기준시점[^0-9]{0,10}\d{4}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}",
    r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일[^0-9]{0,12}기준시점",
]

# 4-Z 스윕에서 승격된 구조 검사
FORBIDDEN_SCHEMA_RE = r'aggregateRating|"@type"\s*:\s*"Review"|"@type"\s*:\s*"Product"|"@type"\s*:\s*"Offer"|speakable'
FIXED_BLOCKS = (
    ("date-note", r'class="[^"]*date-note'),
    ("calc-note", r'class="[^"]*calc-note'),
    ("푸터 안내문(law-note)", r'class="[^"]*law-note'),
    ("case-cta-desc", r'case-cta-desc'),
)
# 2026-09-30 소유자 확정 — 마스킹은 CSS 스팬이 아니라 평문 O 기호로 표기한다.
# 스팬/블록문자는 소스만 보면 자리수가 드러나고 스타일 제거로 눈에 띄므로 폐지.
# 2026-10-13 소유자 지시로 표기 축약 — 「O층OO호 로 표기.」
#   `O` 개수는 **실제 자릿수와 무관하게 고정**이다. 자릿수를 맞추면 몇 자리인지가 드러나므로
#   (= 자리수 자체가 정보) 실제가 3층 1502호든 지하 1층 101호든 언제나 `O층OO호` 다.
FLOOR_MASK = 'O층'
HO_MASK = 'OO호'
# 구 표기(2026-09-30 ~ 10-13). 자릿수를 맞춘 표기라 폐지되었다.
#   `제OO층` 은 `O층` 을, `OOO호` 는 `OO호` 를 부분문자열로 포함하므로
#   신 표기를 셀 때는 반드시 구 표기를 먼저 지운 사본에서 센다(strip_old_mask).
FLOOR_MASK_OLD = '제OO층'
HO_MASK_OLD = 'OOO호'
JIBEON_MASK = 'OO-OO'   # 미사용 — 2026-10-13 지시로 집합건물은 지번까지 공개한다.

# ================================================================ 「벗겨지는 마스킹」 차단
# 근거: templates/작성가이드_v5.md §4-6 (2026-10-13 소유자 지시로 원칙 확정)
#   「집합건물은 지번까지 보여주고, 동, 층, 호는 O처리 혹은 아예 삭제.
#     (벗겨지는 마킹은 절대 사용 금지)」
# 원칙: 실제 층수·호수·동(棟) 번호 숫자는 **파일 안에 존재해서도 안 된다.**
#   화면에 안 보이게 가리는 것으로는 부족하다 — 소스 보기·개발자도구·크롤러·curl 로
#   그대로 읽히기 때문이다. 가려 둔 값은 「가려진 값」이 아니라 그냥 공개된 값이다.

# (가) 정상 용도가 전혀 없는 가리기 수단 — 내용과 무관하게 오류.
#      전 저장소 0건임을 확인한 것만 넣는다(오탐 0).
PEEL_MECH_ERR = [
    ("-webkit-text-security",
     r"-webkit-text-security"),
    ("addr-mask 류 마스킹 클래스",
     r"\baddr-mask\b|\b(?:floor|unit|ho|jibeon|dong|addr)-mask\b"),
    ("마스킹 블록문자(█·▇·■)",
     "[\u2588\u2587\u25a0]"),
]

# filter:blur 는 **상단 메뉴바의 backdrop-filter 와 반드시 구분한다.**
#   nav { ... backdrop-filter: blur(14px); } 는 전 페이지에 정상적으로 쓰이는 반투명 효과다.
#   이것을 오류로 올리면 모든 초안이 반려되므로, backdrop-filter 선언을 **먼저 지운 사본**에서
#   filter:blur 를 찾는다. -webkit-backdrop-filter 등 접두사형도 같이 지운다.
BACKDROP_DECL_RE = r"(?:-webkit-|-moz-|-ms-|-o-)?backdrop-filter\s*:[^;}\"\']*"
BLUR_DECL_RE = r"(?:-webkit-|-moz-|-ms-|-o-)?filter\s*:[^;}\"\']*\bblur\s*\("

# (나) 정상 용도가 **있는** 가리기 속성 — 가려진 요소 안에 실제 층·호·동 숫자가
#      들어 있을 때만 오류로 올린다. 무조건 오류로 하면 안 되는 이유(실측):
#        display:none  -> FAQ 아코디언 `.faq-item.collapsed .faq-a` (전 페이지 1건)
#        opacity:0     -> 페이드인 초기상태 `.fade-up` / `.hero-content` (index.html 3건)
HIDE_PROP_RE = (r"display\s*:\s*none"
                r"|visibility\s*:\s*hidden"
                r"|opacity\s*:\s*0(?![.0-9])"
                r"|font-size\s*:\s*1px"
                r"|color\s*:\s*var\(\s*--bg\s*\)")

# 실제 층·호·동 번호 판정 패턴.
#   **기존 가시본문 검사(structural_checks)와 똑같은 패턴을 쓴다.** 새로 넓히지 않는 이유:
#   가시본문에서 통과하던 표기가 숨은 표면에서만 걸리면 규칙이 두 개가 되어 혼란스럽고,
#   패턴을 넓히면 오탐이 난다. 실측으로 확인한 정상 표기들:
#     - 「철근콘크리트구조 지하 1층·지상 4층 숙박시설」 = 건물 **규모 서술**(본건 전유부 층이 아님)
#       -> `제\d+층` 으로만 잡으므로 걸리지 않는다.
#     - 「규칙 제2조 제6호」·「제22조」 = 법령 조문 번호
#       -> `호` 는 3~4자리만 잡으므로 걸리지 않는다.
#     - 「제1016호」(회계기준서 번호) -> 앞 25자 안의 기준서·회계기준 문맥으로 제외.
#     - 「가산동」 등 행정동 -> `동` 은 숫자+동만 잡으므로 걸리지 않는다.
#     - 법인 본사 「강남대로 86, 5층 501호 (양재동, 가람빌딩)」 -> strip_self + SELF_FLOOR_HO 로 제외.
REAL_FLOOR_HO_RE = r"제\s*\d+\s*층|\d{3,4}\s*호(?!수)"
REAL_DONG_RE = r"\d{2,3}\s*동(?![산시일안])"
LAW_NO_CTX_RE = r"고시|훈령|예규|기준서|회계기준|법률|대통령령"
# 단지 **총 동수**는 본건 동(棟) 번호가 아니다 — 작성가이드 10-4 는 「본건 동 번호」·
#   「비교사례 동 번호」만 0건을 요구한다. 실측 오탐: cases/yangcheon-mokdong-2025.html 의
#   JSON-LD description 「… 단지 32동 1,588세대」(= 단지 전체 규모, 공개정보).
#   본건 동은 「아파트 32동」·「제32동」·「32동 1502호」 꼴로 나오므로 이 예외에 걸리지 않는다.
DONG_COUNT_CTX_RE = r"(?:단지|총|전체|규모|모두)\s*$"
DONG_COUNT_AFTER_RE = r"^\s*[\d,]*\s*(?:세대|가구|규모|동$)"

# 검사할 「숨은 표면」 속성 — 소스·접근성 트리·크롤러에 전부 노출된다.
PEEL_ATTRS_RE = (r"\b(aria-label|title|alt|content|data-[A-Za-z0-9_-]+)"
                 r"\s*=\s*(\"[^\"]*\"|\'[^\']*\')")


def strip_old_mask(html):
    """구 표기를 지운 사본. 신 표기(O층·OO호) 개수를 셀 때 반드시 먼저 거친다."""
    return html.replace(FLOOR_MASK_OLD, " ").replace(HO_MASK_OLD, " ")


def real_floor_ho_dong(text):
    """실제 층·호·동 번호로 보이는 표기 목록.

    본사 주소·법령/기준서 번호·하이픈 뒤 숫자는 제외한다.
    판정 기준은 기존 가시본문 검사와 동일하다(위 주석 참조).
    """
    st = strip_self(norm_ws(text))
    out = []
    for m in re.finditer(REAL_FLOOR_HO_RE, st):
        w = norm_ws(m.group(0))
        if w in SELF_FLOOR_HO:
            continue
        before = st[max(0, m.start() - 25):m.start()]
        if before.endswith("-") or re.search(LAW_NO_CTX_RE, before):
            continue
        out.append(w)
    for m in re.finditer(REAL_DONG_RE, st):
        before = st[max(0, m.start() - 10):m.start()]
        after = st[m.end():m.end() + 12]
        if re.search(DONG_COUNT_CTX_RE, before) or re.search(DONG_COUNT_AFTER_RE, after):
            continue          # 단지 총 동수 — 본건 동 번호가 아니다
        out.append(norm_ws(m.group(0)))
    return out


def _elems_with_class(html, cls):
    """class 에 cls 가 든 요소의 내용(바깥 태그 제외)을 뽑는다. 중첩 동일태그는 근사."""
    out = []
    pat = (r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*\bclass\s*=\s*[\"\'][^\"\']*(?<![-\w])"
           + re.escape(cls) + r"(?![-\w])[^\"\']*[\"\'][^>]*>([\s\S]*?)</\1\s*>")
    for m in re.finditer(pat, html):
        out.append(m.group(2))
    return out


def peel_mask_checks(html):
    """「벗겨지는 마스킹」 차단 (작성가이드 v5 §4-6). 전부 오류 — 위치·목적과 무관."""
    errs, warns = [], []

    # 1) 정상 용도가 없는 가리기 수단 — 내용 무관
    for label, pat in PEEL_MECH_ERR:
        n = len(re.findall(pat, html, re.I))
        if n:
            errs.append("「벗겨지는 마스킹」 수단 %s 이(가) %d건 있습니다. "
                        "가리는 것이 아니라 처음부터 평문 `O층OO호` 로 쓰십시오. (§4-6)"
                        % (label, n))

    # 2) filter:blur — 상단 메뉴바의 backdrop-filter 는 정상이므로 먼저 지운다
    nob = re.sub(BACKDROP_DECL_RE, " ", html, flags=re.I)
    n = len(re.findall(BLUR_DECL_RE, nob, re.I))
    if n:
        errs.append("「벗겨지는 마스킹」 수단 filter:blur 이(가) %d건 있습니다(원문이 그대로 "
                    "전송됩니다). 상단 메뉴바의 backdrop-filter 는 정상이며 여기서 제외했습니다. (§4-6)"
                    % n)

    # 3) 숨은 표면에 실제 층·호·동 숫자 — 속성 / HTML 주석 / JSON-LD
    for m in re.finditer(PEEL_ATTRS_RE, html):
        val = m.group(2)[1:-1]
        hits = real_floor_ho_dong(val)
        if hits:
            errs.append("%s 속성값에 실제 층·호·동 번호가 있습니다: %s (값: '%s') — 속성값은 "
                        "소스·접근성 트리·크롤러에 전부 노출됩니다. (§4-6)"
                        % (m.group(1), ", ".join(sorted(set(hits))[:5]), norm_ws(val)[:60]))
            break
    for c in re.findall(r"<!--([\s\S]*?)-->", html):
        hits = real_floor_ho_dong(c)
        if hits:
            errs.append("HTML 주석에 실제 층·호·동 번호가 있습니다: %s (주석: '%s') — 주석은 "
                        "소스 보기로 100%% 읽힙니다. (§4-6)"
                        % (", ".join(sorted(set(hits))[:5]), norm_ws(c)[:60]))
            break
    for b in jsonld_blocks(html):
        hits = real_floor_ho_dong(b)
        if hits:
            errs.append("JSON-LD 에 실제 층·호·동 번호가 있습니다: %s — 구조화데이터는 기계가 "
                        "읽도록 만든 자리라 가장 먼저 수집됩니다. (§4-6)"
                        % ", ".join(sorted(set(hits))[:5]))
            break

    # 4) 가려진 요소 안에 실제 층·호·동 숫자
    #    (가) 인라인 style 로 가린 요소
    ipat = (r"<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*\bstyle\s*=\s*[\"\'][^\"\']*(?:" + HIDE_PROP_RE
            + r")[^\"\']*[\"\'][^>]*>([\s\S]*?)</\1\s*>")
    for m in re.finditer(ipat, html, re.I):
        hits = real_floor_ho_dong(m.group(2))
        if hits:
            errs.append("인라인 style 로 가린 <%s> 안에 실제 층·호·동 번호가 있습니다: %s "
                        "— 스타일만 끄면 즉시 노출됩니다. (§4-6)"
                        % (m.group(1), ", ".join(sorted(set(hits))[:5])))
            break

    #    (나) <style> 규칙으로 가린 클래스의 요소
    #        FAQ 아코디언(.faq-a)·페이드인(.fade-up)처럼 정상 용도가 있으므로
    #        **그 요소 안에 실제 숫자가 있을 때만** 오류다.
    css = " ".join(re.findall(r"<style[^>]*>([\s\S]*?)</style>", html, re.I))
    hidden_cls = set()
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        if re.search(HIDE_PROP_RE, m.group(2), re.I):
            hidden_cls.update(re.findall(r"\.([A-Za-z_][\w-]*)", m.group(1)))
    for cls in sorted(hidden_cls):
        bad = []
        for body in _elems_with_class(html, cls):
            bad += real_floor_ho_dong(body)
        if bad:
            errs.append("CSS 로 가린 요소(.%s) 안에 실제 층·호·동 번호가 있습니다: %s "
                        "— 스타일만 끄면 즉시 노출됩니다. (§4-6)"
                        % (cls, ", ".join(sorted(set(bad))[:5])))
            break

    return errs, warns


DRAFT_DIRS = ("review", "queue")


def visible_text(html):
    """head/script/style 를 뺀 가시 본문 텍스트."""
    b = re.sub(r"<head[\s\S]*?</head>", "", html, flags=re.I)
    b = re.sub(r"<script[\s\S]*?</script>", "", b, flags=re.I)
    b = re.sub(r"<style[\s\S]*?</style>", "", b, flags=re.I)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", b))).strip()


def is_draft_path(html_path):
    """automation/review · automation/queue 안의 초안인가."""
    parts = os.path.abspath(html_path).replace("\\", "/").split("/")
    return len(parts) >= 2 and parts[-2] in DRAFT_DIRS


def detect_branch(meta, html):
    """(branch, 판정근거, warnings) — .meta.tsv 의 purpose_branch > cat > 본문 추정."""
    warns = []
    pb = (meta.get("purpose_branch") or "").strip()
    if pb:
        if pb in BRANCHES:
            return pb, "meta.purpose_branch", warns
        warns.append("meta.tsv 의 purpose_branch 값 '%s' 을(를) 알 수 없습니다. 허용값: %s"
                     % (pb, " / ".join(BRANCHES)))
    cat = (meta.get("cat") or "").strip()
    if cat in CAT2BRANCH:
        b = CAT2BRANCH[cat]
        if b:
            return b, "meta.cat=%s" % cat, warns
        # 부동산컨설팅 — 임대료인지 본문으로 추정
        if re.search(r"제\s*22\s*조|실질임대료|지불임대료|적산법|임대료\s*감정평가", html):
            warns.append("cat=부동산컨설팅 인데 meta.tsv 에 purpose_branch 가 없습니다. "
                         "본문으로 '임대료' 로 추정했습니다 — meta.tsv 에 명시하십시오.")
            return "임대료", "본문 추정(부동산컨설팅)", warns
        warns.append("cat=부동산컨설팅 인데 meta.tsv 에 purpose_branch 가 없습니다. "
                     "'기타' 로 보고 목적별 검사를 건너뜁니다 — meta.tsv 에 명시하십시오.")
        return "기타", "본문 추정(부동산컨설팅)", warns
    if cat:
        warns.append("meta.tsv 의 cat 값 '%s' 이(가) 홈 카테고리 목록에 없습니다. "
                     "목적별 검사를 건너뜁니다." % cat)
    else:
        warns.append("meta.tsv 에 cat 이 없어 목적 분기를 판정할 수 없습니다. "
                     "목적별 검사를 건너뜁니다(나머지 검사는 그대로 수행).")
    return None, "판정 불가", warns


def strip_self(html):
    s = html
    for t in SELF_STRINGS:
        s = s.replace(t, " ")
    return s


def _hits(pattern, text, limit=4):
    return [norm_ws(m)[:60] for m in re.findall(pattern, text)][:limit]


# ---------------------------------------------------------------- v2 검사 본체
def purpose_checks(html, text, branch):
    """목적별 법령 오염 · 임대료 수치 · 기준시점 월·일."""
    errs, warns = [], []

    # 전 목적 — 감정서에 없는 용어
    m = re.search(KIFRS_ERR, html)
    if m:
        errs.append("감정서에 없는 용어가 있습니다(전 목적 금지): '%s'" % norm_ws(m.group(0)))
    if re.search(KIFRS_WARN, html):
        warns.append("「한국채택국제회계기준」 표기가 있습니다. 결정서상 당분간 "
                     "「일반기업회계기준」만 씁니다(해당 감정서는 게시 보류 건).")

    if branch is None:
        return errs, warns

    # 1) 목적별 법령 오염
    if branch in LAW_STRICT_BRANCHES:
        for label, pat in SANGJEUNG_TERMS:
            n = len(re.findall(pat, html))
            if n:
                errs.append("목적 분기가 '%s' 인데 상속·증여 전용 표현 %s 이(가) %d건 있습니다. "
                            "전부 삭제하십시오." % (branch, label, n))
    elif branch == "기타":
        for label, pat in SANGJEUNG_TERMS:
            if re.search(pat, html):
                warns.append("목적 분기가 '기타' 인데 상속·증여 전용 표현 %s 이(가) 있습니다. "
                             "목적란 인쇄 문구를 확인하십시오." % label)
                break

    # 2) 재무보고 기준가치
    if branch == "재무보고":
        n = len(re.findall(r"시장가치", html))
        if n:
            errs.append("재무보고(자산재평가) 건의 기준가치는 「공정가치」입니다. "
                        "'시장가치' 가 %d건 있습니다." % n)
        if "공정가치" not in html:
            warns.append("재무보고 건인데 '공정가치' 표현이 없습니다. "
                         "「일반기업회계기준」 정형문을 확인하십시오.")
        if "일반기업회계기준" not in html:
            warns.append("재무보고 건인데 「일반기업회계기준」 인용이 없습니다.")

    # 3) 임대료 — 총괄수치는 허용, 종별 내역만 막는다 (결정 1, 2026-09-28 개정)
    if branch == "임대료":
        # 템플릿 주석(「… 임차인별 배분표는 쓰지 않는다」 등 지침 문장)이 초안에 그대로 남으므로
        # 이 검사들만 주석을 지운 본문에서 돌린다.
        html_nc = re.sub(r"<!--[\s\S]*?-->", "", html)
        for label, pat in RENT_BREAKDOWN_WARNS:
            m = re.search(pat, html_nc)
            if m:
                warns.append("임대료 건에 종별 내역으로 보이는 표기가 있습니다 — %s: '%s'. "
                             "총괄수치(기초가액 총액·기대이율 단일 %%·필요제경비 총액)로만 쓰십시오. (결정 1 개정)"
                             % (label, norm_ws(m.group(0))[:70]))
        if "기초가액" in html_nc:
            kinds = {}
            for m in re.finditer(RENT_KIND_AMOUNT_RE, html_nc):
                kinds.setdefault(m.group(1), norm_ws(m.group(0))[:30])
            if len(kinds) >= 2:
                warns.append("임대료 건에 종별 기초가액 내역으로 보이는 표기가 %d종 있습니다: %s. "
                             "기초가액은 **총액 한 줄**로만 쓰십시오(종별 내역 금지). (결정 1 개정)"
                             % (len(kinds), " / ".join(kinds.values())))
        for label, pat in DEPOSIT_ERR_PATTERNS:
            m = re.search(pat, html_nc)
            if m:
                errs.append("임대료 건에 보증금 계열 수치가 있습니다 — %s: '%s'. "
                            "2026-09-28 소유자 지시로 보증금·보증금환원율(전환이율)은 미게재입니다. "
                            "보증금 유무만 서술하십시오."
                            % (label, norm_ws(m.group(0))[:60]))
        if re.search(r"제\s*22\s*조", html) is None:
            warns.append("임대료 건인데 「감정평가에 관한 규칙」 제22조 인용이 없습니다.")

    # 4) 기준시점 월·일 (결정 2 — 임대료만 허용)
    if branch != "임대료":
        for pat in GIJUN_MD_PATTERNS:
            m = re.search(pat, text)
            if m:
                errs.append("기준시점에 월·일이 있습니다: '%s' — 임대료 목적 외에는 연도만 씁니다."
                            % norm_ws(m.group(0))[:60])
                break
    else:
        if re.search(r"기준시점[^。\n]{0,40}월[·ㆍ・]?\s*일[^。\n]{0,20}표기하지\s*않", text) or \
           re.search(r"기준시점의\s*월[·ㆍ・]?\s*일[^。\n]{0,20}싣지\s*않", text):
            warns.append("임대료 건인데 '기준시점의 월·일을 싣지 않았다' 는 상속용 고정문구가 "
                         "남아 있습니다(결정 2와 모순). 안내문을 임대료용으로 고치십시오.")
        if "역산" not in html and not re.search(r"선행|기산일|작성일이", text):
            warns.append("임대료 건은 작성일이 기준시점(임대차 기산일)보다 앞서는 경우가 흔합니다. "
                         ".date-note 에 그 사실을 밝혔는지 확인하십시오.")

    return errs, warns


def mask_level_checks(html, mask_level):
    """MASK_LEVEL=range 구간 처리 검사 (결정 3)."""
    errs, warns = [], []
    if mask_level != "range":
        return errs, warns
    for label, pat in RANGE_PATTERNS:
        hits = re.findall(pat, html)
        if hits:
            errs.append("MASK_LEVEL=range 인데 %s 이(가) %d건 있습니다: %s (결정 3)"
                        % (label, len(hits), ", ".join(_hits(pat, html))))
    for b in jsonld_blocks(html):
        if re.search(r'"price"', b):
            errs.append("MASK_LEVEL=range 인데 JSON-LD 에 \"price\" 속성이 남아 있습니다. "
                        "about.price 를 속성째 삭제하십시오. (결정 3)")
            break
    if not re.search(r"약\s*[\d.]+\s*(?:만)?\s*㎡|억원대|다수\s*필지|여러\s*동", html):
        warns.append("MASK_LEVEL=range 인데 구간 표기(약 …㎡ / …억원대 / 다수 필지)가 "
                     "보이지 않습니다. 구간 처리를 실제로 적용했는지 확인하십시오.")
    return errs, warns


def corp_mask_checks(html, owner_type):
    """법인 마스킹 검사 (결정 4)."""
    errs, warns = [], []
    if not owner_type or owner_type == "개인":
        return errs, warns
    h = strip_self(html)
    t = visible_text(h)

    jb = re.findall(JIBEON_RE, t)
    if jb:
        errs.append("법인 건(owner_type=%s)인데 지번으로 보이는 표기가 %d건 있습니다: %s "
                    "— 동·읍·면까지만 씁니다. (결정 4)"
                    % (owner_type, len(jb), ", ".join(jb[:5])))

    bad_bld = [a + b for a, b in re.findall(BUILDING_RE, t) if a not in BUILDING_OK_PREFIX]
    if bad_bld:
        errs.append("법인 건인데 단지명·건물명으로 보이는 표기가 있습니다: %s "
                    "— 법인 건에서는 쓰지 않습니다. (결정 4)" % ", ".join(sorted(set(bad_bld))[:5]))

    for m in re.finditer(r"(.{0,40})(제?\s*\d+\s*차)(.{0,40})", t):
        ctx = m.group(1) + m.group(3)
        if re.search(r"유동화|자산유동화|SPC|특수목적", ctx):
            errs.append("법인 건에 유동화전문회사 차수 표기가 있습니다: '%s' (앞뒤: …%s…) "
                        "— 차수는 검색으로 바로 특정됩니다. (결정 4)"
                        % (norm_ws(m.group(2)), norm_ws(m.group(1)[-12:] + m.group(3)[:12])))
            break
    else:
        cha = [x for x in re.findall(r"\d+\s*차(?![이례량감액후원선종단])", t)]
        if cha:
            warns.append("법인 건에 '%s' 같은 차수 표기가 있습니다. 유동화 차수가 아닌지 "
                         "확인하십시오." % ", ".join(sorted(set(cha))[:4]))

    bad_st = [a + b for a, b in re.findall(SINTAK_RE, t) if a not in SINTAK_OK_PREFIX]
    if bad_st:
        warns.append("법인 건에 신탁회사명으로 보이는 표기가 있습니다: %s — 수탁자는 "
                     "'부동산신탁회사(수탁자)' 처럼 유형으로만 씁니다. (결정 4)"
                     % ", ".join(sorted(set(bad_st))[:5]))

    m = re.search(r"(?:주식회사|㈜|\(주\))\s*[가-힣A-Za-z]{2,12}|[가-힣A-Za-z]{2,12}\s*(?:주식회사|㈜|\(주\))", t)
    if m:
        errs.append("법인 건에 회사명 표기가 있습니다: '%s' — 법인명은 일절 쓰지 않습니다. (결정 4)"
                    % norm_ws(m.group(0))[:60])

    for kw in ("임차인", "업종", "설비 품목", "관계회사"):
        if kw in t:
            warns.append("법인 건에 '%s' 서술이 있습니다. 결정 4에 따라 업종·설비·임차인은 "
                         "쓰지 않습니다." % kw)
    return errs, warns


def structural_checks(html, strict):
    """4-Z 스윕에서 승격된 구조·마스킹 검사. strict=False 면 경고로 완화(구 게시본)."""
    E, W = [], []
    out = E if strict else W

    def n(p):
        return len(re.findall(p, html))

    h2 = n(r"<h2[\s>]")
    if h2 != 9:
        out.append("<h2> 개수가 %d개입니다(생성지침 v5 기준 정확히 9개)." % h2)
    cap = n(r"<caption")
    if cap != 2:
        out.append("<caption> 개수가 %d개입니다(표마다 1개, 정확히 2개)." % cap)
    law = n(r"law\.go\.kr")
    if law < 2:
        out.append("본문 법령 링크(law.go.kr)가 %d개입니다(2개 이상 필요)." % law)
    smr = n(r'id="summary"')
    if smr != 1:
        out.append('요약 섹션 id="summary" 가 %d개입니다(정확히 1개).' % smr)
    hx = n(FORBIDDEN_SCHEMA_RE)
    if hx:
        E.append("금지 스키마(aggregateRating·Review·Product·Offer·speakable) %d건이 있습니다." % hx)
    hu = n(r"/cases/[a-z0-9\-]+\.html")
    if hu:
        out.append("'.html' 이 붙은 /cases/ URL 이 %d건 있습니다(확장자 없는 형식만 씁니다)." % hu)
    for label, pat in FIXED_BLOCKS:
        if not n(pat):
            out.append("템플릿 고정문구 %s 가 없습니다(축약 과정에서 지우지 마십시오)." % label)

    # 마스킹 — 목적·마스킹 수준과 무관하게 항상 오류
    # (1) 구 표기 / 자릿수를 맞춘 표기. 신 표기 검사보다 **먼저** 돌린다.
    #     `제OO층` 은 `O층` 을, `OOO호` 는 `OO호` 를 부분문자열로 포함하므로
    #     그냥 세면 구 표기가 신 표기로 오인된다.
    n_fo, n_ho = html.count(FLOOR_MASK_OLD), html.count(HO_MASK_OLD)
    if n_fo or n_ho:
        det = ["%s %d건" % (FLOOR_MASK_OLD, n_fo)] if n_fo else []
        if n_ho:
            det.append("%s %d건" % (HO_MASK_OLD, n_ho))
        E.append("구 마스킹 표기(%s)가 남아 있습니다. 구 표기입니다. "
                 "`%s`·`%s`(붙여 쓰면 `O층OO호`) 로 바꾸십시오 — O 개수는 실제 자릿수와 "
                 "무관하게 고정입니다. (2026-10-13 소유자 지시)"
                 % (" / ".join(det), FLOOR_MASK, HO_MASK))
    h_new = strip_old_mask(html)
    odd = set()
    for m in re.finditer(r"O+(?=층)", h_new):
        if len(m.group(0)) != len(FLOOR_MASK) - 1:
            odd.add(m.group(0) + "층")
    for m in re.finditer(r"O+(?=호)", h_new):
        if len(m.group(0)) != len(HO_MASK) - 1:
            odd.add(m.group(0) + "호")
    if odd:
        E.append("층·호 마스킹의 O 개수가 고정 표기와 다릅니다: %s — 실제 자릿수와 무관하게 "
                 "`%s`·`%s`(붙여 쓰면 `O층OO호`) 로만 씁니다. 자릿수를 맞추면 몇 자리인지가 "
                 "드러납니다. (2026-10-13 소유자 지시)"
                 % (", ".join(sorted(odd)), FLOOR_MASK, HO_MASK))

    # (2) 집합건물이면 신 표기가 각각 1회 이상 있어야 한다.
    #     구 표기가 걸린 건은 (1) 이 이미 「구 표기를 바꾸라」고 지시했으므로 여기서는 건너뛴다.
    #     (구 표기가 있는데 「마스킹 기호가 없다」고 또 올리면 서로 모순되게 읽힌다.)
    if "전유면적" in html and not (n_fo or n_ho):
        if h_new.count(FLOOR_MASK) < 1 or h_new.count(HO_MASK) < 1:
            E.append("집합건물인데 층·호 마스킹 기호가 없습니다(%s %d건 / %s %d건). "
                     "`O층OO호` 로 쓰십시오."
                     % (FLOOR_MASK, h_new.count(FLOOR_MASK),
                        HO_MASK, h_new.count(HO_MASK)))

    # (3) 「벗겨지는 마스킹」 전면 차단 (§4-6) — 구 기호·블록문자 검사도 여기로 합쳤다.
    pe, pw = peel_mask_checks(html)
    E.extend(pe)
    W.extend(pw)
    t = visible_text(html)
    st = strip_self(t)
    fl = []
    for m in re.finditer(r"제\s*\d+\s*층|\d{3,4}\s*호(?!수)", st):
        w = norm_ws(m.group(0))
        if w in SELF_FLOOR_HO:
            continue
        before = st[max(0, m.start() - 25):m.start()]
        if before.endswith("-") or re.search(r"고시|훈령|예규|기준서|회계기준|법률|대통령령", before):
            continue          # 고시·기준서 번호(예: 고시 제2024-123호)
        fl.append(w)
    if fl:
        E.append("본건 실제 층·호로 보이는 표기가 있습니다: %s" % ", ".join(sorted(set(fl))[:6]))
    dong = re.findall(r"\d{2,3}\s*동(?![산시일안])", t)
    if dong:
        E.append("동(棟) 번호로 보이는 표기가 있습니다: %s" % ", ".join(sorted(set(dong))[:6]))
    for kw in ("사정보정", "시점수정", "가격지수"):
        c = html.count(kw)
        if c:
            E.append("규칙 B 위반 — '%s' 가 %d건 있습니다." % (kw, c))

    ln = len(t)
    if ln > 5100:
        out.append("가시 본문이 %d자입니다(5,100자 이내)." % ln)
    dts = sorted(set(re.findall(r'datetime="(\d{4}-\d{2}-\d{2})"', html)))
    if len(dts) > 3:
        out.append("날짜형 datetime 이 %d종입니다(게시일·최종 업데이트·작성일 3종 이하): %s"
                   % (len(dts), ", ".join(dts)))

    road = [x for x in re.findall(r"[가-힣]+(?:대로|로|길)\s*\d+(?:번길)?", strip_self(t))]
    if road:
        W.append("도로명주소로 보이는 표기가 있습니다: %s" % ", ".join(sorted(set(road))[:5]))
    if not strict and W:
        W.insert(0, "구 템플릿으로 만들어진 게시본으로 보여 구조 검사를 경고로 완화했습니다"
                    " (초안 폴더 review/·queue/ 의 파일은 오류로 막습니다).")
    return E, W


def draft_checks_v2(html, html_path, meta, strict):
    errs, warns = [], []
    branch, basis, w = detect_branch(meta, html)
    warns.extend(w)

    mask = (meta.get("mask_level") or "exact").strip().lower()
    if mask not in ("exact", "range"):
        warns.append("meta.tsv 의 mask_level 값 '%s' 을(를) 알 수 없습니다. 'exact' 로 봅니다." % mask)
        mask = "exact"
    if "mask_level" not in meta:
        warns.append("meta.tsv 에 mask_level 키가 없습니다. 기본값 'exact' 로 검사했습니다 "
                     "(생성지침 v5 Step 7-C).")
    owner = (meta.get("owner_type") or "").strip()
    if not owner:
        if mask == "range":
            owner = "법인"
            warns.append("meta.tsv 에 owner_type 이 없는데 mask_level=range 이므로 "
                         "'법인' 으로 보고 법인 마스킹을 검사했습니다.")
        else:
            owner = "개인"

    text = visible_text(html)
    e, w = purpose_checks(html, text, branch)
    errs += e
    warns += w
    e, w = mask_level_checks(html, mask)
    errs += e
    warns += w
    e, w = corp_mask_checks(html, owner)
    errs += e
    warns += w
    e, w = structural_checks(html, strict)
    errs += e
    warns += w
    return errs, warns, dict(branch=branch or "(판정불가)", branch_basis=basis,
                             mask_level=mask, owner_type=owner, strict=strict)


# ---------------------------------------------------------------- 공개 API
def validate_draft(html_path, base_slug=None, check_meta=True, strict=None):
    """반환: (errors, warnings, stats)"""
    html = read_text(html_path)
    slug = base_slug or slug_from_filename(html_path)
    errs, warns = base_validate(html, slug)
    errs = list(errs)
    warns = list(warns)
    e2, w2, stats = draft_checks(html, html_path, slug, check_meta=check_meta)
    # 게시 스크립트와 초안 게이트가 같은 문구로 중복 보고되는 것을 정리
    for e in e2:
        if e not in errs:
            errs.append(e)
    for w in w2:
        if w not in warns:
            warns.append(w)

    # ---- v2 신설: 목적 분기 · MASK_LEVEL · 법인 마스킹 · 구조 검사 ----
    meta = read_meta(find_meta_path(html_path))
    if strict is None:
        strict = is_draft_path(html_path)
    e3, w3, st3 = draft_checks_v2(html, html_path, meta, strict)
    for e in e3:
        if e not in errs:
            errs.append(e)
    for w in w3:
        if w not in warns:
            warns.append(w)
    stats.update(st3)
    stats["slug"] = slug
    return errs, warns, stats


def report(html_path, errs, warns, stats):
    lines = []
    lines.append("=" * 68)
    lines.append("초안 검증: %s" % os.path.basename(html_path))
    lines.append("  슬러그: %s" % stats.get("slug"))
    lines.append("  h1 %s개 · h2 %s개 · h3 %s개 · JSON-LD %s블록 · FAQ %s개"
                 % (stats.get("h1"), stats.get("h2"), stats.get("h3"),
                    stats.get("jsonld"), stats.get("faq")))
    lines.append("  canonical: %s" % (stats.get("canonical") or "(없음)"))
    lines.append("  목적분기: %s (%s) · MASK_LEVEL: %s · owner_type: %s · 검사강도: %s"
                 % (stats.get("branch"), stats.get("branch_basis"),
                    stats.get("mask_level"), stats.get("owner_type"),
                    "초안(엄격)" if stats.get("strict") else "게시본(구조검사 완화)"))
    lines.append("-" * 68)
    if errs:
        lines.append("[오류] %d건 — 이 초안은 게시할 수 없습니다." % len(errs))
        for e in errs:
            lines.append("  ✗ %s" % e)
    else:
        lines.append("[오류] 0건 — 게시 게이트 통과")
    if warns:
        lines.append("[경고] %d건 — 사람이 눈으로 확인하십시오." % len(warns))
        for w in warns:
            lines.append("  △ %s" % w)
    else:
        lines.append("[경고] 0건")
    lines.append("=" * 68)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="가치앤같이 사례 초안 검증기 v2")
    ap.add_argument("files", nargs="*",
                    help="검사할 HTML 파일 경로 (생략하면 review/ + queue/ 전체)")
    ap.add_argument("--dir", help="폴더 내 *.html 을 모두 검사 (예: automation/published)")
    ap.add_argument("--slug", help="파일명 대신 사용할 슬러그(검증용)")
    ap.add_argument("--no-meta", action="store_true", help="meta.tsv 사이드카 검사 생략")
    ap.add_argument("--strict", action="store_true",
                    help="구 게시본에도 구조 검사를 오류로 적용")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    targets = list(args.files)
    if args.dir:
        d = args.dir if os.path.isabs(args.dir) else os.path.join(REPO, args.dir)
        if os.path.isdir(d):
            targets += [os.path.join(d, f) for f in sorted(os.listdir(d))
                        if f.lower().endswith(".html")]
    if not targets and not args.files and not args.dir:
        # 인자 없이 실행 -> review/ + queue/ 의 모든 초안
        for d in DRAFT_DIRS:
            p = os.path.join(HERE, d)
            if os.path.isdir(p):
                targets += [os.path.join(p, f) for f in sorted(os.listdir(p))
                            if f.lower().endswith(".html") and ".bak" not in f]
        if targets:
            print("인자가 없어 automation/review · automation/queue 의 초안 %d건을 검사합니다."
                  % len(targets))
    if not targets:
        print("검사할 파일이 없습니다. 사용법: python validate_draft_v2.py [파일.html]")
        return 0 if (not args.files and not args.dir) else 2

    if PUB is None:
        print("경고: publish_case_v1.py 를 모듈로 불러오지 못했습니다(내장 fallback 사용).")

    bad = 0
    for t in targets:
        p = t if os.path.isabs(t) else os.path.abspath(t)
        if not os.path.exists(p):
            print("파일을 찾을 수 없습니다: %s" % t)
            bad += 1
            continue
        try:
            errs, warns, stats = validate_draft(
                p, base_slug=args.slug, check_meta=not args.no_meta,
                strict=True if args.strict else None)
        except Exception as e:
            print("검증 중 오류: %s (%s)" % (e, t))
            bad += 1
            continue
        print(report(p, errs, warns, stats))
        if errs:
            bad += 1
    print("")
    print("총 %d개 파일 검사 · 실패 %d개" % (len(targets), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("치명적 오류: %s" % exc)
        sys.exit(2)
