---
id: REV-0139
title: "CreateFile ReadFile WriteFile 입력 데이터 추적"
slug: "rev-0139-createfile-readfile-writefile"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["CreateFileW", "ReadFile", "WriteFile", "파일 입출력", "stdcall", "fastcall", "RCX RDX R8 R9"]
aliases: ["파일 입출력 함수 인자", "CreateFile 인자 순서", "ReadFile WriteFile 인자", "파일 데이터 추적"]
symptom_keywords: ["CreateFile 인자가 몇 개인지 모르겠다", "ReadFile 버퍼가 어디인지 모르겠다", "WriteFile로 뭘 쓰는지 확인하고 싶다", "call 직전 스택/레지스터를 봐야 한다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CreateFile`/`ReadFile`/`WriteFile`은 프로그램이 파일(또는 파일처럼 다뤄지는 파이프/장치)과 데이터를 주고받는 지점이므로, 이 세 함수의 정확한 인자 순서를 알고 `CALL` 직전에 x86은 스택을, x64는 `RCX`/`RDX`/`R8`/`R9` 레지스터를 확인하는 법을 익히면 프로그램이 어떤 파일을 열어 어떤 데이터를 읽고 쓰는지 바로 추적할 수 있다.

## 언제 검색해야 하나
- 임포트 목록에서 `CreateFileW`/`CreateFileA`, `ReadFile`, `WriteFile`을 발견하고 이 프로그램이 어떤 파일을 다루는지 알아내야 할 때
- x64dbg로 `WriteFile` 호출 직전에 멈춰서 실제로 어떤 데이터가 파일에 쓰이는지(예: 암호화된 결과, 플래그) 확인하고 싶을 때
- `ReadFile`로 읽어들인 버퍼가 이후 어떻게 가공되는지(복호화, 검증) 추적해야 할 때
- x86과 x64에서 인자를 확인하는 방법이 달라서 헷갈릴 때

## 핵심 개념
세 함수 모두 `kernel32.dll`(내부적으로는 `KernelBase.dll`)이 제공하는 표준 Win32 파일 입출력 API다. 정확한 인자 순서를 외워두면 호출 지점만 봐도 절반은 분석이 끝난다.

**`CreateFileW`** — 파일을 열거나 새로 만들어 핸들을 얻는다.
```c
HANDLE CreateFileW(
    LPCWSTR               lpFileName,           // 1. 파일 경로(유니코드 문자열)
    DWORD                  dwDesiredAccess,      // 2. 원하는 접근 권한(GENERIC_READ/WRITE 등)
    DWORD                  dwShareMode,          // 3. 다른 프로세스와 공유 방식
    LPSECURITY_ATTRIBUTES  lpSecurityAttributes, // 4. 보안 속성(대개 NULL)
    DWORD                  dwCreationDisposition,// 5. 열기/만들기 방식(OPEN_EXISTING, CREATE_ALWAYS 등)
    DWORD                  dwFlagsAndAttributes, // 6. 파일 속성/플래그
    HANDLE                 hTemplateFile         // 7. 템플릿 파일 핸들(대개 NULL)
);
```
반환값은 성공 시 유효한 `HANDLE`(정수값), 실패 시 `INVALID_HANDLE_VALUE`(`-1`, 즉 `0xFFFFFFFF`/`0xFFFFFFFFFFFFFFFF`)이다. 이 반환값(`EAX`/`RAX`)을 이후 `ReadFile`/`WriteFile`의 첫 인자로 그대로 넘기는 패턴이 매우 흔하다.

**`ReadFile`** — 열린 파일에서 데이터를 읽어 버퍼에 채운다.
```c
BOOL ReadFile(
    HANDLE       hFile,                  // 1. CreateFile이 반환한 핸들
    LPVOID       lpBuffer,               // 2. 읽은 데이터를 저장할 버퍼 주소
    DWORD        nNumberOfBytesToRead,   // 3. 읽으려는 바이트 수
    LPDWORD      lpNumberOfBytesRead,    // 4. 실제로 읽은 바이트 수가 저장될 주소
    LPOVERLAPPED lpOverlapped            // 5. 비동기 입출력용 구조체 주소(동기 방식이면 NULL)
);
```

**`WriteFile`** — 열린 파일에 버퍼의 데이터를 써넣는다.
```c
BOOL WriteFile(
    HANDLE       hFile,                   // 1. 파일 핸들
    LPCVOID      lpBuffer,                // 2. 써넣을 데이터가 있는 버퍼 주소
    DWORD        nNumberOfBytesToWrite,   // 3. 쓰려는 바이트 수
    LPDWORD      lpNumberOfBytesWritten,  // 4. 실제로 쓴 바이트 수가 저장될 주소
    LPOVERLAPPED lpOverlapped             // 5. 비동기 입출력용(동기면 NULL)
);
```

`ReadFile`과 `WriteFile`은 인자 구조가 완전히 대칭이며, 2번 인자(버퍼)의 방향만 반대(읽기는 "채워지는 곳", 쓰기는 "읽어가는 곳")라는 점만 기억하면 헷갈리지 않는다. 두 함수 모두 `BOOL`(성공 시 0이 아닌 값)을 반환한다.

이 함수들을 호출할 때 인자가 어디에 실리는지는 아키텍처와 호출 규약에 따라 다르다.

- **x86(32비트, `stdcall`)**: 인자는 오른쪽(마지막 인자)부터 왼쪽(첫 인자) 순서로 스택에 `push`된다. `CALL` 명령이 실행되는 순간 스택에는 이미 모든 인자가 쌓여 있고, `CALL`이 리턴 주소를 추가로 `push`한다. 따라서 함수 진입 직후 기준으로 `[esp]`가 리턴 주소, `[esp+4]`가 첫 번째 인자, `[esp+8]`이 두 번째 인자... 순서로 이어진다.
- **x64(Microsoft x64 호출 규약)**: 정수/포인터 타입 인자 앞 4개는 순서대로 `RCX`, `RDX`, `R8`, `R9` 레지스터에 담긴다. 5번째 인자부터는 스택에 쌓이며, 호출자(caller)는 그 앞에 32바이트(4개 레지스터分)의 "섀도우 스페이스(shadow space)"를 항상 예약해둬야 한다. `ReadFile`/`WriteFile`은 인자가 5개이므로 5번째 인자(`lpOverlapped`)만 스택에서, 그것도 섀도우 스페이스 뒤(`[rsp+0x28]` 부근, 리턴 주소 `[rsp]` + 섀도우 스페이스 0x20)에서 찾아야 한다.

## 화면/코드에서 보이는 징후
- `CALL` 대상 이름이 `CreateFileW`인 명령어 바로 위쪽에 `lea`/`push`(x86) 또는 `mov r9d, ...` / `mov r8, ...` / `lea rdx, ...` / `lea rcx, ...`(x64, 인자가 역순으로 세팅되는 경우가 흔함)가 연이어 나옴
- `CreateFileW` 반환값(`eax`/`rax`)이 곧바로 지역 변수나 전역 변수에 저장된 뒤, 몇 줄 뒤 `ReadFile`이나 `WriteFile`의 첫 인자로 다시 로드되는 패턴
- `ReadFile` 호출 직후 반환값(`eax`)을 `test eax, eax` / `cmp eax, 0`으로 검사해서 실패 시 에러 처리로 분기하는 코드

## 가장 먼저 할 것
1. 대상 바이너리가 x86인지 x64인지부터 확인한다(REV-0136에서 다룬 PE-bear의 Machine 필드로 쉽게 확인 가능).
2. `CreateFileW`(또는 `CreateFileA`)의 첫 번째 인자(파일 경로 문자열)부터 확인해서 "이 프로그램이 어떤 파일을 다루는가"를 먼저 파악한다.
3. 그 핸들이 이후 `ReadFile`/`WriteFile` 어디로 이어지는지 데이터 흐름을 추적한다.

## 단계별 절차
**1) 정적 분석(IDA)**
- 임포트 목록에서 `CreateFileW`를 찾아 `X`(교차 참조)로 호출 위치를 나열한다.
- 각 호출 지점 직전의 인자 세팅 코드를 보고, 첫 번째 인자로 쓰이는 문자열 리터럴이나 변수를 확인한다. Hex-Rays 디컴파일(`F5`)을 쓰면 `CreateFileW(L"data.bin", GENERIC_READ, ...)` 형태로 훨씬 읽기 편하게 나온다.

