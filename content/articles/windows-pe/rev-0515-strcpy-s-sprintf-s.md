---
id: REV-0515
title: "Windows CRT 문자열 함수 사전: strcpy_s sprintf_s"
slug: "rev-0515-strcpy-s-sprintf-s"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["strcpy_s", "sprintf_s", "Secure CRT", "errno_t", "버퍼 오버플로우", "_GS 스택 보호"]
aliases: ["안전한 문자열 복사 함수", "스트카피에스", "스프린트에프에스", "Secure CRT 함수"]
symptom_keywords: ["strcpy_s가 strcpy와 뭐가 다른지 모르겠다", "sprintf_s 인자에 버퍼 크기가 왜 있는지 모르겠다", "errno_t 반환값이 뭔지 모르겠다", "이 바이너리는 버퍼오버플로우가 안 되는 것 같다", "C4996 경고가 왜 뜨는지 궁금하다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strcpy_s`/`sprintf_s`는 기존 `strcpy`/`sprintf`에 목적지 버퍼 크기 인자를 추가로 요구하는 Microsoft Secure CRT 함수로, 이 이름들이 Import/문자열에 보인다면 컴파일러가 버퍼 크기 검사를 강제하고 있다는 뜻이므로 (같은 지점에서) 고전적인 `strcpy` 스타일 오버플로우를 찾기는 더 어렵지만, 대신 크기 인자 자체가 잘못 계산되는 2차적인 취약점 패턴을 봐야 한다.

## 언제 검색해야 하나
- Import 목록이나 IDA 디컴파일 결과에 `strcpy_s`/`sprintf_s`/`strncpy_s` 등 `_s` 접미사가 붙은 함수가 보여서 일반 `strcpy`/`sprintf`와 무엇이 다른지 알아야 할 때
- CTF pwn/리버싱 문제에서 이 바이너리가 Secure CRT를 쓰는지 확인해 오버플로우 공략 가능성을 가늠해야 할 때
- `sprintf_s`의 크기 인자와 포맷 문자열이 실제로 만들어내는 최대 길이가 목적지 버퍼보다 큰지 검토해야 할 때
- Visual Studio 소스 코드에서 `C4996`(이 함수는 안전하지 않을 수 있습니다) 경고를 보고 왜 뜨는지, `_s` 버전과 무슨 관계인지 궁금할 때

## 핵심 개념

### 함수 시그니처
```c
errno_t strcpy_s(
    char       *strDestination,    // 1. 복사될 목적지 버퍼
    rsize_t    numberOfElements,   // 2. 목적지 버퍼의 전체 크기(바이트 수) — 반드시 정확히 지정
    const char *strSource          // 3. 복사할 원본 문자열
);

int sprintf_s(
    char       *buffer,       // 1. 결과가 쓰일 목적지 버퍼
    size_t     sizeOfBuffer,  // 2. 목적지 버퍼의 전체 크기
    const char *format,       // 3. printf 스타일 포맷 문자열
    ...                       // 4. 가변 인자
);
```
`strcpy_s`는 성공 시 `0`을 반환하는 `errno_t`(정수) 값이다 — 일반 `strcpy`가 목적지 포인터를 그대로 반환하는 것과 다르다. `sprintf_s`는 성공 시 기록된 문자 수(널 종료 문자 제외)를, 버퍼가 부족하면 음수를 반환한다.

### 무엇이 "안전"해지는가
- 원본(`strSource`)이 목적지 크기(`numberOfElements`)보다 길면, `strcpy_s`는 조용히 넘치는 대신 **유효하지 않은 매개변수 핸들러(invalid parameter handler)** 를 호출한다. 기본 동작은 목적지 버퍼를 빈 문자열로 만들고 `errno_t`로 `ERANGE`(34) 등을 반환하며, 디버그 빌드에서는 `assert`/`abort`로 즉시 종료되도록 구성되는 경우가 많다.
- 즉 "덮어써지는" 대신 "그 자리에서 감지되어 처리가 중단"되므로, 공격자 입장에서 `strcpy_s` 호출 자체를 통한 스택/힙 오버플로우는 `strcpy`보다 훨씬 어렵다.

### 그래도 남아있는 취약점 패턴
Secure CRT라고 해서 코드가 무조건 안전한 것은 아니다. 실전에서 여전히 자주 나타나는 버그는 다음과 같다.
- `numberOfElements`(크기 인자)를 목적지 버퍼의 **실제 크기가 아니라** 원본 문자열의 크기나 잘못된 상수로 잘못 넘기는 경우 — 이러면 함수 자체는 "안전"해도 결과적으로 버퍼를 초과해서 쓸 수 있다.
- `sprintf_s`의 포맷 문자열이 사용자 입력을 그대로 받는 포맷 스트링 버그(`%n` 등)는 크기 인자와 무관하게 여전히 위험할 수 있다.
- `strncpy_s`/`strcat_s` 등 형제 함수들과 인자 순서를 혼동해서 실제로는 검사되지 않는 크기를 넘기는 실수.

### x86/x64 스택 보호(_GS)와의 관계
`_s` 함수 자체와는 별개로, MSVC의 `/GS`(기본 활성화) 스택 보호 쿠키도 함께 보이는 경우가 많다. 함수 프롤로그에서 `mov eax, ___security_cookie` 후 스택에 저장하고, 에필로그에서 `call __security_check_cookie`로 검증하는 패턴이 있다면 이것도 별도의 스택 오버플로우 완화 장치이며, `_s` 함수의 크기 검사와는 독립적으로 동작한다.

## 화면/코드에서 보이는 징후
```asm
push offset src
push 20h              ; numberOfElements — 여기 값이 dst의 실제 크기와 일치하는지가 핵심
push offset dst
call strcpy_s
test eax, eax
jnz  error_handler     ; errno_t != 0이면 실패 처리
```
- 디컴파일 결과에서 `strcpy_s(dst, 32, src)`처럼 크기 인자가 명시적으로 보인다.
- 호출 직후 반환값(`eax`)을 검사해서 실패 시 별도 처리로 분기하는 코드가 있으면, 실패 처리 로직이 무엇을 하는지(그냥 무시/로그/종료)도 함께 확인할 가치가 있다.

## 가장 먼저 할 것
`strcpy_s`/`sprintf_s` 호출을 발견하면 두 번째 인자(크기)가 상수인지 변수인지, 그리고 그 값이 목적지 버퍼(첫 번째 인자)의 실제 선언 크기와 정확히 일치하는지부터 확인한다. 여기서 불일치가 있으면 "안전한 함수"임에도 실질적 취약점이 존재하는 지점이다.

## 단계별 절차
**1) 목적지 버퍼 크기 확인(IDA)**
스택 프레임(`F5` 디컴파일 결과의 지역 변수 크기, 또는 `.data`/`.bss`의 전역 배열 선언 크기)에서 `dst`가 실제로 몇 바이트인지 확인한다.

