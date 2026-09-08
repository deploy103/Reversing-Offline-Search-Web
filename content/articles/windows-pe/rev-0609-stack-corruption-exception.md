---
id: REV-0609
title: "스택이 깨졌다는 예외가 발생할 때(Stack Corruption)"
slug: "rev-0609-stack-corruption-exception"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords: ["Stack Corruption", "0xC0000409", "STATUS_STACK_BUFFER_OVERRUN", "FAST_FAIL_STACK_COOKIE_CHECK_FAILURE", "__fastfail", "__security_check_cookie"]
aliases: ["스택 오버런 예외", "0xC0000409", "buffer overrun detected", "스택 깨짐 크래시"]
symptom_keywords: ["Run-Time Check Failure 메시지가 뜬다", "0xC0000409 예외가 발생한다", "buffer overrun detected 메시지가 뜬다", "함수가 리턴하는 순간 프로그램이 죽는다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`0xC0000409`(`STATUS_STACK_BUFFER_OVERRUN`) 예외나 "Buffer Overrun Detected!" 메시지는 함수가 `RET`하기 직전에 `/GS` 컴파일 옵션이 심어놓은 스택 카나리(`__security_cookie`) 검사가 실패했다는 뜻이므로, 크래시 지점이 아니라 그 함수 안에서 스택 버퍼에 범위를 넘는 쓰기를 한 지점(대개 `strcpy`/`memcpy`류 호출 직후)을 거꾸로 찾는 것이 실제로 해야 할 일이다.

## 언제 검색해야 하나
- x64dbg나 Windows 자체 크래시 창에서 `0xC0000409` 예외 코드나 "The system detected an overrun of a stack-based buffer" 메시지를 만났을 때
- 프로그램이 특정 함수를 정상적으로 다 실행한 것처럼 보이는데, 딱 그 함수가 `RET`(반환)하는 순간 갑자기 죽을 때
- 크래시 스택 트레이스 최상단에 `__report_gsfailure`, `__security_check_cookie`, `security_check_cookie` 같은 심볼이 보일 때

## 핵심 개념
Visual C++로 컴파일된 대부분의 실행 파일은 기본적으로 `/GS`(Buffer Security Check) 옵션이 켜져 있다. 이 옵션은 지역 변수 중 버퍼(배열)가 있는 함수에 대해, 함수 프롤로그에서 스택에 무작위 값 하나(**스택 쿠키**, 전역 변수 `__security_cookie`에서 가져옴)를 지역 변수와 저장된 반환 주소 사이에 심어두고, 함수가 끝나기 직전(에필로그)에 이 값이 그대로인지 검사한다.

- 함수 시작: 스택 쿠키 값을 프레임 포인터와 XOR한 뒤 스택의 특정 위치(지역 변수보다 낮은 주소, 저장된 반환 주소보다는 높은 주소)에 저장한다.
- 함수 끝: 저장해둔 값을 다시 읽어 같은 방식으로 XOR하고, 원래의 `__security_cookie`와 비교한다(x64에서는 `_security_check_cookie` 루틴이 `cmp rcx, qword ptr [_security_cookie]` 형태로 비교).
- 값이 다르면 스택 버퍼 어딘가에 범위를 넘는 쓰기가 있었다는 뜻이므로, `__report_gsfailure`를 호출해 프로세스를 즉시 종료시킨다. 내부적으로 `__fastfail(FAST_FAIL_STACK_COOKIE_CHECK_FAILURE)`(코드 2)를 실행하며, 이는 실제로는 `INT 0x29` 명령으로 커널에 직접 프로세스 종료를 요청하는 것이다. 이 과정에서 발생하는 예외 코드가 바로 `0xC0000409`(`STATUS_STACK_BUFFER_OVERRUN`)다.

여기서 중요한 점은, **크래시가 관찰되는 위치(함수 에필로그, `RET` 직전)와 실제 문제가 발생한 위치(버퍼에 쓰기가 일어난 지점)가 다르다**는 것이다. 카나리 검사는 함수가 끝날 때만 이루어지므로, 실제 오버플로우는 그보다 훨씬 앞선 코드에서 이미 발생해 있었던 것이다.

## 화면/코드에서 보이는 징후
- 디버그 빌드라면 "Run-Time Check Failure #2 - Stack around the variable '...' was corrupted." 같은 MSVC 런타임 체크 메시지가 뜸
- 릴리즈 빌드라면 그런 친절한 메시지 없이 바로 `0xC0000409` 예외로 죽거나, "이 프로그램이 작동을 멈췄습니다" 형태로만 보임
- x64dbg의 콜스택(Call Stack) 창에서 크래시 시점 최상단에 `security_check_cookie` 또는 `__report_gsfailure`, `RtlFailFast2`류 심볼이 보임
- 크래시 직전 함수 안에 `strcpy`, `sprintf`, `memcpy`, `gets` 등 길이 검증 없이 버퍼에 쓰는 함수 호출이 있음

## 가장 먼저 할 것
1. 크래시가 발생한 함수를 IDA에서 열어, 함수 프롤로그에 `mov rax, cs:__security_cookie` / `xor rax, rsp`류 코드가 있는지 확인해 이 함수가 `/GS` 보호 대상인지 확인한다.
2. 같은 함수 안에서 고정 크기 지역 배열(`char buf[N]`)에 쓰기를 하는 코드(특히 길이 인자를 안 받는 함수 호출)를 찾는다.
3. x64dbg로 그 쓰기 지점 직전에 브레이크포인트를 걸고, 실제로 쓰이는 데이터 길이가 배열 크기(`N`)를 넘는지 직접 확인한다.

## 단계별 절차
**1) 크래시 지점에서 거슬러 올라가기**
- 크래시가 나면 x64dbg의 콜스택을 확인해 어떤 함수가 반환하려다 실패했는지 특정한다. `__security_check_cookie` 호출 직전의 함수가 실제 범인이다.

