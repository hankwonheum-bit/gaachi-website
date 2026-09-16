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
   (단, 직전 실행이 커밋 전에 실패해서 남긴 파일이면 -v2 를 만들지 않고 재사용한다.)
 - 같은 날 두 번 실행해도 안전하다(멱등).
 - 커밋이 이뤄지지 않으면 대기열(queue/) 파일을 소비하지 않는다.
   '스테이지된 변경 없음' 은 절대로 성공으로 처리하지 않는다(STAGE_FAILED).

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
import time
from datetime import datetime, timedelta, timezone

# find_git_v1.py 는 같은 폴더에 있다. 작업 스케줄러가 다른 작업 폴더에서
# 호출해도 확실히 import 되도록 스크립트 폴더를 sys.path 에 먼저 넣는다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from find_git_v1 import find_git_with_source
except Exception:  # 탐색기 파일이 없어도 본체는 죽지 않는다
    def find_git_with_source():
        return None, None

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

# 시작할 때 1회만 해석해서 재사용하는 git 실행 파일 경로. None 이면 git 없음.
GIT_EXE = None
GIT_SRC = None

# git 을 못 찾았을 때 게시 로그 result 칸과 실행 로그에 남기는 안내 문구.
# TSV 이므로 탭 문자를 넣지 않는다.
MANUAL_PUSH_HINT = ("GitHub Desktop 을 열고 Push 를 눌러 주시면 그때 홈페이지에 반영됩니다.")
GIT_NOT_FOUND_RESULT = ("GIT_NOT_FOUND / 페이지는 내 컴퓨터에 준비 완료 — "
                        "아직 홈페이지에 게시되지 않았습니다. " + MANUAL_PUSH_HINT)


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


def resolve_git():
    """git 실행 파일을 1회만 해석해서 전역에 보관한다. 반환: 경로 또는 None"""
    global GIT_EXE, GIT_SRC
    GIT_EXE, GIT_SRC = find_git_with_source()
    if GIT_EXE:
        log("git 실행 파일: %s (출처: %s)" % (GIT_EXE, GIT_SRC))
        if GIT_SRC == "GitHubDesktop":
            log("주의: GitHub Desktop 내장 git 을 사용합니다. GitHub Desktop 을 "
                "업데이트하면 경로가 바뀔 수 있으니 Git for Windows 설치를 권장합니다 "
                "(https://git-scm.com/download/win).")
    else:
        log("GIT_NOT_FOUND — git 실행 파일을 찾지 못했습니다.")
    return GIT_EXE


