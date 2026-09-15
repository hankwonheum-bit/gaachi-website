#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 감정평가법인 — 사례 자동 게시 엔진 v1
=================================================
automation/queue/ 에 쌓아 둔 사례 HTML 중 가장 오래된(파일명 순) 1건을
검증 -> cases/ 복사 -> sitemap.xml / index.html 갱신 -> git commit/push ->
IndexNow 통보 순서로 하루 1건만 게시한다.

원칙
 - 기존 콘텐츠 파일은 절대 삭제/덮어쓰기 하지 않는다.
 - index.html / sitemap.xml 수정 전 타임스탬프 .bak 백업을 먼저 만든다.
 - cases/ 안에 동일 파일이 있으면 -v2, -v3 로 새 파일을 만든다.
 - 같은 날 두 번 실행해도 안전하다(멱등).

사용법
  python publish_case_v1.py            # 실제 게시
  python publish_case_v1.py --dry-run  # 아무것도 쓰지 않고 시뮬레이션
  python publish_case_v1.py --no-push  # 커밋까지만, push 안 함
  python publish_case_v1.py --force    # 오늘 이미 게시했어도 1건 더 게시
"""
import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 기본 설정
KST = timezone(timedelta(hours=9))
SITE = "https://gaachi.co.kr"
AUTO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(AUTO_DIR)

QUEUE_DIR = os.path.join(AUTO_DIR, "queue")
PUBLISHED_DIR = os.path.join(AUTO_DIR, "published")
REJECTED_DIR = os.path.join(AUTO_DIR, "rejected")
LOGS_DIR = os.path.join(AUTO_DIR, "logs")
STATE_DIR = os.path.join(AUTO_DIR, "state")
CONFIG_DIR = os.path.join(AUTO_DIR, "config")

LOG_TSV = os.path.join(STATE_DIR, "published_log.tsv")
LOG_HEADER = "date_kst\tfilename\turl\tcommit_sha\tresult"

BLOCKLIST_FILE = os.path.join(CONFIG_DIR, "blocklist_names_v1.txt")
FORBIDDEN_FILE = os.path.join(CONFIG_DIR, "forbidden_phrases_v1.txt")
INDEXNOW_KEY_FILE = os.path.join(CONFIG_DIR, "indexnow_key_v1.txt")
PING_SCRIPT = os.path.join(AUTO_DIR, "ping_indexnow_v1.py")

# index.html 삽입 기준점(앵커):
#   cases-grid(<div class="cases-grid" id="casesGrid">)의 닫는 </div> 와
#   그 바로 다음 형제인 <div class="no-result" id="noResult"> 의 조합.
#   이 조합은 index.html 전체에서 정확히 1회만 등장하므로 <div> 균형을
#   직접 세는 것보다 훨씬 안전하다. (없으면 아래 fallback 사용)
GRID_END_ANCHOR = '    </div>\n    <div class="no-result" id="noResult">'

FIRM_LINE = ('          <p>감정평가법인: 가치앤같이 감정평가법인 '
             '(서울특별시 서초구 강남대로 86, 5층, 양재동 가람빌딩)</p>')
TEL_LINE = '          <p>문의: (02) 572-1900</p>'

_RUNLOG = []


# ---------------------------------------------------------------- 유틸
def now_kst():
    return datetime.now(KST)


def today_dash(d=None):
    return (d or now_kst()).strftime("%Y-%m-%d")


def today_dot(d=None):
    return (d or now_kst()).strftime("%Y. %m. %d")


def stamp(d=None):
    return (d or now_kst()).strftime("%Y%m%d-%H%M%S")


def log(msg, dry=False):
    line = "[%s] %s" % (now_kst().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    _RUNLOG.append(line)


def flush_runlog(dry=False):
    if dry or not _RUNLOG:
        return
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        p = os.path.join(LOGS_DIR, "publish-%s.log" % now_kst().strftime("%Y%m%d"))
        with io.open(p, "a", encoding="utf-8") as f:
            f.write("\n".join(_RUNLOG) + "\n")
    except Exception as e:  # 로그 실패로 전체가 죽지 않게
        print("로그 기록 실패: %s" % e)


def read_text(path):
    with io.open(path, "r", encoding="utf-8", errors="strict") as f:
        return f.read()


def write_text(path, data):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def read_lines_cfg(path):
    """설정 파일을 읽어 (# 주석/빈 줄 제외) 리스트로."""
    if not os.path.exists(path):
        return []
    out = []
    for ln in read_text(path).splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            out.append(ln)
    return out


def backup(path, dry=False):
    """수정 전 타임스탬프 백업. 반환: 백업 경로"""
    bak = "%s.bak-%s" % (path, stamp())
    if dry:
        log("[DRY] 백업 예정: %s" % os.path.basename(bak), dry)
        return bak
    shutil.copy2(path, bak)
    log("백업 생성: %s" % os.path.basename(bak))
    return bak


def git(args, check=False):
    p = subprocess.run(["git"] + args, cwd=REPO, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace").strip()
    if check and p.returncode != 0:
        raise RuntimeError("git %s 실패: %s" % (" ".join(args), out))
    return p.returncode, out


# ---------------------------------------------------------------- 게시 로그
def ensure_log():
    os.makedirs(STATE_DIR, exist_ok=True)
    if not os.path.exists(LOG_TSV):
        write_text(LOG_TSV, LOG_HEADER + "\n")


def log_rows():
    if not os.path.exists(LOG_TSV):
        return []
    rows = []
    for ln in read_text(LOG_TSV).splitlines():
        if not ln.strip() or ln.startswith("date_kst\t"):
            continue
        rows.append(ln.split("\t"))
    return rows


def already_published_today():
    t = today_dash()
    for r in log_rows():
        if len(r) >= 5 and r[0] == t and r[4] == "OK":
            return r
    return None


def append_log_row(date_kst, filename, url, sha, result, dry=False):
    row = "\t".join([date_kst, filename, url, sha or "-", result])
    if dry:
        log("[DRY] 게시로그 추가 예정: %s" % row, dry)
        return
    ensure_log()
    with io.open(LOG_TSV, "a", encoding="utf-8") as f:
        f.write(row + "\n")
    log("게시로그 추가: %s" % row)


# ---------------------------------------------------------------- 검증
NAME_RE = re.compile(r"(의뢰인|소유자|신청인)\s*[:：]\s*[가-힣]{2,4}")
NIM_RE = re.compile(r"(?<![가-힣])[가-힣]{2,3}님")


def validate(html, base_slug):
    """반환: (errors, warnings)"""
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

    # JSON-LD 3종
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.S | re.I)
    types = set()
    for i, b in enumerate(blocks, 1):
        try:
            data = json.loads(b.strip())
        except Exception as e:
            errs.append("JSON-LD 블록 %d 파싱 실패: %s" % (i, e))
            continue
        for node in (data if isinstance(data, list) else [data]):
            if isinstance(node, dict):
                if "@graph" in node and isinstance(node["@graph"], list):
                    for g in node["@graph"]:
                        if isinstance(g, dict) and g.get("@type"):
                            types.add(str(g.get("@type")))
                if node.get("@type"):
                    types.add(str(node.get("@type")))
    for need in ("Article", "FAQPage", "BreadcrumbList"):
        if need not in types:
            errs.append("JSON-LD에 %s 블록이 없습니다. (발견: %s)"
                        % (need, ", ".join(sorted(types)) or "없음"))

    # canonical
    m = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]*>', html, re.I)
    if not m:
        errs.append('<link rel="canonical"> 태그가 없습니다.')
    else:
        hm = re.search(r'href=["\']([^"\']+)["\']', m.group(0))
        want = "%s/cases/%s.html" % (SITE, base_slug)
        if not hm:
            errs.append("canonical 태그에 href가 없습니다.")
        elif hm.group(1).rstrip("/") != want:
            errs.append("canonical URL 불일치: %s (기대값 %s)" % (hm.group(1), want))

    # 개인정보 게이트
    m = NAME_RE.search(html)
    if m:
        errs.append("개인정보 의심 패턴 발견: '%s'" % m.group(0))
    for name in read_lines_cfg(BLOCKLIST_FILE):
        if name in html:
            errs.append("차단 인명 발견: '%s'" % name)
    nim = set(NIM_RE.findall(html))
    if nim:
        warns.append("'○○님' 형태 문자열 확인 필요: %s" % ", ".join(sorted(nim))[:200])

    # 금지 문구
    for ph in read_lines_cfg(FORBIDDEN_FILE):
        if ph in html:
            errs.append("금지 문구 발견: '%s'" % ph)

    # 주석 오타
    if "<\\!--" in html:
        errs.append("HTML 주석 오타 '<\\!--' 가 있습니다.")

    return errs, warns