**2) 크기 인자와 대조**
`strcpy_s`/`sprintf_s`의 두 번째 인자가 그 값과 정확히 같은지 비교한다. 더 큰 값이 넘어간다면 그 자체가 버그다.

**3) x64dbg로 실제 길이 확인**
```text
bp strcpy_s
run
; x64: RDX = numberOfElements(크기), R8 = strSource
; R8을 Follow in Dump해서 원본 문자열의 실제 길이를 눈으로 확인
```
원본 문자열 길이가 `RDX` 값보다 긴 경우, 실행을 이어가면 실패 처리 분기로 가는지 실제로 관찰한다.

**4) sprintf_s 포맷 문자열 확인**
세 번째 인자(포맷 문자열)에 `%s`가 여러 개 있거나 사용자 제어 문자열이 그대로 포맷으로 쓰이는지(포맷 스트링 버그 가능성) 확인한다.

## 명령어/단축키
- x64dbg: `bp strcpy_s`, `bp sprintf_s`, `Ctrl+F9`(Execute till return)
- x64dbg: 버퍼 주소 우클릭 → `Follow in Dump`
- IDA: `F5`(디컴파일, 스택 변수 크기 확인), `Structures`/지역 변수 창에서 배열 크기 확인

## 출력 해석
- `strcpy_s` 반환값(`errno_t`)이 `0`이면 성공이고, `0`이 아니면(대개 `EINVAL`=22 또는 `ERANGE`=34) 실패이며 목적지 버퍼는 빈 문자열(`dst[0]=0`)로 초기화되어 있을 가능성이 높다.
- `sprintf_s`가 음수를 반환하면 버퍼가 부족해 아무것도 쓰이지 않은 것이다(일반 `sprintf`처럼 잘린 채로 쓰이지 않는다는 점이 중요한 차이).