def git(args, check=False):
    """해석된 git 실행 파일로 명령을 돌린다. git 이 없으면 (-1, 안내문)."""
    if not GIT_EXE:
        msg = "GIT_NOT_FOUND: git 실행 파일이 없어 'git %s' 를 건너뜁니다." % " ".join(args)
        if check:
            raise RuntimeError(msg)
        return -1, msg
    p = subprocess.run([GIT_EXE] + args, cwd=REPO, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode("utf-8", "replace").strip()
    if check and p.returncode != 0:
        raise RuntimeError("git %s 실패: %s" % (" ".join(args), out))
    return p.returncode, out


# ------------------------------------------------------- git 잠금 파일(index.lock)
# 이전 git 프로세스가 비정상 종료하면 .git/index.lock 이 0바이트로 남는다.
# 그 상태에서는 'git add' 가 전부
#   fatal: Unable to create '....git/index.lock': File exists.
# 로 실패하는데, 예전 코드는 반환값을 보지 않아서 "스테이지된 변경이 없음" 으로
# 읽고 그대로 '완료' 로 끝냈다. 대기열 파일은 이미 소비된 뒤라 사례가 통째로
# 사라지는, 무인 실행에서 가장 나쁜 실패였다. 그래서 git 작업 전에 반드시 이
# 잠금 파일을 먼저 정리하고, 정리하지 못하면 아예 시작하지 않는다.
GIT_LOCK_STALE_SEC = 300      # 5분보다 오래됐으면 '죽은 잠금' 으로 본다
GIT_LOCK_WAIT_SEC = 3         # 최근 잠금이면 잠깐 기다려 본다
GIT_LOCK_RETRIES = 2          # 기다렸다가 다시 확인하는 횟수


class GitLockError(RuntimeError):
    """.git/index.lock 을 지우지 못해 게시를 시작할 수 없을 때."""


def git_dir():
    """REPO 의 .git 경로. (.git 이 'gitdir: …' 파일인 경우도 처리)"""
    p = os.path.join(REPO, ".git")
    if os.path.isfile(p):
        try:
            txt = read_text(p).strip()
        except Exception:
            return p
        if txt.startswith("gitdir:"):
            g = txt.split(":", 1)[1].strip()
            if not os.path.isabs(g):
                g = os.path.normpath(os.path.join(REPO, g))
            return g
    return p


def git_lock_path():
    return os.path.join(git_dir(), "index.lock")


def _git_process_running():
    """git 프로세스가 돌고 있을 '가능성' 만 본다. 확인 못 하면 False(없다고 본다)."""
    try:
        if os.name == "nt":
            p = subprocess.run(["tasklist", "/FI", "IMAGENAME eq git.exe", "/NH"],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=15)
            return "git.exe" in p.stdout.decode("utf-8", "replace").lower()
        p = subprocess.run(["pgrep", "-x", "git"], stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=15)
        return p.returncode == 0
    except Exception:
        return False


def _remove_git_lock(lock):
    """잠금 파일 '하나' 만 지운다. .git 하위의 다른 것은 절대 건드리지 않는다."""
    if os.path.basename(lock) != "index.lock":
        raise GitLockError("안전장치: index.lock 이 아닌 파일은 지우지 않습니다: %s" % lock)
    os.remove(lock)   # 실패하면 OSError 가 그대로 올라간다


def _lock_manual_hint():
    return ("git 잠금 파일(.git\\index.lock)을 지우지 못했습니다. 게시를 중단합니다. "
            "파일 탐색기에서 %s 폴더를 열고 .git\\index.lock 파일을 삭제한 뒤 다시 "
            "실행해 주세요. (명령 프롬프트에서는 cd /d \"%s\" 후 del .git\\index.lock) "
            "— .git 폴더가 보이지 않으면 탐색기의 '보기 > 숨긴 항목' 을 켜세요."
            % (REPO, REPO))


def clear_stale_git_lock(dry=False):
    """git 작업 전에 남아 있는 .git/index.lock 을 정리한다.
    - 5분보다 오래됐고 git 프로세스가 없어 보이면 바로 제거
    - 최근 파일이면 몇 초 기다렸다가, 그래도 남아 있으면 제거
    - 제거에 실패하면 GitLockError 를 올린다(조용히 진행하지 않는다)
    반환: 제거했으면 True, 잠금이 없었으면 False"""
    lock = git_lock_path()
    if not os.path.exists(lock):
        return False

    age = 0.0
    for attempt in range(GIT_LOCK_RETRIES + 1):
        try:
            age = time.time() - os.path.getmtime(lock)
        except OSError:
            log("git 잠금 파일이 사라졌습니다. 정상 진행합니다.")
            return False
        running = _git_process_running()
        if age >= GIT_LOCK_STALE_SEC and not running:
            break                      # 확실한 '죽은 잠금'
        if attempt >= GIT_LOCK_RETRIES:
            log("경고: git 잠금 파일이 %d초 전에 만들어졌지만%s 계속 남아 있어 "
                "제거를 시도합니다." % (int(age),
                                      " git 프로세스가 보이고" if running else ""))
            break
        log("git 잠금 파일(.git/index.lock)이 있습니다(%d초 전 생성%s). "
            "%d초 기다렸다가 다시 확인합니다."
            % (int(age), ", git 프로세스 실행 중으로 보임" if running else "",
               GIT_LOCK_WAIT_SEC))
        time.sleep(GIT_LOCK_WAIT_SEC)
        if not os.path.exists(lock):
            log("git 잠금 파일이 스스로 사라졌습니다. 정상 진행합니다.")
            return False

    if dry:
        log("[DRY] 오래된 git 잠금 파일(.git/index.lock) 제거 예정 (생성 %d초 전)" % int(age))
        return True
    try:
        _remove_git_lock(lock)
    except GitLockError:
        raise
    except OSError as e:
        log("오류: git 잠금 파일을 지우지 못했습니다: %s" % e)
        raise GitLockError(_lock_manual_hint())
    log("오래된 git 잠금 파일(.git/index.lock)을 제거했습니다 (생성 %d초 전)." % int(age))
    return True


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


# ---------------------------------------------------------------- 게시일 스탬핑
# 초안(draft)은 "작성한 날"의 날짜를 박은 채로 검토 큐에서 며칠씩 대기할 수 있다.
# 실제로 cases/ 에 올라가는 순간의 KST 날짜로, "웹페이지에 대한 날짜"만 다시 찍는다.
# (프레시니스는 AI 인용과 가장 강하게 붙는 지표이므로 초안 작성일이 아니라
#  실제 게시일이 찍혀 있어야 한다.)
#
# ▷ 다시 찍는 대상 = 웹페이지에 대한 사실
#   1) <time class="publish-date"  datetime="...">…</time>   보이는 게시일
#   2) <time class="modified-date" datetime="...">…</time>   보이는 최종 업데이트
#   3) <meta property="article:published_time" content="...">
#   4) <meta property="article:modified_time"  content="...">
#   5) JSON-LD "datePublished" / "dateModified"
#   6) <meta itemprop="datePublished|dateModified" content="...">  (v3 Article 마이크로데이터)
#   7) <div class="footer-update"> … <time datetime="...">…</time>
#      (v3 템플릿에서 실제로 "보이는 최종 업데이트"는 여기 하나뿐이다)
#
# ▷ 절대 건드리지 않는 것 = 감정평가 업무에 대한 사실
#   - 감정평가서 작성일 : <time class="report-date" …> 또는 v3 의 .case-byline /
#                         "감정평가서 작성일" info-item 안의 <time datetime="YYYY-MM-DD">
#   - 기준시점 / 거래시점 : <time datetime="YYYY">YYYY년</time>
#   아래 치환은 모두 위 7개 앵커(클래스명·meta 속성명·JSON-LD 키)에만 붙는다.
#   앵커가 없는 <time> 은 하나도 건드리지 않으므로 작성일·기준시점은 그대로 남는다.

_ISO = r"\d{4}-\d{2}-\d{2}"


def kr_date(iso):
    """'2026-09-16' -> '2026년 9월 16일' (월·일에 0 채우지 않음)"""
    y, m, d = iso.split("-")
    return "%d년 %d월 %d일" % (int(y), int(m), int(d))


def _squeeze(s, n=120):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else (s[:n] + "…")


def _splice(html, pat, fix, label, changes):
    """pat 에 걸린 조각을 fix() 결과로 바꾸고 (라벨, 이전, 이후) 를 기록한다."""
    out, pos, n = [], 0, 0
    for m in pat.finditer(html):
        old = m.group(0)
        new = fix(old)
        if new != old:
            changes.append((label, old, new))
        out.append(html[pos:m.start()])
        out.append(new)
        pos = m.end()
        n += 1
    out.append(html[pos:])
    return "".join(out), n


def _sub_time_by_class(html, cls, iso, label, changes):
    """<time class="…cls…" datetime="ISO">한글날짜</time> 의 datetime 과 본문을 함께 교체."""
    pat = re.compile(
        r'<time\b(?=[^>]*\bclass=["\'][^"\']*\b%s\b)[^>]*>[^<]*</time>'
        % re.escape(cls), re.I)

    def fix(tag):
        t = re.sub(r'(\bdatetime=["\'])%s' % _ISO,
                   lambda m: m.group(1) + iso, tag, count=1, flags=re.I)
        t = re.sub(r'(>)[^<]*(</time>)',
                   lambda m: m.group(1) + kr_date(iso) + m.group(2), t, count=1)
        return t

    return _splice(html, pat, fix, label, changes)


def _meta_pat(attr, name):
    return re.compile(r'<meta\b[^>]*\b%s=["\']%s["\'][^>]*>'
                      % (attr, re.escape(name)), re.I)


def _sub_meta_date(html, attr, name, iso, label, changes):
    """<meta … content="YYYY-MM-DD[T…]"> 에서 날짜 부분만 교체(시각·오프셋은 보존)."""
    def fix(tag):
        return re.sub(r'(\bcontent=["\'])%s' % _ISO,
                      lambda m: m.group(1) + iso, tag, count=1, flags=re.I)

    return _splice(html, _meta_pat(attr, name), fix, label, changes)


def _sub_jsonld_date(html, key, iso, label, changes):
    """application/ld+json 블록 안의 "key": "YYYY-MM-DD" 만 교체."""
    blk = re.compile(
        r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>.*?</script>',
        re.I | re.S)
    kp = re.compile(r'(["\']%s["\']\s*:\s*["\'])%s' % (re.escape(key), _ISO))
    hits = [0]

    def fix(block):
        new, n = kp.subn(lambda m: m.group(1) + iso, block)
        hits[0] += n
        return new

    html, _ = _splice(html, blk, fix, label, changes)
    return html, hits[0]


def _sub_footer_update(html, iso, label, changes):
    """<div class="footer-update"> 안의 첫 <time datetime="ISO">…</time> 를 교체.
    v3 템플릿에서 사람이 눈으로 보는 '최종 업데이트'가 바로 여기다."""
    pat = re.compile(
        r'<div\b[^>]*\bclass=["\'][^"\']*\bfooter-update\b[^"\']*["\'][^>]*>.*?</div>',
        re.I | re.S)
    tp = re.compile(r'(<time\b[^>]*\bdatetime=["\'])%s(["\'][^>]*>)[^<]*(</time>)'
                    % _ISO, re.I)
    hits = [0]

    def fix(block):
        new, n = tp.subn(
            lambda m: m.group(1) + iso + m.group(2) + kr_date(iso) + m.group(3),
            block, count=1)
        hits[0] += n
        return new

    html, _ = _splice(html, pat, fix, label, changes)
    # div 자체가 아니라 '실제로 날짜를 찍을 수 있는 <time>' 의 개수를 돌려준다.
    return html, hits[0]


def extract_published_date(html):
    """이미 게시된 페이지에서 '기존 게시일(ISO)'을 읽는다. 못 찾으면 None."""
    m = re.search(
        r'<time\b(?=[^>]*\bclass=["\'][^"\']*\bpublish-date\b)[^>]*\bdatetime=["\'](%s)'
        % _ISO, html, re.I)
    if m:
        return m.group(1)
    for attr, name in (("property", "article:published_time"),
                       ("itemprop", "datePublished")):
        mt = _meta_pat(attr, name).search(html)
        if mt:
            mc = re.search(r'\bcontent=["\'](%s)' % _ISO, mt.group(0), re.I)
            if mc:
                return mc.group(1)
    m = re.search(r'["\']datePublished["\']\s*:\s*["\'](%s)' % _ISO, html)
    if m:
        return m.group(1)
    return None


def find_previous_published_date(cases_dir, base_slug, final_slug):
    """재게시(-v2/-v3 …)일 때 원본 페이지의 게시일을 찾는다.
    원본(base) 을 최우선으로, 실패하면 최신 이전 버전부터 거슬러 올라간다.
    반환: (ISO 날짜 또는 None, 읽어 온 파일명 또는 None)"""
    cands = [base_slug]
    mv = re.match(r"^%s-v(\d+)$" % re.escape(base_slug), final_slug)
    if mv:
        cands += ["%s-v%d" % (base_slug, i) for i in range(int(mv.group(1)) - 1, 1, -1)]
    for slug in cands:
        p = os.path.join(cases_dir, slug + ".html")
        if not os.path.exists(p):
            continue
        try:
            iso = extract_published_date(read_text(p))
        except Exception as e:
            log("경고: 기존 페이지 %s.html 을 읽지 못했습니다: %s" % (slug, e))
            continue
        if iso:
            return iso, slug + ".html"
    return None, None


def stamp_publish_dates(html, pub_iso, mod_iso):
    """게시일=pub_iso, 최종 업데이트=mod_iso 로 다시 찍는다.
    반환: (새 html, [(라벨, 이전, 이후)…], [경고…], 앵커를 찾은 곳 수)

    ※ '찾은 곳(matches)' 과 '바뀐 곳(changes)' 은 다른 값이다.
       초안 날짜가 이미 오늘이면 앵커는 다 있는데 바뀐 곳은 0이 된다.
       예전 코드는 changes 만 세어서 그때마다 '날짜 표기를 한 곳도 찾지 못했습니다'
       라는 틀린 경고를 냈다. 그래서 matches 를 따로 돌려준다."""
    changes, warns = [], []

    html, n_pub_vis = _sub_time_by_class(html, "publish-date", pub_iso,
                                         "보이는 게시일(time.publish-date)", changes)
    html, n_mod_vis = _sub_time_by_class(html, "modified-date", mod_iso,
                                         "보이는 최종 업데이트(time.modified-date)", changes)
    html, n_foot = _sub_footer_update(html, mod_iso,
                                      "보이는 최종 업데이트(div.footer-update)", changes)
    html, n_op = _sub_meta_date(html, "property", "article:published_time", pub_iso,
                                "meta article:published_time", changes)
    html, n_om = _sub_meta_date(html, "property", "article:modified_time", mod_iso,
                                "meta article:modified_time", changes)
    html, n_ip = _sub_meta_date(html, "itemprop", "datePublished", pub_iso,
                                "meta itemprop=datePublished", changes)
    html, n_im = _sub_meta_date(html, "itemprop", "dateModified", mod_iso,
                                "meta itemprop=dateModified", changes)
    html, n_jp = _sub_jsonld_date(html, "datePublished", pub_iso,
                                  "JSON-LD datePublished", changes)
    html, n_jm = _sub_jsonld_date(html, "dateModified", mod_iso,
                                  "JSON-LD dateModified", changes)

    if n_pub_vis == 0:
        warns.append("페이지에 '보이는 게시일'(<time class=\"publish-date\">)이 없습니다. "
                     "메타·JSON-LD 게시일만 찍었습니다. "
                     "템플릿에 게시일 표시를 추가해야 독자와 크롤러가 눈으로 확인할 수 있습니다.")
    if n_mod_vis == 0 and n_foot == 0:
        warns.append("페이지에 '보이는 최종 업데이트' 표기가 없습니다"
                     "(<time class=\"modified-date\"> / <div class=\"footer-update\"> 모두 없음).")
    if n_op == 0 or n_om == 0:
        warns.append("meta article:published_time / article:modified_time 중 일부가 없습니다 "
                     "(published %d건, modified %d건)." % (n_op, n_om))
    if n_jp == 0 or n_jm == 0:
        warns.append("JSON-LD datePublished / dateModified 중 일부가 없습니다 "
                     "(datePublished %d건, dateModified %d건)." % (n_jp, n_jm))
    matches = (n_pub_vis + n_mod_vis + n_foot + n_op + n_om
               + n_ip + n_im + n_jp + n_jm)
    return html, changes, warns, matches


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
def staged_paths():
    """현재 인덱스에 스테이지된 경로 목록. 명령 자체가 실패하면 (None, 출력)."""
    rc, out = git(["diff", "--cached", "--name-only"])
    if rc != 0:
        return None, out
    names = []
    for ln in out.splitlines():
        ln = ln.strip().strip('"')
        if ln:
            names.append(ln.replace("\\", "/"))
    return names, out


def _is_staged(staged, rel):
    """rel(파일 또는 폴더)이 스테이지 목록 안에 있는가."""
    rel = rel.replace("\\", "/").rstrip("/")
    for s in staged:
        if s == rel or s.startswith(rel + "/"):
            return True
    return False


def git_publish(paths, msg, no_push=False, dry=False, expect=None):
    """반환: (commit_sha, result)
    result in {OK, PUSH_FAIL, NO_CHANGE, STAGE_FAILED, COMMIT_FAIL, GIT_NOT_FOUND}

    expect: 이번 실행에서 실제로 만들거나 고친 파일들(저장소 기준 상대경로).
            git add 이후 'git diff --cached --name-only' 로 정말 스테이지됐는지
            확인하고, 하나라도 빠지면 STAGE_FAILED 로 끝낸다.
            expect 가 비어 있을 때만 '스테이지된 변경 없음' 이 진짜 NO_CHANGE 다."""
    expect = list(expect or [])
    if dry:
        log("[DRY] git add: %s" % ", ".join(paths), dry)
        log("[DRY] git commit -m \"%s\"" % msg, dry)
        log("[DRY] git push origin main", dry)
        return "-", "OK"

    # git 이 없어도 파일 준비(검증/복사/sitemap/index)는 이미 끝났다.
    # 커밋/푸시만 건너뛰고, 사용자가 GitHub Desktop 으로 직접 Push 하게 안내한다.
    if not GIT_EXE:
        log("GIT_NOT_FOUND — git 실행 파일이 없어 커밋/푸시를 건너뜁니다.")
        log("사례 페이지와 index.html, sitemap.xml 수정은 내 컴퓨터에 정상적으로 "
            "준비되었습니다. 다만 아직 홈페이지에는 올라가지 않았습니다.")
        log("→ " + MANUAL_PUSH_HINT)
        log("→ 근본 해결: https://git-scm.com/download/win 에서 Git for Windows 를 "
            "설치하세요. 설치 방법: automation\\git_설치안내_v1.txt")
        return "-", "GIT_NOT_FOUND"

    # 실행 도중(검증~파일 작성 사이)에 새로 생긴 잠금 파일도 한 번 더 확인한다.
    try:
        clear_stale_git_lock(False)
    except GitLockError as e:
        log("오류: %s" % e)
        return "-", "STAGE_FAILED"

    # 1) git add — 반환값을 반드시 확인한다(예전 코드가 여기서 실패를 삼켰다).
    add_fail = []
    for p in paths:
        rc, out = git(["add", "-A", "--", p])
        if rc != 0:
            add_fail.append(p)
            log("오류: git add 실패 (%s) rc=%d: %s" % (p, rc, _squeeze(out, 300)))

    # 2) 정말 인덱스에 올라갔는지 눈으로 확인한다.
    staged, out = staged_paths()
    if staged is None:
        log("오류: 'git diff --cached --name-only' 실행 실패: %s" % _squeeze(out, 300))
        log("!!! 인덱스 상태를 확인할 수 없어 커밋하지 않고 중단합니다. (STAGE_FAILED)")
        return "-", "STAGE_FAILED"

    missing = [p for p in expect if not _is_staged(staged, p)]

    def _log_missing():
        for p in missing:
            log("오류: 스테이지되어야 할 파일이 인덱스에 없습니다: %s" % p)

    if not staged:
        # 스테이지가 비었을 때 '진짜 바뀐 게 없는 것(NO_CHANGE)' 과
        # 'add 가 실패해서 비어 있는 것(STAGE_FAILED)' 을 반드시 구분한다.
        # git 자신이 "차이 없음" 이라고 답할 때만 NO_CHANGE 다.
        clean = False
        if expect and not add_fail:
            rc, out = git(["status", "--porcelain", "--"] + list(expect))
            clean = (rc == 0 and not out.strip())
        elif not expect and not add_fail:
            clean = True
        if not clean:
            _log_missing()
            log("!!! 치명적: 이번 실행에서 파일을 만들거나 고쳤는데 git 인덱스에 올라간 "
                "것이 하나도 없습니다. 커밋도 푸시도 이뤄지지 않았으므로 홈페이지에는 "
                "아무것도 반영되지 않았습니다. (STAGE_FAILED)")
            log("→ 가장 흔한 원인은 .git\\index.lock 이 남아 있는 경우입니다. "
                "바로 위의 git add 오류 메시지를 확인하세요.")
            return "-", "STAGE_FAILED"
        # 여기만이 '진짜' NO_CHANGE 다: 대기열 원고가 이미 커밋된 내용과 같아서
        # 새로 커밋할 것이 없다.
        log("이미 커밋된 내용과 같아 커밋할 변경이 없습니다. (NO_CHANGE)")
        rc, sha = git(["rev-parse", "--short", "HEAD"])
        return (sha if rc == 0 else "-"), "NO_CHANGE"

    if missing or add_fail:
        _log_missing()
        log("!!! 치명적: 일부 파일만 스테이지됐습니다. 반쪽짜리 커밋을 막기 위해 "
            "커밋하지 않고 중단합니다. (STAGE_FAILED)")
        return "-", "STAGE_FAILED"

    log("스테이지 확인 완료 (%d개): %s%s"
        % (len(staged), ", ".join(staged[:8]), " …" if len(staged) > 8 else ""))

    rc, out = git(["commit", "-m", msg])
    if rc != 0:
        log("커밋 실패 rc=%d: %s" % (rc, out))
        return "-", "COMMIT_FAIL"
    rc, sha = git(["rev-parse", "--short", "HEAD"])
    if rc != 0:
        log("경고: 커밋 후 HEAD 해시를 읽지 못했습니다: %s" % _squeeze(sha, 200))
        sha = "-"
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
        log("→ " + MANUAL_PUSH_HINT)
        return sha, "PUSH_FAIL"
    rc3, out3 = git(["push", "origin", "main"])
    if rc3 == 0:
        log("재시도 push 완료")
        return sha, "OK"
    log("재시도 push 실패: %s" % out3)
    log("커밋은 로컬에 남겨 둡니다(리셋하지 않음). 수동 확인 필요.")
    log("→ " + MANUAL_PUSH_HINT)
    return sha, "PUSH_FAIL"


# --------------------------------------------- 직전 실패 실행이 남긴 파일 재사용
def _date_blind_signature(html):
    """날짜 표기만 지운 본문 시그니처. 게시일 스탬핑 차이를 무시하고
    '같은 원고인가' 만 본다."""
    s = re.sub(_ISO, "@D@", html)
    s = re.sub(r"\d{4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일", "@D@", s)
    s = re.sub(r"\d{4}\.\s*\d{1,2}\.\s*\d{1,2}\.?", "@D@", s)
    return re.sub(r"\s+", " ", s).strip()


def leftover_reason(rel_path, abs_path, draft_html):
    """cases/<slug>.html 이 '직전 실행이 커밋 전에 실패해서 남긴 파일' 인가?

    git 이 있으면 '인덱스에 없는 파일(=한 번도 커밋된 적 없음)' 인지로 판단한다.
    이게 가장 확실하다. 커밋된 파일이면 진짜 기존 사례이므로 -v2 로 넘어간다.
    git 이 없을 때만 날짜를 뺀 본문 비교로 대신 판단한다.
    반환: 재사용해도 되면 사유 문자열, 아니면 ''"""
    rel = rel_path.replace("\\", "/")
    if GIT_EXE:
        rc, _ = git(["ls-files", "--error-unmatch", "--", rel])
        if rc != 0:
            return "git 에 한 번도 커밋된 적이 없는 파일(직전 실행이 커밋 전에 중단됨)"
        return ""
    try:
        same = (_date_blind_signature(read_text(abs_path))
                == _date_blind_signature(draft_html))
    except Exception:
        same = False
    if same:
        return "대기열 원고와 (날짜를 빼고) 내용이 같은 파일"
    return ""


def undo_moves(pairs):
    """커밋이 이뤄지지 않았을 때 대기열 파일을 queue/ 로 되돌린다."""
    for src, dst in reversed(pairs):
        try:
            if os.path.exists(dst) and not os.path.exists(src):
                shutil.move(dst, src)
                log("커밋되지 않았으므로 대기열 파일을 되돌렸습니다: "
                    "published/%s -> queue/%s"
                    % (os.path.basename(dst), os.path.basename(src)))
        except Exception as e:
            log("경고: 대기열 파일을 되돌리지 못했습니다(%s -> %s): %s" % (dst, src, e))
            log("→ automation\\published\\%s 를 automation\\queue\\ 로 직접 옮겨 "
                "주세요. 그래야 다음 실행에서 다시 게시합니다." % os.path.basename(dst))


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

    # git 실행 파일을 여기서 딱 1회 해석한다(없으면 None -> 커밋/푸시만 생략).
    resolve_git()

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

    # 2.5) git 잠금 파일 정리 — 아무것도 쓰기 전에 먼저 한다.
    #      여기서 못 지우면 뒤의 git add 가 전부 실패하므로 시작조차 하지 않는다.
    try:
        clear_stale_git_lock(dry)
    except GitLockError as e:
        log("오류: %s" % e)
        log("대기열 파일(%s)은 queue/ 에 그대로 두었습니다. 잠금 파일을 지운 뒤 "
            "다시 실행하면 이어서 게시합니다." % qname)
        append_log_row(today_dash(), qname, "-", "-", "GIT_LOCK_STUCK", dry)
        log("==== 실패: git 잠금 파일 때문에 시작하지 못했습니다 (GIT_LOCK_STUCK) ====")
        return 1

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
    #    예외: 직전 실행이 커밋 전에 실패해서 남긴 파일이라면 -v2 를 만들지 않고
    #          그 파일을 그대로 다시 쓴다. (재실행 멱등성)
    cases_dir = os.path.join(REPO, "cases")
    final_slug = base_slug
    reuse_why = ""
    v = 1
    while os.path.exists(os.path.join(cases_dir, final_slug + ".html")):
        reuse_why = leftover_reason("cases/%s.html" % final_slug,
                                    os.path.join(cases_dir, final_slug + ".html"),
                                    html)
        if reuse_why:
            break
        v += 1
        final_slug = "%s-v%d" % (base_slug, v)
    if reuse_why:
        log("cases/%s.html 이 이미 있지만 %s 이므로, 새 버전(-v%d)을 만들지 않고 "
            "그 파일을 다시 씁니다." % (final_slug, reuse_why, v + 1))
    if final_slug != base_slug:
        log("cases/%s.html 이 이미 있어 %s 로 버전업합니다." % (base_slug, final_slug))
        html = html.replace("%s/cases/%s.html" % (SITE, base_slug),
                            "%s/cases/%s.html" % (SITE, final_slug))
        html = html.replace("/cases/%s.html" % base_slug,
                            "/cases/%s.html" % final_slug)
    url = "%s/cases/%s.html" % (SITE, final_slug)
    dst = os.path.join(cases_dir, final_slug + ".html")

    # 5.5) 게시일 스탬핑 — 초안에 박힌 '작성한 날'이 아니라 '실제로 올라가는 날'을 찍는다.
    #      감정평가서 작성일·기준시점은 건드리지 않는다.
    today_iso = today_dash()
    pub_iso = today_iso
    if final_slug != base_slug:
        prev_iso, prev_name = find_previous_published_date(cases_dir, base_slug, final_slug)
        if prev_iso:
            pub_iso = prev_iso
            log("재게시: 게시일은 %s 의 기존 값 %s 을 유지하고, 최종 업데이트만 %s 로 찍습니다."
                % (prev_name, prev_iso, today_iso))
        else:
            log("경고: 기존 페이지에서 게시일을 읽지 못했습니다. "
                "게시일·최종 업데이트 모두 오늘(%s)로 찍습니다." % today_iso)
    html, date_changes, date_warns, date_hits = stamp_publish_dates(
        html, pub_iso, today_iso)
    for w in date_warns:
        log("경고: %s" % w)
    if date_changes:
        log("게시일 스탬핑 완료 — 게시일 %s / 최종 업데이트 %s (%d곳 갱신)"
            % (pub_iso, today_iso, len(date_changes)))
        for label, before, after in date_changes:
            log("  · %s" % label)
            log("      이전: %s" % _squeeze(before))
            log("      이후: %s" % _squeeze(after))
    elif date_hits:
        # 앵커는 다 있는데 바꿀 게 없었던 경우 = 초안 날짜가 이미 오늘이다.
        # 이건 정상이므로 경고가 아니다.
        log("게시일·최종 업데이트가 이미 오늘 날짜입니다 (앵커 %d곳 확인). "
            "바꿀 내용이 없어 그대로 둡니다." % date_hits)
    else:
        log("경고: 갱신할 날짜 표기(앵커)를 한 곳도 찾지 못했습니다. "
            "게시일 스탬핑을 건너뜁니다.")

    # 6) cases/ 로 복사 (이동 아님)
    #    expect = 이번 실행에서 실제로 만들거나 고친 파일. git add 뒤에
    #    정말 스테이지됐는지 이 목록으로 확인한다.
    expect = []
    if dry:
        log("[DRY] 복사 예정: %s -> cases/%s.html" % (qname, final_slug))
    else:
        os.makedirs(cases_dir, exist_ok=True)
        write_text(dst, html)
        expect.append("cases/%s.html" % final_slug)
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
        if update_sitemap(sm, url, dry) and not dry:
            expect.append("sitemap.xml")
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
        if update_index(idx, card, final_slug, dry) and not dry:
            expect.append("index.html")
    except Exception as e:
        log("경고: index.html 카드 추가 실패(게시는 계속 진행): %s" % e)
        num = num or "00"

    # 10) 대기열 -> published
    #     커밋에 '큐에서 빠지고 published 로 들어간 사실' 까지 함께 담기도록
    #     이동을 먼저 한다. 다만 커밋이 이뤄지지 않으면(undo_moves) 곧바로
    #     queue/ 로 되돌려서, 대기열 항목이 커밋 없이 소비되는 일이 없게 한다.
    move_pairs = []
    if dry:
        log("[DRY] 이동 예정: queue/%s -> published/%s" % (qname, qname))
    else:
        moved = os.path.join(PUBLISHED_DIR, qname)
        if os.path.exists(moved):
            moved = os.path.join(PUBLISHED_DIR, "%s-%s" % (stamp(), qname))
        shutil.move(qpath, moved)
        move_pairs.append((qpath, moved))
        if os.path.exists(mpath):
            mdst = os.path.join(PUBLISHED_DIR, os.path.basename(mpath))
            if os.path.exists(mdst):
                mdst = os.path.join(PUBLISHED_DIR,
                                    "%s-%s" % (stamp(), os.path.basename(mpath)))
            shutil.move(mpath, mdst)
            move_pairs.append((mpath, mdst))
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
    sha, result = git_publish(paths, msg, args.no_push, dry, expect=expect)

    # 12.5) 커밋이 이뤄지지 않았으면 대기열 항목을 소비하지 않는다.
    #       (다음 실행이 같은 파일을 다시 집어서 이어서 게시할 수 있게 한다)
    if result in ("STAGE_FAILED", "COMMIT_FAIL"):
        undo_moves(move_pairs)

    # 13) IndexNow 통보 (push 성공 시에만)
    if result == "OK":
        ping_indexnow(url, dry)
    else:
        log("push 성공이 아니므로 IndexNow 통보를 생략합니다. (result=%s)" % result)

    # 14) 게시 로그
    #     git 이 없어 커밋/푸시를 못 한 경우에는, 나중에 로그만 봐도 무엇을
    #     해야 하는지 알 수 있도록 result 칸에 한국어 안내를 그대로 적는다.
    result_cell = GIT_NOT_FOUND_RESULT if result == "GIT_NOT_FOUND" else result
    append_log_row(today_dash(), qname, url, sha, result_cell, dry)

    if result == "GIT_NOT_FOUND":
        log("==== 완료(로컬 준비까지): %s ====" % url)
        log("★ 홈페이지에 올리려면: " + MANUAL_PUSH_HINT)
    elif result in ("STAGE_FAILED", "COMMIT_FAIL"):
        log("==== 실패: %s (%s) — 홈페이지에 아무것도 반영되지 않았습니다 ===="
            % (url, result))
        log("★ 대기열 파일(%s)은 queue/ 에 그대로 있습니다. 원인을 고친 뒤 다시 "
            "실행하면 같은 사례를 이어서 게시합니다." % qname)
        if not dry:
            log("★ cases/%s.html 은 만들어진 채로 남아 있지만 커밋되지 않았습니다. "
                "다음 실행에서 -v2 를 새로 만들지 않고 이 파일을 다시 씁니다."
                % final_slug)
    else:
        log("==== 완료: %s (%s) ====" % (url, result))

    # GIT_NOT_FOUND 는 오류가 아니다. 수동 Push 로 복구 가능하므로 0 으로 끝낸다.
    # STAGE_FAILED / COMMIT_FAIL / PUSH_FAIL 은 반드시 0 이 아닌 값으로 끝낸다.
    return 0 if result in ("OK", "NO_CHANGE", "GIT_NOT_FOUND") else 1


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
