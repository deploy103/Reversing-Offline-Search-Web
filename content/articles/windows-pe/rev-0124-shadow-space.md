---
id: REV-0124
title: "Shadow Space가 무엇인지"
slug: "rev-0124-shadow-space"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Shadow Space", "shadow space", "홈 스페이스", "home space", "sub rsp 0x28", "sub rsp 0x38", "Microsoft x64 calling convention", "레지스터 스필", "스택 예약 공간", "32바이트 예약 공간", "register spill space"]
aliases: ["섀도우 스페이스", "쉐도우 스페이스", "홈 스페이스", "4 register home space", "caller-allocated spill space"]
symptom_keywords: ["함수에 인자가 4개도 안 되는데 sub rsp 0x28이 있음", "call 하기 전에 왜 스택을 항상 미리 줄임", "sub rsp 0x28 sub rsp 0x38 차이가 뭔지 모르겠음", "rcx rdx r8 r9 스택에 왜 또 저장함", "call 직전에 스택을 32바이트씩 까는 이유"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Windows x64(Microsoft x64 calling convention)에서는 함수를 호출하는 쪽(caller)이 인자 개수와 무관하게 **항상 최소 32바이트(4×8)의 스택 공간**을 미리 확보해야 하는데, 이를 Shadow Space(또는 Home Space)라고 부르며 콜리(callee)가 레지스터 인자(`RCX, RDX, R8, R9`)를 필요할 때 이 공간에 "스필(spill, 대피)"시켜 쓸 수 있게 하기 위한 것이다.

## 언제 검색해야 하나
- 디스어셈블리에서 함수 프롤로그에 `sub rsp, 0x28`이나 `sub rsp, 0x38`처럼 애매한 크기의 스택 감소가 반복적으로 보일 때
- 인자가 1~2개뿐인 짧은 함수인데도 `call` 직전에 스택을 미리 줄이는 코드가 있는 이유가 궁금할 때
- IDA/x64dbg에서 함수 시작 부분에 `[rsp+8]`, `[rsp+0x10]`, `[rsp+0x18]`, `[rsp+0x20]`처럼 낮은 고정 오프셋에 레지스터를 저장하는 코드가 보일 때
- Linux SysV x64(`../linux-elf/rev-0106-sysv-amd64-calling-convention.md`)와 비교했을 때 Windows x64가 스택을 유독 더 많이 미리 까는 이유가 궁금할 때
- REV-0122(Microsoft x64 호출 규약)를 읽다가 "Shadow Space"라는 용어만 따로 더 깊이 알고 싶을 때

## 핵심 개념

### Windows x64 호출 규약의 인자 전달
Microsoft x64 calling convention은 정수/포인터 인자를 처음 4개까지 `RCX, RDX, R8, R9` 순서로 레지스터에 담아 전달한다(자세한 전체 규약은 REV-0122 참고). SysV AMD64(리눅스)가 정수 인자에 6개 레지스터(`RDI, RSI, RDX, RCX, R8, R9`)를 쓰는 것과 달리, Windows는 4개뿐이고 5번째 인자부터 스택을 쓴다.

### 왜 4개뿐인데 32바이트를 예약하나
여기서 초보자가 가장 헷갈리는 부분이 나온다. 함수가 인자를 1개만 받든, 아예 안 받든, **caller는 `call` 명령 실행 전에 항상 최소 32바이트(0x20)의 스택 공간을 확보해야 한다**는 것이 Microsoft x64 ABI의 강제 규칙이다. 이 32바이트는 정확히 `RCX, RDX, R8, R9` 4개 레지스터를 각각 8바이트씩 담을 수 있는 크기다.

이 공간이 존재하는 이유는 **callee(호출된 함수)가 레지스터로 받은 인자를 다시 메모리에 "대피(spill)"시켜야 할 수도 있기 때문**이다. 예를 들어 함수 내부에서:
- 레지스터 인자 값을 디버거로 보기 쉽게 스택에 복사해두거나(디버그 빌드에서 흔함),
- 그 레지스터를 다른 계산에 쓰기 위해 잠깐 비워야 하거나,
- 인자의 주소(`&`)를 다른 함수에 넘겨야 하는 경우(레지스터는 주소를 가질 수 없으므로 반드시 메모리에 있어야 함)

콜리 입장에서는 "인자가 들어있던 레지스터를 스택 어딘가에 저장할 공간"이 항상 보장되어 있다고 가정하고 코드를 짤 수 있다. 그 "항상 보장된 공간"이 바로 caller가 미리 깔아둔 이 32바이트다. **호출된 함수가 이 공간을 실제로 쓰는지 안 쓰는지는 상관없다** — 디버그 빌드는 거의 항상 쓰고, 최적화된 릴리즈 빌드는 레지스터에서 바로 계산을 끝내버려서 이 공간을 아예 안 쓰는 경우도 많다. 그래도 caller는 규약을 지키기 위해 항상 이 공간을 예약해야 한다.

### 왜 "Shadow"라는 이름인가
이 32바이트 영역이 레지스터 인자 `RCX, RDX, R8, R9`의 값을 "그림자처럼" 그대로 복사해 둘 수 있는 자리라는 의미에서 Shadow Space라고 부른다. 다른 문서에서는 Home Space(레지스터가 "집처럼" 돌아갈 수 있는 자리)라고도 부르는데 같은 개념이다.

### sub rsp, 0x28 / sub rsp, 0x38의 의미
함수 프롤로그에서 흔히 보이는 `sub rsp, 0x28`(=40바이트)이나 `sub rsp, 0x38`(=56바이트) 같은 값은 다음 두 가지를 합친 크기다.

1. Shadow Space 32바이트(0x20) — ABI가 강제하는 최소값
2. 스택 정렬 보정 + 로컬 변수 — `call` 명령 실행 직전 `RSP`가 16의 배수여야 한다는 규칙(SysV와 동일한 정렬 규칙) 때문에, `call`이 8바이트 리턴 주소를 push하는 것까지 고려해서 8바이트 단위로 크기를 맞춘다.

가장 흔한 패턴은 `sub rsp, 0x28`이다: 로컬 변수가 거의 없는 짧은 leaf가 아닌 함수(다른 함수를 호출하는 함수)가 32바이트 Shadow Space + 8바이트 정렬 보정만 확보하는 경우다. 로컬 변수가 더 있다면 그만큼 더 커져서 `0x38`, `0x48`처럼 늘어난다.

### Leaf 함수는 예외
다른 함수를 전혀 호출하지 않는 leaf 함수(맨 끝단 함수)는 애초에 `call`을 실행하지 않으므로 Shadow Space를 확보할 필요가 없다. 이런 함수는 `sub rsp`가 아예 없거나, 있어도 순수하게 자기 로컬 변수용으로만 스택을 줄인다. Shadow Space는 어디까지나 **"내가 다른 함수를 부를 때, 그 함수를 위해 내가 미리 깔아주는 공간"**이라는 점을 기억하면 헷갈리지 않는다 — 정확히는 caller가 자신이 호출할 callee를 위해 까는 것이므로, 함수 A가 함수 B를 부른다면 "A의 스택 프레임 안에" B를 위한 32바이트가 생기는 것이다.

### SysV(Linux x64)와의 차이
Linux SysV AMD64는 이런 강제 Shadow Space 규칙이 없다. 대신 leaf 함수에 한해 `RSP` 아래 128바이트를 자유롭게 쓸 수 있는 Red Zone이라는 별개의 개념이 있다(`../linux-elf/rev-0106-sysv-amd64-calling-convention.md` 참고). Windows x64 디스어셈블리를 처음 보는 사람이 리눅스 배경지식만 있으면 "왜 함수 시작마다 스택을 저렇게 많이 까지?"라고 의아해하는 경우가 많은데, 그 답이 바로 이 Shadow Space다.

## 화면/코드에서 보이는 징후
- 함수 프롤로그 초반에 `sub rsp, 0x28`, `sub rsp, 0x38`, `sub rsp, 0x48`처럼 8의 배수이면서 0x20 이상인 값이 반복적으로 등장
- 함수 시작부에서 `mov [rsp+8], rcx` / `mov [rsp+0x10], rdx` / `mov [rsp+0x18], r8` / `mov [rsp+0x20], r9`처럼 낮은 고정 오프셋에 인자 레지스터를 저장하는 코드(주로 디버그 빌드)
- `call` 직전에는 별도로 스택을 더 줄이지 않고, 함수 진입 시 한 번에 확보해둔 그 32바이트+α 공간을 그대로 재사용
- IDA 디컴파일러(F5)에서는 이 스택 조작이 대부분 자동으로 걸러져서 안 보이고, 디스어셈블리(그래프/텍스트 뷰)에서만 직접 확인 가능

## 가장 먼저 할 것
함수 프롤로그에서 `sub rsp, N` 값을 보면 곧바로 "이 함수가 인자를 몇 개 받는가"로 넘어가지 말고, 먼저 `N`이 최소 0x20(32) 이상인지 확인한다. 0x20 이상이면 그 중 32바이트는 Shadow Space일 가능성이 높으므로, 나머지 `N - 0x20`만 실제 로컬 변수/추가 정렬용 공간으로 계산하면 스택 프레임을 훨씬 정확하게 읽을 수 있다.

## 단계별 절차

**1) 함수 프롤로그에서 sub rsp 값 확인**