def reject(src, errs, dry=False):
    os.makedirs(REJECTED_DIR, exist_ok=True)
    base = os.path.basename(src)
    dst = os.path.join(REJECTED_DIR, base)
    reason = os.path.join(REJECTED_DIR, base + ".reason.txt")
    body = ("거부 시각: %s\n원본: %s\n\n[거부 사유]\n%s\n"
            % (now_kst().isoformat(), base,
               "\n".join("- " + e for e in errs)))
    if dry:
        log("[DRY] 거부 처리 예정 -> automation/rejected/%s" % base, dry)
        return
    if os.path.exists(dst):  # 덮어쓰기 금지
        dst = os.path.join(REJECTED_DIR, "%s-%s" % (stamp(), base))
        reason = dst + ".reason.txt"
    shutil.move(src, dst)
    meta = find_meta(src)
    if meta and os.path.exists(meta):
        shutil.move(meta, os.path.join(REJECTED_DIR, os.path.basename(meta)))
    write_text(reason, body)
    log("거부 처리 완료 -> automation/rejected/%s" % os.path.basename(dst))


# ---------------------------------------------------------------- 메타
META_KEYS = ("num", "cat", "tag", "title_line1", "title_line2", "purpose",
             "sijae", "gijun", "method", "value_text", "seo_h2", "seo_p",
             "region", "object", "purpose_short")


