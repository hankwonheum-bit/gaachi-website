#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 감정평가법인 — 초안 승인 도구 v1
==============================================
automation/review/ 에 쌓인 초안을 사람이 확인하고
  승인 -> automation/queue/ 로 이동 (다음 실행 때 자동 게시)
  반려 -> automation/rejected/ 로 이동 + 사유 파일 기록
한다.

원칙
  - 어떤 파일도 삭제하지 않는다. 이동(move)만 한다.
  - 대상 폴더에 같은 이름이 있으면 덮어쓰지 않고 중단한다.
  - 승인 시 automation/state/approval_counter_v1.txt 가 1 증가한다.
    이 값이 10 이상이 되면 생성기가 review 를 거치지 않고 queue 에 바로 쓴다.

사용법
  python approve_v1.py                                 # 대기 목록 보기
  python approve_v1.py --approve 011_gangnam-2026.html # 파일명으로 승인
  python approve_v1.py --approve 1                     # 목록 번호로 승인
  python approve_v1.py --reject 1 --reason "평가액 오기"
  python approve_v1.py --status                        # 승인 카운터 확인
"""
import argparse
import io
import os
import re
import shutil
import sys
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

REVIEW_DIR = os.path.join(HERE, "review")
QUEUE_DIR = os.path.join(HERE, "queue")
REJECTED_DIR = os.path.join(HERE, "rejected")
STATE_DIR = os.path.join(HERE, "state")

COUNTER_FILE = os.path.join(STATE_DIR, "approval_counter_v1.txt")
APPROVAL_LOG = os.path.join(STATE_DIR, "approval_log.tsv")
APPROVAL_LOG_HEADER = ("datetime_kst\taction\tfilename\tslug\tvalue_text"
                       "\tcounter_after\treason")

AUTO_THRESHOLD = 10  # 이 건수만큼 승인하면 완전 자동 게시로 전환


# ---------------------------------------------------------------- 유틸
def now_kst():
    return datetime.now(KST)


def stamp():
    return now_kst().strftime("%Y%m%d-%H%M%S")


def read_text(path):
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path, data):
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(data)


def read_counter():
    try:
        raw = read_text(COUNTER_FILE).strip().splitlines()[0].strip()
        return int(raw)
    except Exception:
        return 0


def write_counter(n):
    os.makedirs(STATE_DIR, exist_ok=True)
    write_text(COUNTER_FILE, "%d\n" % n)


def ensure_approval_log():
    os.makedirs(STATE_DIR, exist_ok=True)
    if not os.path.exists(APPROVAL_LOG):
        write_text(APPROVAL_LOG, APPROVAL_LOG_HEADER + "\n")


def append_approval_log(action, filename, slug, value_text, counter_after, reason):
    ensure_approval_log()
    row = "\t".join([now_kst().strftime("%Y-%m-%d %H:%M:%S"), action, filename,
                     slug or "-", value_text or "-", str(counter_after),
                     (reason or "-").replace("\t", " ").replace("\n", " ")])
    with io.open(APPROVAL_LOG, "a", encoding="utf-8") as f:
        f.write(row + "\n")


def meta_path_for(html_path):
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


def slug_of(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    return stem.split("_", 1)[1] if re.match(r"^\d+_", stem) else stem


def title_of(html, meta):
    if meta.get("seo_h2"):
        return meta["seo_h2"]
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).split("|")[0].split("—")[0].strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S | re.I)
    if m:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(1))).strip()
    return "(제목 없음)"


def value_of(html, meta):
    if meta.get("value_text"):
        return meta["value_text"]
    m = re.search(r"최종\s*감정평가액[^0-9]{0,40}?([0-9][0-9,]{6,})\s*원", html)
    if m:
        return m.group(1) + "원"
    m = re.search(r"class=[\"'][^\"']*final-value[^\"']*[\"'][^>]*>\s*([^<]{1,40})", html)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return "(확인 필요)"


def gijun_of(html, meta):
    if meta.get("gijun"):
        return meta["gijun"]
    m = re.search(r'<time[^>]+datetime=["\']([0-9]{4}-[0-9]{2}-[0-9]{2})["\']', html)
    return m.group(1) if m else "-"


# ---------------------------------------------------------------- 목록
def pending():
    if not os.path.isdir(REVIEW_DIR):
        return []
    out = []
    for f in sorted(os.listdir(REVIEW_DIR)):
        if not f.lower().endswith(".html"):
            continue
        p = os.path.join(REVIEW_DIR, f)
        html = read_text(p)
        meta = read_meta(meta_path_for(p))
        out.append({
            "filename": f,
            "path": p,
            "slug": slug_of(f),
            "title": title_of(html, meta),
            "value": value_of(html, meta),
            "gijun": gijun_of(html, meta),
            "has_meta": os.path.exists(meta_path_for(p)),
        })
    return out


def print_list(items=None):
    items = pending() if items is None else items
    c = read_counter()
    print("=" * 70)
    print("승인 대기 초안 — automation/review/")
    print("=" * 70)
    if not items:
        print("  (대기 중인 초안이 없습니다)")
    for i, it in enumerate(items, 1):
        print("  [%d] %s" % (i, it["filename"]))
        print("      제목      : %s" % it["title"])
        print("      최종평가액: %s" % it["value"])
        print("      기준시점  : %s" % it["gijun"])
        if not it["has_meta"]:
            print("      ⚠ meta.tsv 사이드카 없음 — 승인 전에 반드시 만들어야 합니다.")
    print("-" * 70)
    left = max(0, AUTO_THRESHOLD - c)
    print("현재 승인 누적: %d건 / 전환 기준 %d건" % (c, AUTO_THRESHOLD))
    if left > 0:
        print("완전 자동 게시까지 남은 승인: %d건" % left)
    else:
        print("완전 자동 게시 단계입니다(초안이 queue 로 바로 들어갑니다).")
    print("=" * 70)
    return items


def resolve_target(items, key):
    """숫자(목록 번호) 또는 파일명으로 항목을 찾는다."""
    if key is None:
        return None
    key = str(key).strip()
    if re.fullmatch(r"\d+", key):
        i = int(key)
        if 1 <= i <= len(items):
            return items[i - 1]
        return None
    base = os.path.basename(key)
    for it in items:
        if it["filename"] == base:
            return it
    # 확장자 생략 허용
    for it in items:
        if os.path.splitext(it["filename"])[0] == os.path.splitext(base)[0]:
            return it
    return None


def move_no_overwrite(src, dst_dir, label):
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst):
        raise RuntimeError("%s 에 같은 이름이 이미 있습니다: %s (덮어쓰지 않고 중단)"
                           % (label, os.path.basename(src)))
    shutil.move(src, dst)
    return dst


# ---------------------------------------------------------------- 승인 / 반려
def run_validator(html_path):
    """validate_draft_v1.py 가 있으면 검증한다. 반환 (ok, 출력문자열)"""
    vp = os.path.join(HERE, "validate_draft_v1.py")
    if not os.path.exists(vp):
        return True, "(validate_draft_v1.py 없음 — 검증 생략)"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("validate_draft_v1", vp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        errs, warns, stats = mod.validate_draft(html_path)
        return (not errs), mod.report(html_path, errs, warns, stats)
    except Exception as e:
        return False, "검증기 실행 실패: %s" % e


def approve(key, force=False):
    items = pending()
    it = resolve_target(items, key)
    if not it:
        print("승인 대상을 찾지 못했습니다: %s" % key)
        print_list(items)
        return 1

    ok, rep = run_validator(it["path"])
    print(rep)
    if not ok and not force:
        print("검증 오류가 있어 승인을 중단합니다. 초안을 고친 뒤 다시 실행하십시오.")
        print("(검증을 무시하고 강제 승인하려면 --force 를 붙이십시오. 권장하지 않습니다.)")
        return 1
    if not ok:
        print("⚠ --force 지정으로 검증 오류를 무시하고 승인합니다.")

    mpath = meta_path_for(it["path"])
    if not os.path.exists(mpath):
        print("meta.tsv 사이드카가 없습니다: %s" % os.path.basename(mpath))
        print("게시 카드(index.html)가 부정확해지므로 승인을 중단합니다.")
        return 1

    try:
        dst_html = move_no_overwrite(it["path"], QUEUE_DIR, "automation/queue")
        dst_meta = move_no_overwrite(mpath, QUEUE_DIR, "automation/queue")
    except Exception as e:
        print("이동 실패: %s" % e)
        return 1

    c = read_counter() + 1
    write_counter(c)
    append_approval_log("APPROVE", it["filename"], it["slug"], it["value"], c, "-")

    print("")
    print("승인 완료: %s" % it["filename"])
    print("  -> %s" % os.path.relpath(dst_html, REPO).replace("\\", "/"))
    print("  -> %s" % os.path.relpath(dst_meta, REPO).replace("\\", "/"))
    print("  다음 자동 게시 실행(automation/run_daily_v1.bat) 때 사이트에 올라갑니다.")
    left = max(0, AUTO_THRESHOLD - c)
    print("")
    print("승인 누적 %d건 / %d건" % (c, AUTO_THRESHOLD))
    if left > 0:
        print("완전 자동 게시까지 남은 승인: %d건" % left)
    else:
        print("★ 승인 %d건을 채웠습니다. 이후 초안은 review 를 거치지 않고 queue 로 직행합니다."
              % AUTO_THRESHOLD)
    return 0


def reject(key, reason):
    items = pending()
    it = resolve_target(items, key)
    if not it:
        print("반려 대상을 찾지 못했습니다: %s" % key)
        print_list(items)
        return 1
    if not reason or not reason.strip():
        print("반려 사유(--reason)를 반드시 적어야 합니다. 다음 생성 때 같은 실수를 막는 근거가 됩니다.")
        return 1

    os.makedirs(REJECTED_DIR, exist_ok=True)
    base = it["filename"]
    dst = os.path.join(REJECTED_DIR, base)
    if os.path.exists(dst):
        base = "%s-%s" % (stamp(), it["filename"])
        dst = os.path.join(REJECTED_DIR, base)
    shutil.move(it["path"], dst)

    mpath = meta_path_for(it["path"])
    if os.path.exists(mpath):
        mdst = os.path.join(REJECTED_DIR, os.path.basename(mpath))
        if os.path.exists(mdst):
            mdst = os.path.join(REJECTED_DIR,
                                "%s-%s" % (stamp(), os.path.basename(mpath)))
        shutil.move(mpath, mdst)

    write_text(dst + ".reason.txt",
               "반려 시각: %s\n원본: %s\n슬러그: %s\n최종평가액: %s\n\n[반려 사유]\n%s\n"
               % (now_kst().isoformat(), it["filename"], it["slug"],
                  it["value"], reason.strip()))
    append_approval_log("REJECT", it["filename"], it["slug"], it["value"],
                        read_counter(), reason.strip())
    print("반려 완료: %s -> automation/rejected/%s" % (it["filename"], base))
    print("사유 파일: automation/rejected/%s.reason.txt" % base)
    print("※ 승인 카운터는 올라가지 않습니다(현재 %d건)." % read_counter())
    return 0


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description="가치앤같이 초안 승인 도구 v1")
    ap.add_argument("--approve", help="승인할 초안(파일명 또는 목록 번호)")
    ap.add_argument("--reject", help="반려할 초안(파일명 또는 목록 번호)")
    ap.add_argument("--reason", help="반려 사유 (--reject 와 함께 필수)")
    ap.add_argument("--force", action="store_true", help="검증 오류를 무시하고 승인(비권장)")
    ap.add_argument("--list", action="store_true", help="대기 목록만 출력")
    ap.add_argument("--status", action="store_true", help="승인 카운터만 출력")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    os.makedirs(REVIEW_DIR, exist_ok=True)

    if args.status:
        c = read_counter()
        print("승인 누적: %d건 / 전환 기준 %d건 · 남은 승인 %d건"
              % (c, AUTO_THRESHOLD, max(0, AUTO_THRESHOLD - c)))
        print("현재 단계: %s" % ("승인 후 게시" if c < AUTO_THRESHOLD else "완전 자동 게시"))
        return 0
    if args.reject:
        return reject(args.reject, args.reason)
    if args.approve:
        return approve(args.approve, force=args.force)
    print_list()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("치명적 오류: %s" % exc)
        sys.exit(2)
