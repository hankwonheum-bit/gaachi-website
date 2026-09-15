#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IndexNow 색인 통보 v1  (Bing / Naver / Yandex / Seznam 공용 엔드포인트)

사용법
  python ping_indexnow_v1.py --url https://gaachi.co.kr/cases/xxx.html
  python ping_indexnow_v1.py --url A --url B          (여러 건 동시 통보)

키
  automation/config/indexnow_key_v1.txt 첫 줄의 문자열을 키로 사용한다.
  같은 이름의 <키>.txt 파일이 사이트 루트(https://gaachi.co.kr/<키>.txt)에
  배포되어 있어야 하며, 없으면 403 이 돌아온다.

참고
  - Google sitemap ping(엔드포인트 /ping?sitemap=)은 2023년 폐지되어 쓰지 않는다.
  - Google Indexing API 는 JobPosting/BroadcastEvent 전용이므로 호출하지 않는다.
    (일반 페이지에 사용하면 계정 제재 위험)
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://api.indexnow.org/indexnow"
HOST = "gaachi.co.kr"
SITE = "https://" + HOST
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "config", "indexnow_key_v1.txt")


def read_key():
    if not os.path.exists(KEY_FILE):
        print("오류: 키 파일이 없습니다 -> %s" % KEY_FILE)
        return None
    with open(KEY_FILE, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln and not ln.startswith("#"):
                return ln
    print("오류: 키 파일이 비어 있습니다 -> %s" % KEY_FILE)
    return None


def ping(urls, key, timeout=30):
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": "%s/%s.txt" % (SITE, key),
        "urlList": urls,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=data, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8",
                 "User-Agent": "gaachi-publisher/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            code, body = r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        code = e.code
        body = e.read().decode("utf-8", "replace") if e.fp else ""
    except Exception as e:
        print("IndexNow 요청 실패(네트워크): %s" % e)
        return 2

    print("IndexNow HTTP %s" % code)
    if body.strip():
        print("응답: %s" % body.strip()[:400])

    if code in (200, 202):
        print("성공: %d건 통보 완료" % len(urls))
        return 0
    if code == 403:
        print("실패(403): 키 파일 미배치")
        print("  힌트: %s/%s.txt 파일이 사이트에 배포되어 있어야 합니다." % (SITE, key))
        print("        저장소 루트에 %s.txt (내용: %s) 를 두고 push 하세요." % (key, key))
        return 3
    if code == 422:
        print("실패(422): URL 이 host 와 일치하지 않거나 키 형식 오류")
        return 4
    if code == 429:
        print("실패(429): 요청이 너무 잦습니다. 잠시 후 재시도하세요.")
        return 5
    print("실패: 예상치 못한 상태 코드 %s" % code)
    return 6


def main():
    ap = argparse.ArgumentParser(description="IndexNow 색인 통보 v1")
    ap.add_argument("--url", action="append", default=[],
                    help="통보할 전체 URL (여러 번 지정 가능)")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    urls = [u.strip() for u in args.url if u.strip()]
    if not urls:
        print("사용법: python ping_indexnow_v1.py --url https://gaachi.co.kr/cases/파일.html")
        return 1
    bad = [u for u in urls if not u.startswith(SITE)]
    if bad:
        print("오류: %s 로 시작하지 않는 URL 이 있습니다: %s" % (SITE, ", ".join(bad)))
        return 1

    key = read_key()
    if not key:
        return 1
    print("대상 %d건, 키 %s…" % (len(urls), key[:6]))
    return ping(urls, key)


if __name__ == "__main__":
    sys.exit(main())
