#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 사례 자동 게시 — 사전 점검 v2
==========================================
점검_v1.bat 의 기능을 그대로 파이썬으로 옮긴 것이다.

왜 옮겼나
    cmd.exe 는 배치 파일을 실행할 때 "지금 몇 번째 바이트를 읽고 있는지"를
    기억했다가 명령이 끝날 때마다 그 위치로 되돌아간다. chcp 65001(UTF-8)
    상태에서 한글처럼 여러 바이트를 쓰는 글자가 배치 파일 안에 들어 있으면
    이 위치 계산이 어긋나서, 다음 줄의 중간부터 실행되는 일이 생긴다.
    ('t' is not recognized ... 같은 엉뚱한 오류가 이것 때문이다.)
    그래서 .bat 에는 ASCII 만 남기고, 한글 출력은 전부 파이썬이 맡는다.

실행
    automation\\점검_v2.bat  (권장)
    또는  py -3 automation\\check_v2.py

종료 코드는 항상 0 이다. 이 스크립트는 '보고서'이지 '관문'이 아니다.
"""
import os
import subprocess
import sys
from pathlib import Path

# ------------------------------------------------ 콘솔 인코딩 (한글 깨짐 방지)
# Windows 콘솔 코드페이지가 949 든 65001 이든 상관없이 UTF-8 로 내보낸다.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ------------------------------------------------------------------- 기본 경로
AUTO_DIR = Path(__file__).resolve().parent
REPO = AUTO_DIR.parent

QUEUE_DIR = AUTO_DIR / "queue"
REVIEW_DIR = AUTO_DIR / "review"
COUNTER_FILE = AUTO_DIR / "state" / "approval_counter_v1.txt"

TIMEOUT = 20            # 모든 외부 명령의 제한 시간(초)
AUTO_THRESHOLD = 10     # 승인 이만큼 쌓이면 완전 자동 게시로 전환

# 작업 스케줄러/숨김 실행에서 콘솔 창이 깜빡이지 않게
if os.name == "nt":
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
else:
    _NO_WINDOW = 0


def run(cmd, cwd=None, timeout=TIMEOUT):
    """외부 명령을 실행하고 (성공여부, 표준출력, 오류설명) 을 돌려준다.

    어떤 경우에도 예외를 밖으로 던지지 않는다.
    """
    kw = {"capture_output": True, "timeout": timeout}
    if cwd is not None:
        kw["cwd"] = str(cwd)
    if _NO_WINDOW:
        kw["creationflags"] = _NO_WINDOW
    try:
        p = subprocess.run(cmd, **kw)
    except FileNotFoundError:
        return False, "", "실행 파일을 찾을 수 없습니다."
    except subprocess.TimeoutExpired:
        return False, "", "%d초 안에 응답이 없어 중단했습니다." % timeout
    except Exception as exc:
        return False, "", "실행 중 오류가 났습니다: %s" % exc

    out = (p.stdout or b"").decode("utf-8", "replace").strip()
    err = (p.stderr or b"").decode("utf-8", "replace").strip()
    if p.returncode == 0:
        return True, out, ""
    return False, out, (err or out or "종료 코드 %s" % p.returncode)


def count_html(folder):
    """폴더 안의 *.html 개수. 폴더가 없으면 0."""
    try:
        return len([p for p in folder.glob("*.html") if p.is_file()])
    except Exception:
        return 0


def read_counter():
    """승인 누적 건수. 읽지 못하면 None."""
    try:
        txt = COUNTER_FILE.read_text(encoding="utf-8-sig", errors="replace").strip()
        return int(txt or "0")
    except Exception:
        return None


def line(text=""):
    print(text, flush=True)


# =============================================================== 본문
def main():
    line("============================================")
    line(" 가치앤같이 사례 자동게시 - 사전 점검 v2")
    line("============================================")
    line(" 저장소: %s" % REPO)
    line("============================================")
    line()

    index_html = REPO / "index.html"
    if not index_html.is_file():
        line("[실패] 저장소 폴더를 찾을 수 없습니다.")
        line("       이 파일은 저장소 안의 automation 폴더에 있어야 합니다.")
        line("       기대 위치: C:\\Users\\user\\Documents\\GitHub\\gaachi-website"
             "\\automation\\check_v2.py")
        line("       지금 위치: %s" % (AUTO_DIR / "check_v2.py"))
        line()
        line("[요약] index.html 을 찾지 못해 나머지 점검을 건너뜁니다.")
        return 0

    # ---------------------------------------------------- [1/5] Python
    line("[1/5] Python 확인")
    pyver = sys.version.split()[0]
    line("  [정상] Python %s" % pyver)
    line("         실행 파일: %s" % sys.executable)
    line("         실행 방식: 이 점검 스크립트가 지금 그 Python 으로 돌고 있습니다.")
    line("         상세 버전: %s" % " ".join(sys.version.split()))
    py_ok = True
    line()

    # ---------------------------------------------------- [2/5] Git
    line("[2/5] Git 확인")
    git_exe = None
    git_src = None
    git_ok = False
    if str(AUTO_DIR) not in sys.path:
        sys.path.insert(0, str(AUTO_DIR))
    try:
        from find_git_v1 import find_git_with_source, git_version
    except Exception as exc:
        line("  [실패] find_git_v1.py 를 불러오지 못했습니다: %s" % exc)
        line("         automation 폴더에 find_git_v1.py 가 있는지 확인하세요.")
    else:
        try:
            git_exe, git_src = find_git_with_source()
        except Exception as exc:
            git_exe, git_src = None, None
            line("  [실패] git 탐색 중 오류가 났습니다: %s" % exc)

        if not git_exe:
            line("  [실패] git 을 찾을 수 없습니다.")
            line("         https://git-scm.com/download/win 에서 설치하세요.")
            line("         설치 방법 요약: automation\\git_설치안내_v1.txt")
        else:
            git_ok = True
            try:
                ver = git_version(git_exe) or "git version 확인 실패"
            except Exception:
                ver = "git version 확인 실패"
            line("  [정상] %s" % ver)
            line("         경로: %s" % git_exe)
            line("         출처: %s" % git_src)
            if (git_src or "").lower() == "githubdesktop":
                line("  [참고] GitHub Desktop 내장 git 을 사용합니다. "
                     "버전 폴더(app-x.y.z)가 바뀌어도 자동으로 다시 찾으므로 "
                     "그대로 두셔도 됩니다.")
                line("         Git for Windows 를 설치하면 더 안정적입니다: "
                     "https://git-scm.com/download/win")
    line()

    # ---------------------------------------------------- [3/5] 자격증명
    line("[3/5] GitHub 자격증명 확인")
    cred_ok = False
    if not git_ok:
        line("  [건너뜀] git 이 없어 확인하지 못했습니다.")
    else:
        ok, _out, err = run([git_exe, "ls-remote", "origin", "-h"], cwd=REPO)
        if ok:
            cred_ok = True
            line("  [정상] GitHub 원격 저장소에 접근할 수 있습니다.")
        else:
            line("  [실패] GitHub 인증이 안 됩니다.")
            line("         - GitHub Desktop 을 열고 한 번 Push 해서 "
                 "로그인 상태를 만들어 주세요.")
            line("         - 그래도 안 되면 아래 명령을 한 번 실행하세요:")
            line('           "%s" config --global credential.helper manager' % git_exe)
            if err:
                line("         - git 이 남긴 말: %s" % err.splitlines()[0])
    line()

    # ---------------------------------------------------- [4/5] 미푸시 커밋
    line("[4/5] 미푸시 커밋 확인")
    ahead = None
    if not git_ok:
        line("  [건너뜀] git 이 없어 확인하지 못했습니다.")
        line("           GitHub Desktop 을 열면 푸시할 커밋이 있는지 바로 보입니다.")
    else:
        ok, out, _err = run(
            [git_exe, "rev-list", "--count", "origin/main..HEAD"], cwd=REPO)
        first = out.splitlines()[0].strip() if out else ""
        if ok and first.isdigit():
            ahead = int(first)
            line("  [정상] 로컬에만 있는 커밋: %d 건" % ahead)
            if ahead:
                line("         GitHub Desktop 을 열고 Push 를 눌러 주세요.")
        else:
            line("  [주의] 미푸시 커밋 수를 확인하지 못했습니다.")
            line("         origin/main 정보가 아직 없을 수 있습니다. "
                 "GitHub Desktop 에서 Fetch origin 을 한 번 눌러 주세요.")
    line()

    # ---------------------------------------------------- [5/5] 대기열
    line("[5/5] 대기열 상태")
    qcnt = count_html(QUEUE_DIR)
    rcnt = count_html(REVIEW_DIR)
    line("  게시 대기 queue 폴더: %d 건" % qcnt)
    line("  승인 대기 review 폴더: %d 건" % rcnt)

    counter = read_counter()
    if counter is None:
        line("  승인 누적 기록을 읽지 못했습니다: %s" % COUNTER_FILE)
        line("  (아직 승인을 한 번도 하지 않았다면 정상입니다.)")
        left = AUTO_THRESHOLD
    else:
        left = max(0, AUTO_THRESHOLD - counter)
        line("  승인 누적: %d 건 / 전환 기준 %d 건" % (counter, AUTO_THRESHOLD))
    if left > 0:
        line("  완전 자동 게시까지 남은 승인: %d 건" % left)
        line("  현재 단계: 승인 후 게시")
    else:
        line("  완전 자동 게시까지 남은 승인: 0 건")
        line("  현재 단계: 완전 자동 게시")
    line()

    # ---------------------------------------------------- [요약]
    line("============================================")
    line(" [요약]")
    blockers = []
    if not py_ok:
        blockers.append("Python 설치")
    if not git_ok:
        blockers.append("git 설치 또는 경로 지정")
    if not cred_ok:
        blockers.append("GitHub 자격증명(로그인)")

    if not blockers:
        line("  자동 게시를 사람이 지켜보지 않아도 돌릴 수 있는 상태입니다.")
        if ahead:
            line("  다만 아직 푸시하지 않은 커밋이 %d 건 있습니다. "
                 "GitHub Desktop 에서 Push 해 주세요." % ahead)
    else:
        line("  아직 무인 실행이 어렵습니다. 먼저 해결할 것: %s"
             % ", ".join(blockers))
    line("============================================")
    line()
    line(" 점검 완료")
    line()
    return 0


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:  # 어떤 일이 있어도 보고서는 끝까지 낸다
        try:
            line("[오류] 점검 중 예상치 못한 문제가 났습니다: %s" % exc)
        except Exception:
            pass
        rc = 0
    sys.exit(0 if rc is None else 0)