def find_meta(html_path):
    stem = os.path.splitext(html_path)[0]
    for cand in (stem + ".meta.tsv", html_path + ".meta.tsv"):
        if os.path.exists(cand):
            return cand
    return stem + ".meta.tsv"


def read_meta(path):
    if not os.path.exists(path):
        return {}
    meta = {}
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


def derive_meta_from_html(html):
    """meta 파일이 없을 때 <title>/description 으로 최소한만 채운다."""
    out = {}
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        title = title.split("|")[0].strip()
        out["seo_h2"] = title
        parts = title.split(" ", 1)
        out["title_line1"] = parts[0]
        out["title_line2"] = parts[1] if len(parts) > 1 else "감정평가"
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)',
                  html, re.I)
    if m:
        out["seo_p"] = re.sub(r"\s+", " ", m.group(1)).strip()
    return out


# ---------------------------------------------------------------- sitemap
def update_sitemap(path, url, dry=False):
    xml = read_text(path)
    if "<loc>%s</loc>" % url in xml:
        log("sitemap.xml 에 이미 등록된 URL 입니다. 건너뜁니다.")
        return False
    backup(path, dry)

    entry = ("  <url>\n"
             "    <loc>%s</loc>\n"
             "    <lastmod>%s</lastmod>\n"
             "    <changefreq>monthly</changefreq>\n"
             "    <priority>0.8</priority>\n"
             "  </url>\n") % (url, today_dash())

    idx = xml.rfind("</urlset>")
    if idx == -1:
        raise RuntimeError("sitemap.xml 에 </urlset> 이 없습니다.")
    new = xml[:idx] + entry + xml[idx:]

    # 홈 URL lastmod 갱신 (기존 항목 삭제 없이 날짜만 교체)
    new, n = re.subn(
        r"(<loc>%s/</loc>\s*<lastmod>)[^<]*(</lastmod>)" % re.escape(SITE),
        r"\g<1>%s\g<2>" % today_dash(), new, count=1)
    if n == 0:
        log("경고: sitemap.xml 홈 <loc> 항목을 찾지 못해 lastmod 를 갱신하지 못했습니다.")

    if dry:
        log("[DRY] sitemap.xml 에 <url> 1건 추가 예정: %s" % url, dry)
        return True
    write_text(path, new)
    log("sitemap.xml 갱신 완료: %s" % url)
    return True