**2) 동적 분석 - x86**
- x64dbg(x32dbg)에서 `bp CreateFileW` 후 실행한다.
- 브레이크포인트가 걸리면 함수 진입 직후이므로, Stack 창에서 `[esp]`=리턴 주소, `[esp+4]`=`lpFileName`, `[esp+8]`=`dwDesiredAccess` 순서로 값을 확인한다. `[esp+4]`에 있는 주소를 우클릭 → "Follow in Dump"하면 실제 파일 경로 문자열(유니코드)이 보인다.

**3) 동적 분석 - x64**
- `bp ReadFile` 또는 `bp WriteFile`로 브레이크포인트를 건다.
- 브레이크포인트가 걸린 순간 Registers 창에서 `RCX`(hFile), `RDX`(lpBuffer), `R8`(바이트 수)를 바로 확인한다. `RDX`를 우클릭 → "Follow in Dump"하면 실제 버퍼 내용을 볼 수 있다.
- `WriteFile`이라면 이 시점(함수 진입 직후, 아직 실제로 파일에 쓰기 전)에서 `RDX`가 가리키는 메모리를 보면 "지금 막 파일에 쓰이려는 데이터"를 그대로 확인할 수 있다. 이는 암호화된 출력 결과나 최종 flag 데이터를 가로채는 데 매우 유용하다.
- 5번째 인자(`lpOverlapped`)까지 확인해야 한다면 `[rsp+0x28]`(함수 진입 직후 기준, 리턴 주소 8바이트 + 섀도우 스페이스 0x20바이트)을 스택 창에서 확인한다.