## 흔한 실수
- `_s` 함수가 보이면 "이 바이너리는 오버플로우가 절대 불가능하다"고 성급히 단정하는 것 — 크기 인자 자체가 잘못 계산된 2차적 취약점은 여전히 존재할 수 있다.
- `strcpy_s`의 반환값을 목적지 포인터로 착각하는 것 — 일반 `strcpy`와 달리 `errno_t`(정수 상태 코드)를 반환한다.
- `sprintf_s`의 두 번째 인자(버퍼 크기)와 세 번째 인자(포맷 문자열) 순서를 헷갈려서 잘못 해석하는 것 — 항상 시그니처 순서(`buffer, sizeOfBuffer, format, ...`)를 확인한다.

## 막혔을 때 다음 체크
- 와이드 문자(유니코드) 버전 함수가 궁금하다면 → REV-0516 Windows CRT 문자열 함수 사전: wcscpy wcscat 계열(와이드 문자)
- 메모리 복사 계열의 안전 함수가 궁금하다면 → REV-0517 Windows CRT 메모리 함수 사전: memcpy_s memmove_s
- 이 함수들이 다루는 문자열이 ASCII인지 UTF-16인지 헷갈린다면 → REV-0128 Windows 문자열 ASCII와 UTF-16 찾기

## 미니 예제
```c
char dst[16];
char userInput[64];
gets(userInput); // 별개의 취약점(별도 문서에서 다룸)

errno_t err = strcpy_s(dst, sizeof(dst), userInput); // sizeof(dst)=16으로 정확히 넘김
if (err != 0) {
    printf("copy failed, buffer too small\n");
    return -1;
}
```
이 예제에서는 `sizeof(dst)`를 정확히 넘겼으므로 `userInput`이 16바이트보다 길면 `strcpy_s`가 실패 처리로 빠지며 오버플로우가 발생하지 않는다. 만약 이 자리에 `sizeof(dst)` 대신 `sizeof(userInput)`(64)처럼 잘못된 상수가 들어갔다면, 함수는 "성공"으로 리턴하면서도 `dst`를 최대 64바이트까지 덮어쓸 수 있어 실질적인 오버플로우가 된다.

## 관련 글
- REV-0516 — Windows CRT 문자열 함수 사전: wcscpy wcscat 계열(와이드 문자)
- REV-0517 — Windows CRT 메모리 함수 사전: memcpy_s memmove_s
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `strcpy_s`/`sprintf_s`의 시그니처, 반환값(`errno_t`), 실패 시 동작(invalid parameter handler 호출)은 Microsoft 공식 문서(learn.microsoft.com, "strcpy_s, wcscpy_s, _mbscpy_s, _mbscpy_s_l" / "sprintf_s, _sprintf_s_l, swprintf_s, _swprintf_s_l") 기준이다(2026-09-08 확인).
- MSVC `/GS` 스택 보호 쿠키 메커니즘과 `_s` 함수 검사는 서로 독립적인 별개의 완화 기법이라는 점은 Microsoft 공식 문서의 일반적인 보안 기능 설명 기준이다.