# ---------------------------------------------------------------- index.html
def next_case_num(html):
    nums = [int(x) for x in re.findall(r'class="case-num">\s*(\d+)\s*<', html)]
    return "%02d" % ((max(nums) + 1) if nums else 1)


def build_card(meta, slug, num):
    cat = meta.get("cat") or "상속·증여"
    tag = meta.get("tag") or ("%s 감정평가" % cat)
    t1 = meta.get("title_line1") or "감정평가 사례"
    t2 = meta.get("title_line2") or "감정평가"
    purpose = meta.get("purpose") or "세무서 제출 목적"
    sijae = meta.get("sijae") or "-"
    gijun = meta.get("gijun") or "-"
    method = meta.get("method") or "거래사례비교법"
    value_text = meta.get("value_text") or "-"
    seo_h2 = meta.get("seo_h2") or ("%s %s 감정평가 사례" % (t1, t2))
    seo_p = meta.get("seo_p") or ""
    ps = [p.strip() for p in seo_p.split("||") if p.strip()]
    if not ps:
        ps = ["가치앤같이 감정평가법인이 수행한 %s %s 감정평가 사례입니다." % (t1, t2)]
    p_lines = "\n".join("          <p>%s</p>" % p for p in ps)

    return (
        '      <div class="case-card fade-up" data-cat="%s" onclick="location.href=\'/cases/%s.html\'">\n'
        '        <div class="case-card-head">\n'
        '          <div class="case-num">%s</div>\n'
        '          <div class="case-tag">%s</div>\n'
        '          <div class="case-title">%s<br>%s</div>\n'
        '          <div class="case-purpose">%s</div>\n'
        '        </div>\n'
        '        <div class="case-card-body">\n'
        '          <div class="case-meta-row">\n'
        '            <div class="case-meta"><div class="case-meta-label">소재지</div><div class="case-meta-val">%s</div></div>\n'
        '            <div class="case-meta"><div class="case-meta-label">기준시점</div><div class="case-meta-val">%s</div></div>\n'
        '            <div class="case-meta"><div class="case-meta-label">평가방법</div><div class="case-meta-val">%s</div></div>\n'
        '          </div>\n'
        '          <div class="case-value-row">\n'
        '            <div><div class="case-value-label">최종 감정평가액</div><div class="case-value-num">%s</div></div>\n'
        '            <div class="case-more">상세 보기 →</div>\n'
        '          </div>\n'
        '          <div class="case-date-badge">%s 업데이트</div>\n'
        '        </div>\n'
        '        <!-- SEO: 크롤러용 상세 내용 -->\n'
        '        <div class="seo-content">\n'
        '          <h2>%s</h2>\n'
        '%s\n'
        '%s\n'
        '%s\n'
        '        </div>\n'
        '      </div>'
        % (cat, slug, num, tag, t1, t2, purpose, sijae, gijun, method,
           value_text, today_dot(), seo_h2, p_lines, FIRM_LINE, TEL_LINE))


def _balanced_block_end(html, start):
    """start(=<div ...) 위치부터 균형 잡힌 </div> 의 끝 인덱스를 반환."""
    depth = 0
    for m in re.finditer(r"<div\b|</div>", html[start:]):
        if m.group(0) == "</div>":
            depth -= 1
            if depth == 0:
                return start + m.end()
        else:
            depth += 1
    return -1


