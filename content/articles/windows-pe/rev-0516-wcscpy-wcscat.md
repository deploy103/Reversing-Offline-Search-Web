---
id: REV-0516
title: "Windows CRT 문자열 함수 사전: wcscpy wcscat 계열(와이드 문자)"
slug: "rev-0516-wcscpy-wcscat"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["wcscpy", "wcscat", "wcslen", "wcscmp", "wcsncpy", "와이드 문자열", "UTF-16", "CRT"]
aliases: ["wide string CRT 함수", "wcs 계열 함수", "유니코드 문자열 복사 함수"]
symptom_keywords: ["wcscpy가 뭔지 모르겠다", "wcscat 인자 순서를 모르겠다", "유니코드 문자열 함수가 어떻게 다른지 모르겠다", "wcslen이 바이트 수인지 문자 수인지 헷갈린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`wcscpy`/`wcscat`/`wcslen`/`wcscmp` 등 `wcs` 접두사가 붙은 CRT 함수들은 `strcpy`/`strcat`/`strlen`/`strcmp`와 기능은 완전히 같지만 1바이트(`char`) 대신 2바이트(`wchar_t`, UTF-16LE) 단위로 문자열을 다루므로, IDA/x64dbg에서 이 함수들이 보이면 반드시 덤프를 "UTF-16"으로 보고 길이도 "문자 수"가 아니라 "문자 수 × 2바이트"로 계산해야 한다.

## 언제 검색해야 하나
- 임포트 목록에서 `wcscpy`, `wcscat`, `wcsncpy`, `wcslen`, `wcscmp` 등 `wcs`로 시작하는 함수를 발견했을 때
- 덤프 창에 문자열이 보여야 할 자리에 한 글자씩 건너뛴 이상한 바이트가 보일 때(ANSI 모드로 보고 있어서)
- `strcpy` 계열과 `wcscpy` 계열의 버퍼 크기 계산이 왜 다른지 헷갈릴 때

## 핵심 개념
Windows CRT(`msvcrt.dll`, `ucrtbase.dll`, 정적 링크 시 `.text` 내부)는 문자열을 다루는 함수를 두 세트로 제공한다.

| 좁은 문자(char, 1바이트) | 넓은 문자(wchar_t, 2바이트) | 기능 |
|---|---|---|
| `strcpy` | `wcscpy` | NUL까지 복사 |
| `strcat` | `wcscat` | 뒤에 이어붙임 |
| `strlen` | `wcslen` | 길이(문자 개수) 반환 |
| `strcmp` | `wcscmp` | 사전식 비교 |
| `strncpy` | `wcsncpy` | 최대 n개까지 복사 |
| `strncat` | `wcsncat` | 최대 n개까지 이어붙임 |
| `strstr` | `wcsstr` | 부분 문자열 검색 |
| `strchr` | `wcschr` | 문자 검색 |

`wchar_t`는 Windows에서 2바이트(UTF-16 코드 유닛)로 정의된다(리눅스의 4바이트 `wchar_t`와 다름에 유의). 따라서 `wcslen(L"AB")`은 문자 개수인 `2`를 반환하지만, 실제 메모리에서 이 문자열이 차지하는 바이트 수는 NUL 포함 `6`바이트(`A`=0x0041, `B`=0x0042, NUL=0x0000)이다.

```c
wchar_t *wcscpy(wchar_t *dest, const wchar_t *src);   // src를 dest로 복사(NUL 포함)
wchar_t *wcscat(wchar_t *dest, const wchar_t *src);   // dest 끝(NUL 위치)에 src를 이어붙임
size_t   wcslen(const wchar_t *str);                  // NUL 이전까지의 wchar_t 개수(바이트 아님)
int      wcscmp(const wchar_t *s1, const wchar_t *s2);// 같으면 0
wchar_t *wcsncpy(wchar_t *dest, const wchar_t *src, size_t n); // 최대 n개 wchar_t만 복사
```

보안 강화 버전(`_s` 접미사)도 존재한다: `wcscpy_s(dest, destSize, src)`처럼 대상 버퍼 크기를 명시적으로 받아 오버플로를 막는다. 이 `destSize` 인자 역시 "바이트 수"가 아니라 "wchar_t 개수"임에 주의해야 한다(REV-0515의 `strcpy_s`/`sprintf_s`와 개념은 동일, 단위만 다름).

## 화면/코드에서 보이는 징후
- IDA 임포트 창에 `wcscpy`, `wcscat`, `wcslen` 등이 나열되고, Hex-Rays 디컴파일 결과에 `L"..."` 형태(앞에 `L`이 붙은 리터럴)의 문자열 인자가 보임
- x64dbg 덤프 창에서 문자열이 있어야 할 위치에 `41 00 42 00 43 00 00 00`처럼 각 문자 뒤에 `00`이 끼어 있는 패턴(ANSI로 보면 글자 사이가 비어 보이거나 깨져 보임)
- `wcslen` 반환값을 그대로 `malloc`이나 `memcpy`의 바이트 수 인자로 사용하지 않고 `* 2` 또는 `* sizeof(wchar_t)`를 곱하는 코드가 함께 나타남

## 가장 먼저 할 것
1. x64dbg 덤프 창에서 문자열이 안 보이거나 이상하게 보이면 덤프 창 우클릭 → "UTF-16" 표시로 바꾼다.
2. `wcslen`/`wcscpy` 호출 시 인자로 들어가는 버퍼 주소를 확인하고, 그 주소를 덤프에서 "Follow in Dump"로 열어 실제 유니코드 문자열을 읽는다.
3. 버퍼 크기 계산 코드가 있으면 곱해지는 숫자가 `1`이 아니라 `2`(또는 `sizeof(wchar_t)`)인지 확인해서 ANSI/와이드 혼동을 피한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `wcscpy`(또는 `wcscpy_s`, `wcscat_s`)를 찾아 `X`로 교차 참조를 확인한다.
- Hex-Rays(`F5`)에서 첫 번째 인자(`dest`)와 두 번째 인자(`src`)를 확인한다. `src`가 문자열 리터럴이면 `L"..."` 형태로 바로 보인다.

**2) 동적 분석(x64dbg)**
- `bp wcscpy` 또는 `bp wcscat`으로 브레이크포인트를 건다.
- x64에서는 `RCX`=dest, `RDX`=src(2인자 함수 기준). x86에서는 `[esp+4]`=dest, `[esp+8]`=src.
- `RDX`(또는 `[esp+8]`)를 "Follow in Dump" 한 뒤 덤프 창을 UTF-16으로 전환해 실제 문자열을 읽는다.

