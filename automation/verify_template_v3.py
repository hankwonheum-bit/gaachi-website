# -*- coding: utf-8 -*-
"""템플릿 ↔ 필드정의 정합성 검증기 (읽기 전용) — 버전 무관.

파일명의 `v3` 는 최초 작성 시점(2026-09-16, case_template_v3 대상)의 잔재입니다.
이 도구는 인자로 받은 두 파일만 서로 비교하므로 어느 버전 조합에도 그대로 동작합니다.
현행(2026-09-29 기준)은 case_template_v6.html <-> 필드정의_v5.tsv 를 검증합니다.
개명하지 않습니다 — 파일명을 참조하는 문서가 9곳(폐기된 구버전 포함)이고,
저장소의 파일 삭제·개명 금지 관례와 부딪히기 때문입니다.

사용법: python3 automation/verify_template_v3.py <템플릿.html> <필드정의.tsv>
현행 예: python3 automation/verify_template_v3.py templates/case_template_v6.html templates/필드정의_v5.tsv
"""
import io, json, re, sys

def main():
    tpl_path, tsv_path = sys.argv[1], sys.argv[2]
    raw = io.open(tpl_path, 'rb').read()
    try:
        h = raw.decode('utf-8')
        enc = 'UTF-8 OK (BOM %s)' % ('있음' if raw[:3] == b'\xef\xbb\xbf' else '없음')
    except UnicodeDecodeError as e:
        print('✗ UTF-8 디코드 실패:', e); sys.exit(1)

    errs, out = [], []
    out.append('[1] 인코딩          : ' + enc)

    # 2) 토큰 형식 일관성
    loose = re.findall(r'\{\{[^}]{0,80}\}\}', h)
    bad = [t for t in loose if not re.fullmatch(r'\{\{[A-Z][A-Z0-9_]*\}\}', t)]
    tpl_tokens, seen = [], set()
    for m in re.finditer(r'\{\{([A-Z][A-Z0-9_]*)\}\}', h):
        if m.group(1) not in seen:
            seen.add(m.group(1)); tpl_tokens.append(m.group(1))
    out.append('[2] 토큰 형식       : 총 %d회 출현 / 고유 %d개 / 형식위반 %d건 %s'
               % (len(loose), len(tpl_tokens), len(bad), bad if bad else ''))
    if bad: errs.append('토큰 형식 위반 %d건' % len(bad))
    if re.search(r'\{\s*\{|\}\s*\}(?!\})', h) and not loose:
        errs.append('토큰 구분자 이상')

    # 3) JSON-LD
    blocks = re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', h, re.S)
    types = []
    for i, b in enumerate(blocks, 1):
        probe = re.sub(r'\{\{[A-Z][A-Z0-9_]*\}\}', 'X', b)
        try:
            d = json.loads(probe)
            types.append(d.get('@type'))
        except Exception as e:
            errs.append('JSON-LD %d번 파싱 실패: %s' % (i, e)); types.append('PARSE_FAIL')
    out.append('[3] JSON-LD         : %d블록 %s' % (len(blocks), types))
    if len(blocks) != 3: errs.append('JSON-LD 블록이 3개가 아님(%d)' % len(blocks))
    for need in ('Article', 'FAQPage', 'BreadcrumbList'):
        if need not in types: errs.append('JSON-LD %s 없음' % need)

    # 4) 제목 구조
    h1 = len(re.findall(r'<h1[\s>]', h)); h2 = len(re.findall(r'<h2[\s>]', h)); h3 = len(re.findall(r'<h3[\s>]', h))
    out.append('[4] 제목 구조       : h1 %d · h2 %d · h3 %d' % (h1, h2, h3))
    if h1 != 1: errs.append('h1 이 %d개(1개여야 함)' % h1)
    if h2 < 3: errs.append('h2 가 %d개(3개 이상)' % h2)
    if h3 < 1: errs.append('h3 가 %d개(1개 이상)' % h3)

    # 5) 숨김 텍스트 패턴
    pats = {'font-size:1px': r'font-size\s*:\s*1px',
            'color:var(--bg)': r'color\s*:\s*var\(--bg\)',
            'display:none(인라인)': r'style\s*=\s*["\'][^"\']*display\s*:\s*none',
            '화면밖 배치': r'(text-indent\s*:\s*-\d{3,}|left\s*:\s*-\d{4,}px|clip\s*:\s*rect)'}
    hid = {k: len(re.findall(v, h, re.I)) for k, v in pats.items()}
    out.append('[5] 숨김 텍스트     : ' + ' / '.join('%s %d건' % (k, v) for k, v in hid.items()))
    if sum(hid.values()): errs.append('숨김 텍스트 패턴 %d건' % sum(hid.values()))

    # 6) 태그 균형
    void = {'meta','link','br','img','input','hr','source','area','base','col','embed','param','track','wbr'}
    stack, imbalance = [], []
    body = re.sub(r'<!--.*?-->', '', h, flags=re.S)
    body = re.sub(r'<script.*?</script>|<style.*?</style>', '', body, flags=re.S)
    for m in re.finditer(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)([^>]*?)(/?)>', body):
        close, name, attrs, selfc = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        if name in void or selfc == '/' or name == '!doctype': continue
        if close:
            if stack and stack[-1] == name: stack.pop()
            else: imbalance.append('</%s>' % name)
        else:
            stack.append(name)
    out.append('[6] 태그 균형       : 미닫힘 %s / 짝없는 닫힘 %s' % (stack if stack else '0건', imbalance if imbalance else '0건'))
    if stack or imbalance: errs.append('HTML 태그 불균형')

    # 7) 폐지 규칙 잔재
    dead = {'Person 저자': r'"@type"\s*:\s*"Person"',
            'hasCredential': r'hasCredential',
            'APPRAISER_NAME': r'APPRAISER_NAME',
            '가치형성요인': r'단지외부요인|단지내부요인|호별요인',
            '소급감정 시사': r'신고기한을 역산'}
    left = {k: len(re.findall(v, h)) for k, v in dead.items()}
    out.append('[7] v2 폐지규칙 잔재: ' + ' / '.join('%s %d' % (k, v) for k, v in left.items()))
    if sum(left.values()): errs.append('폐지된 v2 규칙 잔재 %d건' % sum(left.values()))
    # 7-1) 층·호 마스킹(오너 확정 2026-09-30 / **2026-10-13 표기 축약**): 평문 O 기호만 쓴다.
    #      CSS 스팬(.addr-mask)과 블록문자(█·▇·■)는 소스 노출·스타일 제거로 자리수가 드러나 폐지.
    #      2026-10-13 소유자 지시로 신 기호는 `O층`·`OO호`(붙여 쓰면 `O층OO호`) 가 되었다.
    #      구 기호에는 자릿수를 맞춘 구 표기 `제OO층`·`OOO호` 도 포함된다.
    #      `제OO층` 은 `O층` 을, `OOO호` 는 `OO호` 를 부분문자열로 포함하므로
    #      신 기호는 **구 표기를 지운 사본**에서 센다(그냥 세면 구 표기가 신 기호로 오인된다).
    mask_old = (len(re.findall(r'addr-mask', h)) + len(re.findall(r'[\u2588\u2587\u25a0]', h))
                + h.count('제OO층') + h.count('OOO호'))
    h_nm = h.replace('제OO층', ' ').replace('OOO호', ' ')
    mask_new = h_nm.count('O층') + h_nm.count('OO호')
    out.append('[7-1] 층·호 마스킹   : 구 기호(addr-mask/█/▇/■/제OO층/OOO호) %d건 / 신 기호(O층·OO호) %d건 / 층·호 토큰 %s'
               % (mask_old, mask_new, 'FLOOR_MASKED·UNIT_MASKED 있음' if ('FLOOR_MASKED' in h and 'UNIT_MASKED' in h) else '없음'))
    if mask_old: errs.append('구 마스킹 기호(addr-mask/█/▇/■/제OO층/OOO호) 잔존 %d건 — 평문 `O층OO호` 로 교체할 것' % mask_old)

    # 8) 필드정의 ↔ 템플릿 토큰 1:1 · 순서 일치
    rows = [l.rstrip('\n').split('\t') for l in io.open(tsv_path, encoding='utf-8') if l.strip()]
    hdr, data = rows[0], rows[1:]
    tsv_tokens = [r[0] for r in data]
    colbad = [r[0] for r in data if len(r) != 5]
    out.append('[8] 필드정의 헤더   : %s (열 %d개) / 5열 아닌 행 %s' % (hdr, len(hdr), colbad if colbad else '0건'))
    if hdr != ['token', '설명', '예시', '필수여부', '마스킹규칙']: errs.append('TSV 헤더 불일치')
    if colbad: errs.append('TSV 열 수 불일치 %d행' % len(colbad))

    only_tpl = [t for t in tpl_tokens if t not in tsv_tokens]
    only_tsv = [t for t in tsv_tokens if t not in tpl_tokens]
    dup = sorted({t for t in tsv_tokens if tsv_tokens.count(t) > 1})
    order_ok = (tpl_tokens == tsv_tokens)
    out.append('[9] 토큰 집합       : 템플릿 %d개 / 필드정의 %d개' % (len(tpl_tokens), len(tsv_tokens)))
    out.append('    템플릿에만      : %s' % (only_tpl if only_tpl else '0건'))
    out.append('    필드정의에만    : %s' % (only_tsv if only_tsv else '0건'))
    out.append('    TSV 중복        : %s' % (dup if dup else '0건'))
    out.append('    출현순서 일치   : %s' % ('예 (1:1·순서 일치)' if order_ok else '아니오'))
    if only_tpl or only_tsv or dup: errs.append('토큰 집합 불일치')
    if not order_ok and not (only_tpl or only_tsv):
        first = next(i for i, (a, b) in enumerate(zip(tpl_tokens, tsv_tokens)) if a != b)
        errs.append('토큰 순서 불일치 (첫 어긋남 %d번째: 템플릿 %s vs TSV %s)' % (first + 1, tpl_tokens[first], tsv_tokens[first]))

    # 10) 분량
    nostyle = re.sub(r'<style.*?</style>|<script.*?</script>', '', h, flags=re.S)
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', re.sub(r'<!--.*?-->', '', nostyle, flags=re.S)))
    out.append('[10] 분량           : 전체 %d bytes / 본문(태그포함) %d bytes / 텍스트 %d자'
               % (len(h.encode('utf-8')), len(nostyle.encode('utf-8')), len(text)))

    print('\n'.join(out))
    print('-' * 64)
    if errs:
        print('✗ 오류 %d건' % len(errs))
        for e in errs: print('  -', e)
        sys.exit(1)
    print('✓ 오류 0건 — 검증 통과')

main()