IDA나 x64dbg의 디스어셈블리에서 함수 시작 부근의 `sub rsp, N`을 찾는다.

**2) N에서 0x20을 빼서 실제 로컬 변수 공간 추정**

`N - 0x20`이 0이면 이 함수는 Shadow Space만 확보하고 로컬 변수는 거의 없는 함수다. `N - 0x20`이 8이면 스택 정렬 보정 8바이트만 추가된 것이고, 그 이상이면 실제 로컬 변수(버퍼, 임시 변수 등)가 있다는 뜻이다.

**3) 낮은 오프셋 `[rsp+8]`~`[rsp+0x20]` 접근 코드 찾아보기**

함수 초반에 `mov [rsp+8], rcx`처럼 4개 인자 레지스터를 이 영역에 저장하는 코드가 있는지 본다. 있다면 디버그 빌드이거나, 함수 내부에서 인자의 주소가 필요해서 스택에 대피시킨 경우다. 이후 함수 본문에서 `rcx` 대신 `[rsp+8]`을 계속 읽고 쓴다면, 이 값이 바로 원래 첫 번째 인자였다는 것을 기억해두고 분석을 이어간다.

**4) x64dbg에서 실제 값 확인 (동적 검증)**

함수 진입 직후에 브레이크포인트를 걸고, 스택 창에서 `RSP` 기준으로 `[rsp+8]`~`[rsp+0x20]`을 살펴보면 각각 `RCX, RDX, R8, R9`가 저장되기 전/후의 실제 값을 눈으로 비교할 수 있다.