def update_index(path, card, slug, dry=False):
    html = read_text(path)
    if "location.href='/cases/%s.html'" % slug in html:
        log("index.html 에 이미 동일 사례 카드가 있습니다. 건너뜁니다.")
        return False
    backup(path, dry)

    if GRID_END_ANCHOR in html:
        anchor = "cases-grid 닫힘 + no-result 형제 마커"
        new = html.replace(GRID_END_ANCHOR,
                           "\n" + card + "\n" + GRID_END_ANCHOR, 1)
    else:
        # fallback: 마지막 case-card 블록을 <div> 균형으로 찾아 그 뒤에 삽입
        last = html.rfind('<div class="case-card')
        if last == -1:
            raise RuntimeError("index.html 에서 case-card 를 찾지 못했습니다.")
        end = _balanced_block_end(html, last)
        if end == -1:
            raise RuntimeError("index.html case-card 블록의 끝을 찾지 못했습니다.")
        anchor = "마지막 case-card 블록(<div> 균형 계산) 직후"
        new = html[:end] + "\n\n" + card + html[end:]

    log("index.html 삽입 기준점: %s" % anchor)
    if dry:
        log("[DRY] index.html 에 case-card 1건 추가 예정 (%d bytes)" % len(card), dry)
        return True
    write_text(path, new)
    log("index.html 갱신 완료 (카드 추가)")
    return True


# ---------------------------------------------------------------- IndexNow
def ping_indexnow(url, dry=False):
    if dry:
        log("[DRY] IndexNow 통보 예정: %s" % url, dry)
        return
    if not os.path.exists(PING_SCRIPT):
        log("경고: ping_indexnow_v1.py 가 없어 IndexNow 통보를 건너뜁니다.")
        return
    try:
        p = subprocess.run([sys.executable, PING_SCRIPT, "--url", url],
                           cwd=REPO, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60)
        for ln in p.stdout.decode("utf-8", "replace").splitlines():
            log("  IndexNow| " + ln)
    except Exception as e:
        log("경고: IndexNow 통보 실패: %s" % e)


def ensure_indexnow_keyfile(dry=False):
    """사이트 루트에 <key>.txt 가 없으면 새로 만든다(기존 파일은 건드리지 않음)."""
    try:
        key = read_text(INDEXNOW_KEY_FILE).strip().splitlines()[0].strip()
    except Exception:
        return None
    if not re.fullmatch(r"[A-Za-z0-9\-]{8,128}", key or ""):
        return None
    dst = os.path.join(REPO, key + ".txt")
    if os.path.exists(dst):
        return dst
    if dry:
        log("[DRY] IndexNow 키 파일 생성 예정: /%s.txt" % key, dry)
        return dst
    write_text(dst, key + "\n")
    log("IndexNow 키 파일 생성: /%s.txt (커밋에 포함됨)" % key)
    return dst