## 명령어/단축키
- x64dbg: `bp CreateFileW`, `bp ReadFile`, `bp WriteFile` (임포트 함수명으로 바로 브레이크포인트 설정 가능)
- x64dbg 레지스터 확인(x64): `RCX`, `RDX`, `R8`, `R9` 창에서 직접 값 확인, 우클릭 → "Follow in Dump"로 메모리 내용 확인
- x64dbg 스택 확인(x86): Stack 창에서 `[esp+4]`, `[esp+8]` 형태로 오프셋 직접 계산
- IDA: `X`(교차 참조), `F5`(Hex-Rays 디컴파일로 인자를 한눈에)

## 출력 해석
- `CreateFileW` 반환값이 `0xFFFFFFFF`(x86) 또는 `0xFFFFFFFFFFFFFFFF`(x64, `INVALID_HANDLE_VALUE`)이면 파일 열기에 실패한 것이다. 이후 코드가 이 값을 검사하지 않고 그냥 `ReadFile`에 넘긴다면 버그이거나, 의도적으로 실패를 무시하는 경로일 수 있다.
- `dwDesiredAccess`가 `GENERIC_READ`(0x80000000)면 읽기 전용, `GENERIC_WRITE`(0x40000000)면 쓰기, 둘 다 OR 되어 있으면 읽기/쓰기 모두 가능하다는 뜻이다.
- `dwCreationDisposition`이 `CREATE_ALWAYS`(2)면 파일이 있어도 덮어쓰며 새로 만들고, `OPEN_EXISTING`(3)이면 파일이 없으면 실패한다. 이 값으로 "이 파일을 새로 만드는 코드인지, 기존 파일을 여는 코드인지" 바로 알 수 있다.
- `ReadFile`/`WriteFile`의 반환값(`BOOL`)이 0이면 실패, 0이 아니면 성공이며, 실제로 처리된 바이트 수는 반환값이 아니라 4번째 인자(`lpNumberOfBytesRead`/`Written`)가 가리키는 `DWORD` 변수에 별도로 저장된다는 점에 유의한다.