```text
bp <함수시작주소>
run
; Registers 창에서 RCX, RDX, R8, R9 확인
; Stack 창에서 [RSP+8] ~ [RSP+20] 값이 아직 쓰이기 전인지 확인
```

**5) call 직전 부분도 대칭적으로 확인**

함수가 다른 함수를 부르는 지점(`call some_func`) 앞에서, 그 `call`을 위한 인자(`RCX, RDX, R8, R9`)를 세팅하는 코드만 있고 스택을 추가로 줄이는 코드는 없다면, 이미 프롤로그에서 확보한 Shadow Space를 재사용하고 있는 것이다.

## 명령어/단축키
- IDA: 함수 프롤로그를 볼 때는 그래프 뷰(Space)보다 텍스트 뷰가 오프셋을 한눈에 비교하기 편하다.
- x64dbg: `bp <주소>`(브레이크포인트), Stack 창에서 `RSP` 기준 오프셋 확인, Registers 창에서 `RCX/RDX/R8/R9` 확인.
- x64dbg 커맨드바: `dq rsp` 로 스택 상단 8바이트씩(QWORD) 여러 줄 덤프해서 Shadow Space 영역 값을 한 번에 확인 가능.

## 출력 해석
- `sub rsp, 0x20`만 있고 그 이상이 없다면: 로컬 변수 없이 Shadow Space만 쓰는 아주 단순한 함수.
- `sub rsp, 0x28`: Shadow Space 0x20 + 정렬 보정 8바이트. 매우 흔한 패턴.
- `sub rsp, 0x40` 이상: Shadow Space 외에 로컬 버퍼/구조체가 스택에 있다는 뜻이므로, 이후 `[rsp+0x30]` 같은 더 높은 오프셋 접근이 로컬 변수 접근일 가능성이 높다.
- 함수 진입 직후 `[rsp+8]`~`[rsp+0x20]`에 값이 저장되는데 함수 본문에서 그 값을 전혀 다시 읽지 않는다면, 디버그 정보용으로만 저장해둔 것(최적화되면 사라짐)이다.