## 명령어/단축키
- x64dbg: `bp wcscpy`, `bp wcscat`, `bp wcslen`
- x64dbg 덤프 창 우클릭 → "UTF-16" (문자열 표시 인코딩 전환)
- IDA: `X`(교차 참조), `F5`(디컴파일)

## 출력 해석
- `wcscpy`/`wcscat`는 반환값으로 `dest` 포인터를 그대로 돌려준다(성공 실패 판단용이 아니라 체이닝용).
- `wcslen`의 반환값은 "문자 개수"이며, 실제 메모리 크기를 계산하려면 `(반환값 + 1) * 2`바이트(NUL 포함)로 환산해야 한다.
- `wcscmp` 반환값이 `0`이면 완전히 동일한 문자열이라는 뜻으로, flag 검증 로직에서 흔히 등장한다.

## 흔한 실수
- ANSI 덤프 모드로 유니코드 버퍼를 보고 "문자열이 깨졌다"고 오해하는 것. 반드시 UTF-16 표시로 전환해야 한다.
- `wcslen` 반환값을 그대로 `malloc` 바이트 수로 써서 버퍼가 실제 필요한 크기의 절반만 할당되는 것으로 착각하는 것(실제 코드가 이렇게 버그를 가진 경우도 있으니, 반대로 이 패턴이 보이면 오버플로 취약점 후보로 의심해야 한다).
- `wcscpy_s`의 두 번째 인자(버퍼 크기)를 바이트 수로 착각하는 것. 이 인자는 wchar_t 개수 기준이다.
- `strcpy`와 `wcscpy`를 섞어서 문자열을 다루면 문자 사이에 `00`이 끼어 예상과 다른 결과가 나오는 것을 디버깅하지 못하는 것.

## 막혔을 때 다음 체크
- ANSI/좁은 문자 버전 함수의 인자 규약이 궁금하면 → REV-0515(strcpy_s sprintf_s)를 먼저 본다.
- 문자열이 애초에 ANSI인지 UTF-16인지 구분하는 법 자체가 궁금하면 → REV-0128(Windows 문자열 ASCII와 UTF-16 찾기)을 본다.
- `memcpy_s`처럼 문자열이 아닌 원시 메모리 복사 함수와 헷갈린다면 → REV-0517(memcpy_s memmove_s)을 본다.

## 미니 예제
x64dbg에서 `bp wcscat` 후 실행하니 다음처럼 멈췄다.

```text
RCX = 0x0000000000403050   (dest, 이미 L"flag: " 저장되어 있음)
RDX = 0x000001A2B4C01000   (src)
```

`RDX`를 Follow in Dump 하고 UTF-16으로 전환하면 `L"CTF{w1de_str1ng}"`가 보인다. `wcscat` 실행 후 `dest`를 다시 확인하면 `L"flag: CTF{w1de_str1ng}"`로 이어붙여진 것을 확인할 수 있다.

참고로 Windows API 계열(Win32 함수)은 대부분 이름 끝에 `A`(ANSI)나 `W`(Wide, UTF-16) 접미사가 붙은 두 가지 버전으로 존재하지만(예: `CreateFileA`/`CreateFileW`), CRT의 `wcs` 계열 함수는 이런 A/W 접미사 구분이 아니라 애초에 `wchar_t*`(넓은 문자 포인터)만 받는 별도 함수 이름 체계라는 점에서 다르다. IDA는 임포트 라이브러리 정보를 인식하면 `wcscpy`처럼 접미사가 없는 이름 그대로 표시하므로, `strcpy`와 `wcscpy`가 이름부터 아예 다른 함수라는 사실을 헷갈리지 않도록 주의해야 한다.

## 관련 글
- REV-0515 — Windows CRT 문자열 함수 사전: strcpy_s sprintf_s
- REV-0517 — Windows CRT 메모리 함수 사전: memcpy_s memmove_s
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `wcscpy`/`wcscat`/`wcslen`/`wcscmp` 등의 함수 시그니처와 동작은 Microsoft C 런타임 라이브러리(CRT) 공식 문서 기준이다.
- Windows `wchar_t`가 2바이트(UTF-16 코드 유닛)로 정의된다는 사실은 Microsoft C++ 언어/CRT 문서 기준이다.
- 위 미니 예제의 주소와 문자열은 설명용으로 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