# ---------------------------------------------------------------- git
def git_publish(paths, msg, no_push=False, dry=False):
    """반환: (commit_sha, result) result in {OK, PUSH_FAIL, NO_CHANGE}"""
    if dry:
        log("[DRY] git add: %s" % ", ".join(paths), dry)
        log("[DRY] git commit -m \"%s\"" % msg, dry)
        log("[DRY] git push origin main", dry)
        return "-", "OK"

    for p in paths:
        git(["add", "-A", "--", p])
    rc, _ = git(["diff", "--cached", "--quiet"])
    if rc == 0:
        log("스테이지된 변경이 없어 커밋을 건너뜁니다.")
        _, sha = git(["rev-parse", "--short", "HEAD"])
        return sha, "NO_CHANGE"

    rc, out = git(["commit", "-m", msg])
    if rc != 0:
        log("커밋 실패: %s" % out)
        return "-", "COMMIT_FAIL"
    _, sha = git(["rev-parse", "--short", "HEAD"])
    log("커밋 완료 %s : %s" % (sha, msg))

    if no_push:
        log("--no-push 지정으로 push 생략")
        return sha, "OK"

    rc, out = git(["push", "origin", "main"])
    if rc == 0:
        log("push 완료 (Cloudflare Pages 자동 배포 시작)")
        return sha, "OK"
    log("push 실패, git pull --rebase 후 1회 재시도합니다: %s" % out.splitlines()[-1:])
    rc2, out2 = git(["pull", "--rebase", "origin", "main"])
    if rc2 != 0:
        log("pull --rebase 실패: %s" % out2)
        log("커밋은 로컬에 남겨 둡니다(리셋하지 않음). 수동 확인 필요.")
        return sha, "PUSH_FAIL"
    rc3, out3 = git(["push", "origin", "main"])
    if rc3 == 0:
        log("재시도 push 완료")
        return sha, "OK"
    log("재시도 push 실패: %s" % out3)
    log("커밋은 로컬에 남겨 둡니다(리셋하지 않음). 수동 확인 필요.")
    return sha, "PUSH_FAIL"


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="가치앤같이 사례 자동 게시 v1")
    ap.add_argument("--dry-run", action="store_true", help="파일/깃 변경 없이 시뮬레이션")
    ap.add_argument("--no-push", action="store_true", help="커밋까지만 하고 push 안 함")
    ap.add_argument("--force", action="store_true", help="오늘 이미 게시했어도 진행")
    ap.add_argument("--queue-dir", default=QUEUE_DIR, help="대기열 폴더 경로")
    args = ap.parse_args()
    dry = args.dry_run

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    log("==== 사례 자동 게시 시작 (KST %s)%s ===="
        % (now_kst().strftime("%Y-%m-%d %H:%M:%S"), " [DRY-RUN]" if dry else ""))
    log("저장소: %s" % REPO)

    for d in (args.queue_dir, PUBLISHED_DIR, REJECTED_DIR, LOGS_DIR, STATE_DIR):
        if not dry:
            os.makedirs(d, exist_ok=True)
    if not dry:
        ensure_log()

    # 1) 멱등 체크
    done = already_published_today()
    if done and not args.force:
        log("오늘은 이미 게시됨 (%s / %s)" % (done[1], done[2]))
        return 0

    # 2) 대기열에서 가장 오래된(파일명 순) 1건
    try:
        files = sorted(f for f in os.listdir(args.queue_dir)
                       if f.lower().endswith(".html"))
    except FileNotFoundError:
        files = []
    if not files:
        log("대기열 비어있음")
        return 0
    qname = files[0]
    qpath = os.path.join(args.queue_dir, qname)
    log("대상 파일: %s" % qname)

    # 3) slug 도출 (NNN_slug.html -> slug)
    stem = os.path.splitext(qname)[0]
    base_slug = stem.split("_", 1)[1] if re.match(r"^\d+_", stem) else stem
    seq = stem.split("_", 1)[0] if re.match(r"^\d+_", stem) else ""

    try:
        html = read_text(qpath)
    except UnicodeDecodeError as e:
        log("UTF-8 디코딩 실패: %s" % e)
        reject(qpath, ["UTF-8 로 읽을 수 없습니다: %s" % e], dry)
        append_log_row(today_dash(), qname, "-", "-", "REJECTED", dry)
        return 0

    # 4) 검증 (하드 게이트)
    errs, warns = validate(html, base_slug)
    for w in warns:
        log("경고: %s" % w)
    if errs:
        log("검증 실패 %d건 — 게시를 거부합니다." % len(errs))
        for e in errs:
            log("  - %s" % e)
        reject(qpath, errs, dry)
        append_log_row(today_dash(), qname, "-", "-", "REJECTED", dry)
        return 0
    log("검증 통과 (오류 0건, 경고 %d건)" % len(warns))

    # 5) 최종 slug 결정 (덮어쓰기 금지 -> -v2, -v3 …)
    cases_dir = os.path.join(REPO, "cases")
    final_slug = base_slug
    v = 1
    while os.path.exists(os.path.join(cases_dir, final_slug + ".html")):
        v += 1
        final_slug = "%s-v%d" % (base_slug, v)
    if final_slug != base_slug:
        log("cases/%s.html 이 이미 있어 %s 로 버전업합니다." % (base_slug, final_slug))
        html = html.replace("%s/cases/%s.html" % (SITE, base_slug),
                            "%s/cases/%s.html" % (SITE, final_slug))
        html = html.replace("/cases/%s.html" % base_slug,
                            "/cases/%s.html" % final_slug)
    url = "%s/cases/%s.html" % (SITE, final_slug)
    dst = os.path.join(cases_dir, final_slug + ".html")

    # 6) cases/ 로 복사 (이동 아님)
    if dry:
        log("[DRY] 복사 예정: %s -> cases/%s.html" % (qname, final_slug))
    else:
        os.makedirs(cases_dir, exist_ok=True)
        write_text(dst, html)
        log("사례 페이지 생성: cases/%s.html" % final_slug)

    # 7) 메타 로드
    mpath = find_meta(qpath)
    meta = read_meta(mpath)
    if meta:
        log("메타 파일 사용: %s" % os.path.basename(mpath))
    else:
        meta = derive_meta_from_html(html)
        log("경고: 메타 파일(%s)이 없어 <title>/description 에서 카드 정보를 추정합니다."
            % os.path.basename(mpath))

    # 8) sitemap.xml
    sm = os.path.join(REPO, "sitemap.xml")
    try:
        update_sitemap(sm, url, dry)
    except Exception as e:
        log("경고: sitemap.xml 갱신 실패: %s" % e)

    # 9) index.html (카드 실패해도 게시는 중단하지 않음)
    idx = os.path.join(REPO, "index.html")
    num = meta.get("num") or ""
    try:
        if not num:
            num = next_case_num(read_text(idx))
        num = ("%02d" % int(num)) if str(num).isdigit() else str(num)
        card = build_card(meta, final_slug, num)
        update_index(idx, card, final_slug, dry)
    except Exception as e:
        log("경고: index.html 카드 추가 실패(게시는 계속 진행): %s" % e)
        num = num or "00"

    # 10) 대기열 -> published
    moved = os.path.join(PUBLISHED_DIR, qname)
    if dry:
        log("[DRY] 이동 예정: queue/%s -> published/%s" % (qname, qname))
    else:
        if os.path.exists(moved):
            moved = os.path.join(PUBLISHED_DIR, "%s-%s" % (stamp(), qname))
        shutil.move(qpath, moved)
        if os.path.exists(mpath):
            mdst = os.path.join(PUBLISHED_DIR, os.path.basename(mpath))
            if os.path.exists(mdst):
                mdst = os.path.join(PUBLISHED_DIR,
                                    "%s-%s" % (stamp(), os.path.basename(mpath)))
            shutil.move(mpath, mdst)
        log("대기열 파일 이동: published/%s" % os.path.basename(moved))

    # 11) IndexNow 키 파일 확인
    keyfile = ensure_indexnow_keyfile(dry)

    # 12) git
    region = meta.get("region") or meta.get("title_line1") or final_slug
    obj = meta.get("object") or re.sub(r"\s*감정평가\s*$", "",
                                       meta.get("title_line2") or "부동산")
    purp = meta.get("purpose_short") or meta.get("cat") or "감정평가"
    nn = num if num else (seq or "NN")
    msg = "feat: [%s] [%s] [%s] 감정평가 사례 추가 (#%s)" % (region, obj, purp, nn)

    # 주의: automation/rejected 는 개인정보 게이트에 걸린 원본이 들어갈 수 있으므로
    #       절대 커밋 대상에 넣지 않는다(automation/.gitignore 로도 제외).
    paths = ["cases/%s.html" % final_slug, "sitemap.xml", "index.html",
             "automation/queue", "automation/published", "automation/state"]
    if keyfile:
        paths.append(os.path.basename(keyfile))
    sha, result = git_publish(paths, msg, args.no_push, dry)

    # 13) IndexNow 통보 (push 성공 시에만)
    if result == "OK":
        ping_indexnow(url, dry)
    else:
        log("push 성공이 아니므로 IndexNow 통보를 생략합니다. (result=%s)" % result)

    # 14) 게시 로그
    append_log_row(today_dash(), qname, url, sha,
                   "OK" if result == "OK" else result, dry)
    log("==== 완료: %s (%s) ====" % (url, result))
    return 0 if result in ("OK", "NO_CHANGE") else 1


if __name__ == "__main__":
    code = 1
    try:
        code = main()
    except Exception as exc:  # noqa
        import traceback
        log("치명적 오류: %s" % exc)
        for ln in traceback.format_exc().splitlines():
            log("  " + ln)
        code = 2
    finally:
        flush_runlog("--dry-run" in sys.argv)
    sys.exit(code)