**2) 카나리가 심어진 위치와 버퍼 위치 비교**
- IDA로 해당 함수의 스택 레이아웃(로컬 변수 뷰, `Alt+K` 또는 함수 프레임 보기)을 확인하면, 스택 쿠키 변수(대개 `var_4`나 `canary`로 표시됨)와 버퍼 변수(`buf` 등)의 상대 오프셋을 볼 수 있다. 버퍼가 쿠키보다 낮은 주소(스택은 높은 주소에서 낮은 주소로 자라므로, 버퍼가 먼저 채워지고 그 다음이 쿠키)에 있다면, 버퍼 오버플로우가 쿠키를 덮어쓸 수 있는 구조라는 뜻이다.

**3) 실제 오버플로우 지점 재현**
- 해당 함수에 진입할 때 브레이크포인트를 걸고, 버퍼에 쓰기가 일어나는 API(`strcpy`, `memcpy`, 수동 루프 등) 호출 직전/직후에도 브레이크포인트를 추가한다.
- 쓰기 직후 덤프 창에서 버퍼 뒤쪽(더 높은 주소, 쿠키가 저장된 위치)까지 데이터가 덮어썼는지 바이트 단위로 확인한다.

**4) 원인 데이터 추적**
- 오버플로우를 일으킨 데이터가 어디서 왔는지(사용자 입력, 파일, 네트워크 등) 상위 호출 스택을 따라 추적한다. CTF 문제라면 이 지점이 대개 취약점의 핵심이다.

## 명령어/단축키
- IDA: `Alt+K`(스택 프레임/로컬 변수 뷰), Imports에서 `strcpy`/`memcpy`/`sprintf` xref 확인
- x64dbg: `F2`(브레이크포인트), Call Stack 창에서 프레임 확인, 덤프 창에서 스택 주소로 이동(`Ctrl+G` 후 `rsp` 입력)