## 흔한 실수
- `ReadFile`/`WriteFile`의 성공 여부를 반환값(`BOOL`)이 아니라 4번째 인자(처리된 바이트 수)로 착각하는 것. 반환값과 바이트 수는 서로 다른 값이며 둘 다 확인해야 정확하다.
- x64에서 다섯 번째 인자를 찾을 때 섀도우 스페이스 0x20을 빼먹고 스택 오프셋을 잘못 계산하는 것. 함수 진입 직후 기준 `[rsp]`=리턴 주소이므로 5번째 인자는 `[rsp+0x28]`이다(리턴 주소 8바이트 + 섀도우 스페이스 0x20바이트).
- `CreateFileA`(ANSI)와 `CreateFileW`(유니코드)를 같은 것으로 생각해서 문자열을 1바이트 단위로 읽어버리는 것. `W` 버전은 2바이트(UTF-16LE) 단위이므로 덤프 창에서 "UTF-16" 표시 옵션으로 봐야 문자열이 제대로 보인다.
- `WriteFile` 호출 직전이 아니라 직후에 브레이크포인트를 걸어서, 이미 파일에 쓰인 뒤의 상태만 보고 "데이터가 어디서 왔는지" 못 찾는 것. 데이터 자체를 가로채려면 호출 직전(브레이크포인트가 함수 진입 시 걸리므로 자연히 이 시점)에 버퍼를 확인해야 한다.

## 막혔을 때 다음 체크
- 함수 이름 자체가 낯설어 인자 순서를 짐작하기 어렵다면 → REV-0138(Windows API 이름으로 기능 추측하는 법)을 먼저 참고한다.
- 읽거나 쓰는 데이터가 암호화되어 있다면 → REV-0140(Crypt API BCrypt API 흔적 찾기)에서 관련 API 흔적을 함께 확인한다.
- 파일이 아니라 PE 내부 리소스에서 데이터가 오는 것 같다면 → REV-0141(Resource Section과 숨겨진 데이터 확인)을 확인한다.

## 미니 예제
x64 바이너리를 x64dbg로 열고 `bp WriteFile` 후 실행했더니 다음과 같이 멈췄다고 하자.

```text
RCX = 0x0000000000000094   (hFile, 이전 CreateFileW의 반환값과 일치)
RDX = 0x000001F2A3C04010   (lpBuffer)
R8  = 0x0000000000000020   (nNumberOfBytesToWrite = 32)
```

`RDX`를 우클릭 → "Follow in Dump"하면 다음과 같은 32바이트가 보인다.

```text
1F2A3C04010  43 54 46 7B 64 33 62 75  67 5F 66 31 6C 33 5F 77
1F2A3C04020  31 74 68 5F 72 33 61 64  5F 66 31 6C 33 7D 00 00
```

ASCII로 변환하면 `CTF{d3bug_f1l3_w1th_r3ad_f1l3}`가 되며, 이는 프로그램이 파일에 쓰기 직전의 평문 데이터를 그대로 가로챈 것이다. 파일이 실제로 디스크에 기록되기를 기다리지 않고, `WriteFile` 호출 시점에 메모리에서 바로 값을 읽어냈기 때문에 가능한 방법이다.

## 관련 글
- REV-0138 — Windows API 이름으로 기능 추측하는 법
- REV-0140 — Crypt API BCrypt API 흔적 찾기
- REV-0141 — Resource Section과 숨겨진 데이터 확인

## 출처/검증
- `CreateFileW`/`ReadFile`/`WriteFile`의 함수 시그니처와 인자 순서, 반환값 의미는 Microsoft Win32 API 공식 문서 기준이다.
- Microsoft x64 호출 규약(`RCX`/`RDX`/`R8`/`R9`, 섀도우 스페이스 0x20바이트)과 x86 `stdcall`의 스택 인자 전달 방식은 Microsoft x64 소프트웨어 규약 공식 문서 기준이다.
- 위 미니 예제의 값과 flag 문자열은 설명을 위해 구성한 예시이며 실제 특정 문제의 데이터가 아니다(2026-09-08 기준 서술).