## 흔한 실수
- `sub rsp, N`의 `N`을 전부 "로컬 변수 크기"로 오해해서 스택 프레임 그림을 잘못 그리는 것 — 최소 0x20은 거의 항상 Shadow Space 몫이다.
- Shadow Space를 "콜리가 인자를 저장하기 위해 반드시 써야 하는 공간"으로 오해하는 것 — 사실은 caller가 규약상 의무적으로 확보해주는 것뿐이고, callee가 실제로 그 공간에 값을 저장하는지는 컴파일러 최적화에 따라 다르다.
- SysV(Linux) 배경지식으로 x64 Windows 코드를 보면서 Red Zone과 Shadow Space를 같은 것으로 착각하는 것 — 방향이 정반대다. Red Zone은 caller가 미리 까는 게 아니라 leaf 함수가 자기 스택 아래를 몰래 쓰는 것이고, Shadow Space는 caller가 callee를 위해 의무적으로 미리 까는 것이다.
- 인자가 5개 이상인 함수에서 5번째 인자부터는 Shadow Space 32바이트 "다음" 스택 위치(`[rsp+0x20]` 이후, 함수에 따라 계산 방식이 다름)에 있다는 것을 놓치고 계속 레지스터에서만 인자를 찾으려는 것.

## 막혔을 때 다음 체크
- Windows x64 호출 규약 전체(레지스터 순서, 부동소수점 인자, 스택 정렬)를 더 보고 싶다면 → REV-0122 Microsoft x64 호출 규약
- Linux SysV와 정확히 어떻게 다른지 대조표가 필요하다면 → REV-0106 SysV AMD64 Calling Convention
- 지금 보고 있는 스택 프레임을 x64dbg에서 직접 관찰하며 확인하고 싶다면 → REV-0127 x64dbg로 EXE 첫 분석 시작
- `call` 직전에 `GetProcAddress`/`LoadLibrary` 같은 API 호출 인자를 확인하려는 상황이라면 → REV-0129 GetProcAddress LoadLibrary 동적 API 해석

## 미니 예제
```c
int add_two(int a, int b) { return a + b; }
```
릴리즈 빌드에서도 `add_two`를 호출하는 쪽 코드는 다음과 비슷하게 나타난다.

```asm
; caller
sub  rsp, 0x28        ; Shadow Space(0x20) + 정렬 보정(8)
mov  edx, 2            ; b = 2
mov  ecx, 1            ; a = 1
call add_two
add  rsp, 0x28
; eax에 결과(3)

; add_two 본문 (디버그 빌드 예시, 인자를 스택에 대피시키는 경우)
mov  [rsp+8], ecx      ; a를 Shadow Space에 저장
mov  [rsp+0x10], edx   ; b를 Shadow Space에 저장
mov  eax, [rsp+8]
add  eax, [rsp+0x10]
ret
```
`add_two`는 인자가 2개뿐이지만 caller는 여전히 0x20(32)바이트를 규약대로 예약했고, 디버그 빌드의 `add_two`는 그 공간의 앞부분(`[rsp+8]`, `[rsp+0x10]`)을 실제로 활용해 `RCX`, `RDX` 값을 대피시켰다.

## 관련 글
- REV-0122 — Microsoft x64 Calling Convention
- REV-0106 — SysV AMD64 Calling Convention
- REV-0127 — x64dbg로 EXE 첫 분석 시작
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석

## 출처/검증
- Shadow Space(Home Space) 32바이트 강제 예약 규칙과 스택 정렬 요구사항은 Microsoft Learn "x64 calling convention" / "x64 prolog and epilog" 공식 문서 기준.
- SysV Red Zone과의 대조는 x86-64 psABI(AMD64 Architecture Processor Supplement) "The Stack Frame" 절 기준(2026-09-08 확인).