## 출력 해석
- 콜스택에 `ntdll.dll!__report_gsfailure` 또는 `RtlFailFast2`가 보이면 100% `/GS` 스택 쿠키 검사 실패다. 다른 종류의 스택 문제(예: 스택 오버플로우로 가드 페이지에 접근)와는 다른 원인이므로 혼동하지 않는다.
- 예외 코드가 `0xC0000409`가 아니라 `0xC00000FD`(`STATUS_STACK_OVERFLOW`)라면 이는 스택 카나리 문제가 아니라 재귀 등으로 스택 공간 자체를 다 써버린 경우이므로 접근 방법이 다르다.

## 흔한 실수
- 크래시 주소(대개 `RET` 근처)를 취약점 발생 위치로 착각해서 그 근처만 계속 들여다보는 것. 실제 취약점은 함수 앞부분의 버퍼 쓰기 코드에 있다.
- `/GS` 보호가 모든 함수에 적용된다고 생각하는 것. 실제로는 컴파일러가 위험하다고 판단한 함수(고정 크기 버퍼가 있는 함수 등)에만 선택적으로 삽입하므로, 카나리가 없는 함수에서는 오버플로우가 나도 이 예외 없이 조용히 반환 주소를 덮어써 버릴 수 있다.
- 카나리 검사를 그냥 우회(패치)해서 크래시를 없애버리고 "문제가 해결됐다"고 착각하는 것. CTF 등에서는 이 오버플로우 자체가 익스플로잇의 핵심이므로, 검사를 지우는 것과 취약점을 이해하는 것은 전혀 다른 목표다.

## 막혔을 때 다음 체크
- 이 크래시가 애초에 왜 발생하는지 이해가 안 된다면 → REV-0610(카나리 체크 실패로 프로그램이 바로 종료될 때)에서 카나리 검사 자체의 동작을 더 자세히 확인한다.
- x86/x64 호출 규약과 스택 프레임 구조가 헷갈린다면 → REV-0123(x86 호출 규약), REV-0122(MS x64 호출 규약)을 먼저 읽는다.
- 예외가 SEH/VEH로 처리되는 것처럼 보인다면 → REV-0608을 확인한다.

## 미니 예제
IDA에서 다음과 같은 함수를 확인했다고 하자.

```c
void vuln(char *input)
{
    char buf[64];
    strcpy(buf, input);   // 길이 검사 없음
    printf("%s\n", buf);
}
```

이 함수는 `/GS`가 적용되어 있어 `buf` 뒤쪽에 카나리가 심어져 있다. `input`이 64바이트를 훨씬 넘는 문자열이면 `strcpy`가 카나리와 저장된 반환 주소까지 덮어쓰고, 함수가 `RET`하려는 순간 `__security_check_cookie`가 실패를 감지해 `0xC0000409`로 프로세스가 죽는다. x64dbg에서 `strcpy` 호출 직후 `buf`의 뒤쪽 메모리를 덤프해보면 카나리 값이 입력 문자열의 일부로 덮어써진 것을 직접 확인할 수 있다.

## 관련 글
- REV-0610 — 카나리 체크 실패로 프로그램이 바로 종료될 때
- REV-0608 — RIP가 예상 못한 예외 핸들러로 튈 때
- REV-0123 — Windows x86 stdcall cdecl fastcall thiscall

## 출처/검증
- `/GS` 스택 쿠키의 배치(지역 변수와 저장된 반환 주소 사이), `__security_cookie`/`__security_check_cookie`의 동작 방식, 실패 시 `__report_gsfailure` 호출 및 `0xC0000409`(`STATUS_STACK_BUFFER_OVERRUN`) 발생은 Microsoft MSRC의 스택 손상 완화 관련 공개 기술 문서와 다수의 리버스 엔지니어링 분석 자료 기준이다.
- `FAST_FAIL_STACK_COOKIE_CHECK_FAILURE`(`__fastfail` 코드 2)를 통한 프로세스 종료 메커니즘은 공개된 Windows 내부 동작 분석 자료 및 실제 크래시 사례(WinDbg 분석 사례 포함) 기준이다(2026-09-08 확인).
