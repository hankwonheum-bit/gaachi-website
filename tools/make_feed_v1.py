#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_feed_v1.py — gaachi.co.kr RSS 2.0 피드 생성기

목적
----
`cases/*.html` 의 메타데이터를 읽어 저장소 루트에 `feed.xml`(RSS 2.0)을 생성한다.

왜 RSS인가
----------
78일간의 서버 로그 분석 연구에서, AI 크롤러가 RSS 피드를 519회 가져간 반면
llms.txt 는 7회에 그쳤다. 즉 AI 답변엔진에 새 콘텐츠를 알리는 실질적 경로는
llms.txt 가 아니라 RSS 피드다. (sitemap.xml 과 병행 운용)

사용법
------
    python3 tools/make_feed_v1.py            # 저장소 루트/ tools/ 어디서 실행해도 동작
    python3 tools/make_feed_v1.py --check    # 파일을 쓰지 않고 파싱 결과만 출력

입력
----
  - cases/*.html : <title>, <meta name="description">,
                   <meta property="article:published_time">,
                   <meta property="og:url"> / <link rel="canonical">
  - sitemap.xml  : <lastmod> (published_time 이 없을 때의 대체 날짜)

출력
----
  - feed.xml (RSS 2.0, 최신순)

주의: 기존 feed.xml 이 있으면 feed.xml.bak-YYYYMMDD-HHMMSS 로 백업 후 덮어쓴다.
"""

from __future__ import annotations

import argparse
import glob
import html
import io
import os
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

SITE = "https://gaachi.co.kr"
CHANNEL_TITLE = "가치앤같이 감정평가법인 — 감정평가 사례"
CHANNEL_DESC = (
    "㈜감정평가법인 가치앤같이가 실제로 수행한 감정평가 사례. "
    "상속재산 감정평가, 증여세 감정평가, 세무서 제출용 시가인정액, 취득세 시가인정액, "
    "법원 촉탁·담보·보상 평가 등 목적별 실무 사례를 공개합니다."
)
CHANNEL_LANG = "ko"
KST = timezone(timedelta(hours=9))

RFC822_DAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
RFC822_MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def repo_root() -> str:
    """이 스크립트(tools/)의 상위 디렉터리를 저장소 루트로 본다."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rfc822(dt: datetime) -> str:
    """RFC-822 날짜 문자열. locale 에 의존하지 않도록 직접 조립한다."""
    return "%s, %02d %s %04d %02d:%02d:%02d %s" % (
        RFC822_DAY[dt.weekday()], dt.day, RFC822_MON[dt.month - 1], dt.year,
        dt.hour, dt.minute, dt.second, dt.strftime("%z") or "+0000",
    )


def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def meta(src: str, attr: str, value: str) -> str | None:
    """<meta {attr}="{value}" content="..."> 에서 content 를 뽑는다(속성 순서 무관)."""
    pat = re.compile(
        r"<meta\b[^>]*\b%s\s*=\s*[\"']%s[\"'][^>]*>" % (re.escape(attr), re.escape(value)),
        re.I,
    )
    m = pat.search(src)
    if not m:
        return None
    c = re.search(r"\bcontent\s*=\s*[\"'](.*?)[\"']", m.group(0), re.I | re.S)
    return html.unescape(c.group(1)).strip() if c else None


def parse_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=KST)
        except ValueError:
            continue
    # 2026-04-23T00:00:00+09:00 형태의 콜론 포함 오프셋 보정
    fixed = re.sub(r"([+-]\d{2}):(\d{2})$", r"\1\2", raw)
    if fixed != raw:
        return parse_date(fixed)
    return None


def read_sitemap_lastmod(root: str) -> dict[str, str]:
    """{절대URL: lastmod} 매핑."""
    path = os.path.join(root, "sitemap.xml")
    out: dict[str, str] = {}
    if not os.path.exists(path):
        return out
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        print("  [warn] sitemap.xml 파싱 실패: %s" % e, file=sys.stderr)
        return out
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for url in tree.getroot().findall("sm:url", ns):
        loc = url.findtext("sm:loc", default="", namespaces=ns).strip()
        lastmod = url.findtext("sm:lastmod", default="", namespaces=ns).strip()
        if loc:
            out[loc] = lastmod
    return out


def collect_cases(root: str, lastmods: dict[str, str]) -> list[dict]:
    items: list[dict] = []
    for path in sorted(glob.glob(os.path.join(root, "cases", "*.html"))):
        name = os.path.basename(path)
        src = io.open(path, encoding="utf-8", errors="replace").read()

        m = re.search(r"<title[^>]*>(.*?)</title>", src, re.I | re.S)
        title = strip_tags(m.group(1)) if m else os.path.splitext(name)[0]

        desc = meta(src, "name", "description") or meta(src, "property", "og:description") or ""

        canon = meta(src, "property", "og:url")
        if not canon:
            lm = re.search(r"<link\b[^>]*\brel\s*=\s*[\"']canonical[\"'][^>]*>", src, re.I)
            if lm:
                hm = re.search(r"\bhref\s*=\s*[\"'](.*?)[\"']", lm.group(0), re.I)
                if hm:
                    canon = hm.group(1).strip()
        if not canon:
            canon = "%s/cases/%s" % (SITE, name)

        dt = parse_date(meta(src, "property", "article:published_time"))
        src_label = "article:published_time"
        if dt is None:
            dt = parse_date(lastmods.get(canon))
            src_label = "sitemap lastmod"
        if dt is None:
            dt = datetime.fromtimestamp(os.path.getmtime(path), tz=KST)
            src_label = "file mtime"

        items.append({
            "file": name, "title": title, "link": canon,
            "desc": desc, "date": dt, "date_src": src_label,
        })

    items.sort(key=lambda d: d["date"], reverse=True)  # 최신순
    return items


def esc(s: str) -> str:
    return html.escape(s, quote=False)


def cdata(s: str) -> str:
    return "<![CDATA[%s]]>" % s.replace("]]>", "]]&gt;")


def build_rss(items: list[dict], now: datetime) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8"?>']
    out.append('<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">')
    out.append("  <channel>")
    out.append("    <title>%s</title>" % esc(CHANNEL_TITLE))
    out.append("    <link>%s/#cases</link>" % SITE)
    out.append("    <description>%s</description>" % esc(CHANNEL_DESC))
    out.append("    <language>%s</language>" % CHANNEL_LANG)
    out.append('    <atom:link href="%s/feed.xml" rel="self" type="application/rss+xml" />' % SITE)
    out.append("    <lastBuildDate>%s</lastBuildDate>" % rfc822(items[0]["date"] if items else now))
    out.append("    <generator>tools/make_feed_v1.py</generator>")
    out.append("    <docs>https://www.rssboard.org/rss-specification</docs>")
    out.append("    <ttl>1440</ttl>")
    for it in items:
        out.append("    <item>")
        out.append("      <title>%s</title>" % esc(it["title"]))
        out.append("      <link>%s</link>" % esc(it["link"]))
        out.append('      <guid isPermaLink="true">%s</guid>' % esc(it["link"]))
        out.append("      <pubDate>%s</pubDate>" % rfc822(it["date"]))
        out.append("      <description>%s</description>" % cdata(it["desc"]))
        out.append("    </item>")
    out.append("  </channel>")
    out.append("</rss>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="gaachi.co.kr RSS 2.0 피드 생성")
    ap.add_argument("--check", action="store_true", help="파일을 쓰지 않고 파싱 결과만 출력")
    args = ap.parse_args()

    root = repo_root()
    now = datetime.now(KST)
    lastmods = read_sitemap_lastmod(root)
    items = collect_cases(root, lastmods)

    if not items:
        print("[error] cases/*.html 을 찾지 못했습니다.", file=sys.stderr)
        return 1

    print("사례 %d건 수집 (최신순)" % len(items))
    for it in items:
        print("  %s  %s  [%s]" % (it["date"].strftime("%Y-%m-%d"), it["file"], it["date_src"]))

    xml = build_rss(items, now)

    # 생성물 자체 검증
    ET.fromstring(xml.encode("utf-8"))

    if args.check:
        print("\n--check 모드: feed.xml 을 쓰지 않았습니다. (XML 파싱 OK)")
        return 0

    out_path = os.path.join(root, "feed.xml")
    if os.path.exists(out_path):
        bak = out_path + datetime.now().strftime(".bak-%Y%m%d-%H%M%S")
        shutil.copy2(out_path, bak)
        print("기존 feed.xml 백업 -> %s" % os.path.basename(bak))

    io.open(out_path, "w", encoding="utf-8", newline="\n").write(xml)
    print("생성 완료: %s (%d bytes)" % (out_path, os.path.getsize(out_path)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
