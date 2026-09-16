#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가치앤같이 사례 자동 게시 — git 실행 파일 탐색기 v1
====================================================
Git for Windows 가 설치되어 있지 않아 `git` 이 PATH 에 없어도,
GitHub Desktop 이 내장한 git.exe 를 찾아내서 자동화가 계속 동작하게 한다.

탐색 순서 (먼저 `git --version` 이 성공하는 것을 채택)
  1) automation/config/git_path_v1.txt 에 적힌 경로   -> Override
  2) PATH 위의 git                                    -> PATH
  3) GitHub Desktop 내장 git (cmd\\git.exe)            -> GitHubDesktop
  4) GitHub Desktop 내장 git (mingw64\\bin\\git.exe)   -> GitHubDesktop
  5) C:\\Program Files\\Git\\... 등 표준 설치 경로      -> ProgramFiles
  6) %LOCALAPPDATA%\\Programs\\Git\\cmd\\git.exe       -> LocalAppData

GitHub Desktop 의 app-<버전> 폴더 이름은 업데이트마다 바뀌므로 절대 하드코딩하지
않고, 실행할 때마다 glob 으로 찾아 버전 내림차순(최신 우선)으로 시도한다.

모듈로 쓰기
    from find_git_v1 import find_git
    exe = find_git()            # 문자열 경로 또는 None

명령줄로 쓰기
    python find_git_v1.py             # 경로 1줄 출력, 종료코드 0 / 못 찾으면 1
    python find_git_v1.py --source    # 출처 토큰 1줄 출력
    python find_git_v1.py --check     # 3줄 출력: 경로 / git --version / 출처

오류 메시지는 전부 표준오류(stderr)로만 내보낸다.
배치 파일이 `for /f ... 2^>nul` 로 표준출력만 읽어도 오염되지 않게 하기 위함이다.
"""
import glob
import os
import re
import subprocess
import sys

AUTO_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(AUTO_DIR, "config")
OVERRIDE_FILE = os.path.join(CONFIG_DIR, "git_path_v1.txt")

INSTALL_HINT = (
    "git 을 찾을 수 없습니다.\n"
    "  https://git-scm.com/download/win 에서 Git for Windows 를 설치하세요.\n"
    "  자세한 설치 방법: automation\\git_설치안내_v1.txt\n"
    "  이미 설치했는데도 안 잡히면 automation\\config\\git_path_v1.txt 에\n"
    "  git.exe 전체 경로를 한 줄로 적어 주세요."
)

# GitHub Desktop 내장 git (app-<버전> 폴더명은 업데이트마다 바뀐다)
GITHUB_DESKTOP_PATTERNS = (
    r"C:\Users\*\AppData\Local\GitHubDesktop\app-*\resources\app\git\cmd\git.exe",
    r"C:\Users\*\AppData\Local\GitHubDesktop\app-*\resources\app\git\mingw64\bin\git.exe",
)

PROGRAM_FILES_PATHS = (
    r"C:\Program Files\Git\cmd\git.exe",
    r"C:\Program Files\Git\bin\git.exe",
    r"C:\Program Files (x86)\Git\cmd\git.exe",
)

# Windows 에서 콘솔 창이 깜빡이지 않게 (작업 스케줄러/숨김 실행 대비)
if os.name == "nt":
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
else:
    _NO_WINDOW = 0


# ------------------------------------------------------------------ 내부 유틸
def _clean(line):
    """앞뒤 공백과 따옴표를 제거한다."""
    return (line or "").strip().strip('"').strip("'").strip()


def read_override():
    """config/git_path_v1.txt 에서 수동 지정 경로를 읽는다.

    비어 있거나 '#' 주석만 있으면 '설정 안 함'(None)으로 본다.
    """
    try:
        if not os.path.isfile(OVERRIDE_FILE):
            return None
        with open(OVERRIDE_FILE, "r", encoding="utf-8-sig", errors="replace") as f:
            raw = f.read()
    except Exception:
        return None
    for ln in raw.splitlines():
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        val = _clean(ln)
        if val:
            return val
    return None


def _version_key(path):
    """'app-3.4.13-beta1' 같은 폴더명에서 정렬용 숫자 튜플을 만든다."""
    m = re.search(r"app-([0-9][0-9A-Za-z.\-_]*)", path)
    if not m:
        return (0,)
    parts = []
    for chunk in re.split(r"[.\-_]", m.group(1)):
        parts.append(int(chunk) if chunk.isdigit() else 0)
    return tuple(parts) or (0,)


def _glob_sorted(pattern):
    """glob 결과를 버전 내림차순(최신 우선)으로 반환. 실패해도 예외를 내지 않는다."""
    try:
        hits = glob.glob(pattern)
    except Exception:
        return []
    hits = [h for h in hits if os.path.isfile(h)]
    try:
        hits.sort(key=lambda p: (_version_key(p), p), reverse=True)
    except Exception:
        hits.sort(reverse=True)
    return hits


def git_version(exe, timeout=25):
    """`<exe> --version` 을 실행해 출력 문자열을 반환. 실패하면 None."""
    if not exe:
        return None
    kw = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT, "timeout": timeout}
    if _NO_WINDOW:
        kw["creationflags"] = _NO_WINDOW
    try:
        p = subprocess.run([exe, "--version"], **kw)
    except Exception:
        return None
    if p.returncode != 0:
        return None
    out = p.stdout.decode("utf-8", "replace").strip().splitlines()
    return out[0].strip() if out else "git"


def _works(exe):
    return git_version(exe) is not None


def _path_git():
    """PATH 위의 git. shutil.which 로 먼저 찾고, 없으면 'git' 자체를 시도한다."""
    try:
        import shutil
        found = shutil.which("git")
        if found:
            return found
    except Exception:
        pass
    return "git"


def candidates():
    """(출처, 경로) 후보를 탐색 순서대로 만들어 낸다."""
    ov = read_override()
    if ov:
        yield ("Override", ov)

    yield ("PATH", _path_git())

    for pattern in GITHUB_DESKTOP_PATTERNS:
        for hit in _glob_sorted(pattern):
            yield ("GitHubDesktop", hit)

    for p in PROGRAM_FILES_PATHS:
        if os.path.isfile(p):
            yield ("ProgramFiles", p)

    local = os.environ.get("LOCALAPPDATA")
    if local:
        p = os.path.join(local, "Programs", "Git", "cmd", "git.exe")
        if os.path.isfile(p):
            yield ("LocalAppData", p)


def find_git_with_source():
    """(경로, 출처) 를 반환. 못 찾으면 (None, None)."""
    seen = set()
    for source, exe in candidates():
        key = os.path.normcase(exe)
        if key in seen:
            continue
        seen.add(key)
        # 절대경로 후보는 파일 존재 확인을 먼저 (헛된 실행 방지)
        if os.path.isabs(exe) and not os.path.isfile(exe):
            continue
        if _works(exe):
            return exe, source
    return None, None


def find_git():
    """사용 가능한 git 실행 파일 경로(str) 또는 None 을 반환한다."""
    return find_git_with_source()[0]


# ------------------------------------------------------------------ 명령줄
def main(argv):
    want_source = "--source" in argv
    want_check = "--check" in argv

    exe, source = find_git_with_source()
    if not exe:
        sys.stderr.write("[실패] " + INSTALL_HINT + "\n")
        return 1

    if want_source and not want_check:
        sys.stdout.write(source + "\n")
        return 0

    sys.stdout.write(exe + "\n")
    if want_check:
        sys.stdout.write((git_version(exe) or "git version 확인 실패") + "\n")
        sys.stdout.write(source + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
