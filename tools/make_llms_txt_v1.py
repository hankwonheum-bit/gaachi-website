#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_llms_txt_v1.py — gaachi.co.kr llms.txt 생성기

성격: 낮은 확신도(low-confidence) / 보험성 파일.
     llms.txt 는 아직 어떤 주요 AI 업체도 공식 지원을 선언하지 않은 제안 표준이다.
     78일 서버 로그 연구 기준 AI 크롤러의 RSS 피드 접근 519회 vs llms.txt 7회.
     → 실효성은 feed.xml / sitemap.xml 이 담당하고, 이 파일은 표준이 채택될 경우를
       대비한 저비용 보험으로만 유지한다. 유지비 이상을 투자하지 말 것.

사용법
------
    python3 tools/make_llms_txt_v1.py
    python3 tools/make_llms_txt_v1.py --check   # 파일을 쓰지 않고 출력만 확인

입력: cases/*.html (<title>, meta description, og:url/canonical, article:published_time)
출력: llms.txt (저장소 루트)

참고: llms-full.txt 는 의도적으로 만들지 않는다(중복 콘텐츠 및 유지비 대비 효익 없음).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import html
import io
import os
import re
import shutil
import sys

SITE = "https://gaachi.co.kr"
FIRM = "㈜감정평가법인 가치앤같이"

SUMMARY = (
    "서울 서초구 소재 감정평가법인. 상속재산·증여세 신고용 감정평가, 세무서 제출용 "
    "시가인정액, 취득세 시가인정액, 특수관계인 거래, 법원 촉탁, 담보·경매, 공익사업 보상, "
    "재개발 종전자산, 무형자산 및 기계기구 감정평가를 수행합니다. "
    "실제 수행한 감정평가 사례의 기준시점·적용 감정평가방법·산출 근거·최종 평가액을 "
    "사례별로 공개하고 있습니다."
)

SERVICES = [
    ("상속재산 감정평가", "상속세 신고 목적. 상속개시일 전후 6개월 이내 기준시점으로 시가를 산정합니다."),
    ("증여세 감정평가", "증여세 신고 목적. 증여일 전 6개월 ~ 후 3개월 이내 기준시점 시가 산정."),
    ("세무서 제출용 시가인정액", "「상속세 및 증여세법」상 시가로 인정받기 위한 감정평가서 작성·제출."),
    ("취득세 시가인정액", "「지방세법」상 취득세 과세표준이 되는 시가인정액 산정."),
    ("특수관계인 거래 감정평가", "부당행위계산부인 리스크 대응을 위한 적정 거래가격 산정."),
    ("법원 촉탁 감정평가", "경매, 이혼 재산분할, 상속 분쟁 등 법원 촉탁 사건."),
    ("담보 감정평가", "금융기관 대출 담보물 평가."),
    ("경매 감정평가", "경매 목적물의 최저매각가격 산정 기초 평가."),
    ("공익사업 보상평가", "공익사업을 위한 토지 등의 취득 및 보상에 관한 법률에 따른 보상평가."),
    ("재개발 종전자산 감정평가", "정비사업 종전자산 평가 및 분담금 산정 기초 자료."),
    ("무형자산 감정평가", "영업권·상표권 등 무형자산 가치평가."),
    ("기계기구 감정평가", "공장 기계기구 및 설비 평가."),
]

CONTACT = [
    ("상호", FIRM + " (별칭: 가치앤같이 감정평가법인)"),
    ("대표자", "김지광"),
    ("주소", "서울특별시 서초구 강남대로 86, 5층 501호 (양재동, 가람빌딩)"),
    ("전화", "02-572-1900"),
    ("팩스", "02-572-1901"),
    ("사업자등록번호", "722-81-02543"),
    ("문의", SITE + "/#contact"),
]


def repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def meta(src: str, attr: str, value: str) -> str | None:
    pat = re.compile(
        r"<meta\b[^>]*\b%s\s*=\s*[\"']%s[\"'][^>]*>" % (re.escape(attr), re.escape(value)),
        re.I,
    )
    m = pat.search(src)
    if not m:
        return None
    c = re.search(r"\bcontent\s*=\s*[\"'](.*?)[\"']", m.group(0), re.I | re.S)
    return html.unescape(c.group(1)).strip() if c else None


def clean_title(t: str) -> str:
    """'… — 가치앤같이 감정평가법인' 같은 사이트명 접미사를 제거."""
    for sep in (" — ", " – ", " - ", " | "):
        if sep in t:
            head, tail = t.rsplit(sep, 1)
            if "가치앤같이" in tail and head.strip():
                return head.strip()
    return t.strip()


def one_line(desc: str, limit: int = 110) -> str:
    """메타 설명에서 한 줄 요약을 뽑는다. 첫 1~2문장, 사이트명 꼬리는 제거."""
    desc = re.sub(r"\s*가치앤같이 감정평가법인\.?\s*$", "", desc.strip())
    parts = [p.strip() for p in re.split(r"(?<=\.)\s+", desc) if p.strip()]
    out = ""
    for p in parts:
        if out and len(out) + len(p) + 1 > limit:
            break
        out = (out + " " + p).strip()
    if not out:
        out = desc[:limit]
    if len(out) > limit + 20:
        out = out[:limit].rstrip() + "…"
    return out.rstrip(".") + "."


def collect_cases(root: str) -> list[dict]:
    items = []
    for path in sorted(glob.glob(os.path.join(root, "cases", "*.html"))):
        name = os.path.basename(path)
        src = io.open(path, encoding="utf-8", errors="replace").read()

        m = re.search(r"<title[^>]*>(.*?)</title>", src, re.I | re.S)
        title = clean_title(strip_tags(m.group(1))) if m else os.path.splitext(name)[0]

        desc = meta(src, "name", "description") or meta(src, "property", "og:description") or ""

        url = meta(src, "property", "og:url")
        if not url:
            lm = re.search(r"<link\b[^>]*\brel\s*=\s*[\"']canonical[\"'][^>]*>", src, re.I)
            if lm:
                hm = re.search(r"\bhref\s*=\s*[\"'](.*?)[\"']", lm.group(0), re.I)
                if hm:
                    url = hm.group(1).strip()
        if not url:
            url = "%s/cases/%s" % (SITE, name)

        pub = meta(src, "property", "article:published_time") or ""
        sort_key = pub[:10] or _dt.datetime.fromtimestamp(
            os.path.getmtime(path)).strftime("%Y-%m-%d")

        items.append({"title": title, "url": url,
                      "summary": one_line(desc), "sort": sort_key})

    items.sort(key=lambda d: d["sort"], reverse=True)
    return items


def build(items: list[dict]) -> str:
    L: list[str] = []
    L.append("# %s" % FIRM)
    L.append("")
    L.append("> %s" % SUMMARY)
    L.append("")
    L.append("## 감정평가 사례")
    L.append("")
    for it in items:
        L.append("- [%s](%s): %s" % (it["title"], it["url"], it["summary"]))
    L.append("")
    L.append("## 서비스")
    L.append("")
    for name, desc in SERVICES:
        L.append("- **%s**: %s" % (name, desc))
    L.append("")
    L.append("## 문의")
    L.append("")
    for k, v in CONTACT:
        L.append("- **%s**: %s" % (k, v))
    L.append("")
    L.append("---")
    L.append("")
    L.append("- 전체 페이지 목록: %s/sitemap.xml" % SITE)
    L.append("- 신규 사례 RSS 피드: %s/feed.xml" % SITE)
    L.append("- 최종 갱신: %s (tools/make_llms_txt_v1.py 로 자동 생성)"
             % _dt.date.today().isoformat())
    L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="gaachi.co.kr llms.txt 생성")
    ap.add_argument("--check", action="store_true", help="파일을 쓰지 않고 출력만 확인")
    args = ap.parse_args()

    root = repo_root()
    items = collect_cases(root)
    if not items:
        print("[error] cases/*.html 을 찾지 못했습니다.", file=sys.stderr)
        return 1

    text = build(items)

    if args.check:
        sys.stdout.write(text)
        print("\n[--check] 사례 %d건. 파일을 쓰지 않았습니다." % len(items))
        return 0

    out_path = os.path.join(root, "llms.txt")
    if os.path.exists(out_path):
        bak = out_path + _dt.datetime.now().strftime(".bak-%Y%m%d-%H%M%S")
        shutil.copy2(out_path, bak)
        print("기존 llms.txt 백업 -> %s" % os.path.basename(bak))

    io.open(out_path, "w", encoding="utf-8", newline="\n").write(text)
    print("생성 완료: %s (사례 %d건, %d bytes)"
          % (out_path, len(items), os.path.getsize(out_path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
