"""
가치앤같이 감정평가법인 — Google Search Console 색인 요청 스크립트
사용법: python gsc_index.py
"""

import json
import time
import urllib.request
import urllib.error
import ssl
import sys
import os

# ============================================================
# 설정: 색인 요청할 URL 목록 (매번 여기에 추가)
# ============================================================
URLS_TO_INDEX = [
    "https://gaachi.co.kr/cases/dongjak-daebang-epyeonhansesang-2026.html",
    "https://gaachi.co.kr/cases/mapo-ahyeondong-2025.html",
    # 다음 작업 시 아래에 URL 추가:
    # "https://gaachi.co.kr/cases/다음-파일명.html",
]

# 서비스 계정 JSON 파일 경로 (이 스크립트와 같은 폴더에 있어야 함)
KEY_FILE = os.path.join(os.path.dirname(__file__), "seraphic-being-493407-k0-e942184375bc.json")
SCOPE = "https://www.googleapis.com/auth/indexing"
TOKEN_URI = "https://oauth2.googleapis.com/token"
INDEX_URI = "https://indexing.googleapis.com/v3/urlNotifications:publish"
# ============================================================


def get_access_token(sa: dict) -> str:
    try:
        import jwt
    except ImportError:
        print("[오류] PyJWT 라이브러리가 없습니다. 아래 명령어로 설치 후 다시 실행하세요:")
        print("  pip install PyJWT cryptography")
        sys.exit(1)

    now = int(time.time())
    payload = {
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URI,
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, sa["private_key"], algorithm="RS256")
    data = f"grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Ajwt-bearer&assertion={token}".encode()
    req = urllib.request.Request(TOKEN_URI, data=data,
                                  headers={"Content-Type": "application/x-www-form-urlencoded"})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def request_index(url: str, access_token: str) -> dict:
    payload = json.dumps({"url": url, "type": "URL_UPDATED"}).encode()
    req = urllib.request.Request(INDEX_URI, data=payload,
                                  headers={"Content-Type": "application/json",
                                           "Authorization": f"Bearer {access_token}"})
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "message": e.read().decode()}


def main():
    print("=" * 60)
    print("  가치앤같이 — Google 색인 요청")
    print("=" * 60)

    if not os.path.exists(KEY_FILE):
        print(f"[오류] 서비스 계정 키 파일을 찾을 수 없습니다:\n  {KEY_FILE}")
        print("이 스크립트와 같은 폴더에 JSON 키 파일을 넣어주세요.")
        input("\nEnter 키를 눌러 종료...")
        sys.exit(1)

    with open(KEY_FILE) as f:
        sa = json.load(f)

    print(f"\n서비스 계정: {sa['client_email']}")
    print(f"요청 URL 수: {len(URLS_TO_INDEX)}개\n")

    print("액세스 토큰 발급 중...", end=" ", flush=True)
    try:
        access_token = get_access_token(sa)
        print("완료")
    except Exception as e:
        print(f"\n[오류] 토큰 발급 실패: {e}")
        input("\nEnter 키를 눌러 종료...")
        sys.exit(1)

    print()
    for url in URLS_TO_INDEX:
        print(f"요청 중: {url}")
        result = request_index(url, access_token)
        if "error" in result:
            print(f"  → 실패 ({result['error']}): {result.get('message', '')}")
        else:
            notify = result.get("urlNotificationMetadata", {})
            latest = notify.get("latestUpdate", {})
            print(f"  → 성공! 처리시각: {latest.get('notifyTime', '-')}")
        print()

    print("=" * 60)
    print("  완료. Google 색인 반영까지 수일~2주 소요됩니다.")
    print("=" * 60)
    input("\nEnter 키를 눌러 종료...")


if __name__ == "__main__":
    main()
