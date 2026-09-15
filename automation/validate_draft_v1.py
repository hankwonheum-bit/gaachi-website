#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 감정평가법인 — 초안(draft) 검증기 v1
================================================
`automation/publish_case_v1.py` 의 validate() 게이트를 그대로 재사용하고,
초안 단계에서만 잡을 수 있는 항목을 추가로 검사한다.

게시 스크립트와 규칙이 갈라지지 않도록 publish_case_v1.py 를 직접 import 한다
(import 실패 시에만 내장 fallback 을 쓰고, 그 사실을 경고로 알린다).

추가 게이트
  - 미치환 토큰 {{ }} 0건
  - <h1> 정확히 1개 / <h2> 3개 이상 / <h3> 1개 이상
  - JSON-LD 3블록 전부 파싱 + FAQPage 질문 == 본문 <h3> FAQ 질문 (글자 단위)
  - canonical == og:url == JSON-LD mainEntityOfPage.@id
  - 숨김 키워드 스팬(font-size:1px / color:var(--bg)) 0건
  - 수수료 금액 표현 0건 / 인명 패턴 0건 / <\!-- 오타 0건
  - meta.tsv 사이드카 존재 + 12개 키 전부 존재

사용법
  python validate_draft_v1.py automation/review/011_gangnam-daechi-2026.html
  python validate_draft_v1.py --dir automation/review
  python validate_draft_v1.py templates/케이스_v2_예시.html --slug gangdong-seongnae-geunsaeng-v2-2025 --no-meta

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
    if '<html lang="ko">' not in html:
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
    want = "%s/cases/%s.html" % (SITE, base_slug)
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
    for m in re.finditer(r'href=["\']/cases/([a-z0-9\-]+)\.html["\']', html):
        p = os.path.join(REPO, "cases", m.group(1) + ".html")
        if not os.path.exists(p):
            warns.append("관련 사례 링크 대상 파일이 없습니다: /cases/%s.html" % m.group(1))
    firm = html.count("㈜감정평가법인 가치앤같이")
    if firm < 6:
        warns.append("법인 정식명칭 '㈜감정평가법인 가치앤같이' 가 %d회입니다(6회 이상 권장)." % firm)
    for bad in ("본 법인", "당사", "저희 법인"):
        if bad in html:
            warns.append("모호한 자칭 '%s' 사용 — 법인 정식명칭으로 바꾸십시오." % bad)

    return errs, warns, dict(h1=h1, h2=h2, h3=h3, jsonld=len(blocks),
                             faq=len(hq), canonical=canon)


# ---------------------------------------------------------------- 공개 API
def validate_draft(html_path, base_slug=None, check_meta=True):
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
    ap = argparse.ArgumentParser(description="가치앤같이 사례 초안 검증기 v1")
    ap.add_argument("files", nargs="*", help="검사할 HTML 파일 경로")
    ap.add_argument("--dir", help="폴더 내 *.html 을 모두 검사 (예: automation/review)")
    ap.add_argument("--slug", help="파일명 대신 사용할 슬러그(검증용)")
    ap.add_argument("--no-meta", action="store_true", help="meta.tsv 사이드카 검사 생략")
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
    if not targets:
        print("검사할 파일이 없습니다. 사용법: python validate_draft_v1.py <파일.html>")
        return 2

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
                p, base_slug=args.slug, check_meta=not args.no_meta)
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
