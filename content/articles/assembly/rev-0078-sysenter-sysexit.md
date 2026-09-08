---
id: REV-0078
title: "SYSENTER와 SYSEXIT 기초"
slug: "rev-0078-sysenter-sysexit"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - sysenter
  - SYSENTER
  - sysexit
  - SYSEXIT
  - 시스템 콜
  - 시스템콜
  - fast system call
  - KiFastSystemCall
  - ntdll sysenter
  - __kernel_vsyscall
  - vdso
  - WOW64
  - 32비트 syscall
  - IA32_SYSENTER_CS
  - IA32_SYSENTER_EIP
  - IA32_SYSENTER_ESP
  - anti hooking
  - 안티후킹
  - EDX ECX 핸드셰이크
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
aliases:
  - sysenter 뭐임
  - sysexit 뭐임
  - sysenter가 뭐죠
  - 32비트 시스템콜
  - 윈도우 32비트 시스템콜
symptom_keywords:
  - sysenter 왜 씀
  - sysenter syscall 차이
  - ntdll sysenter 분석
  - 32비트 바이너리 sysenter
  - kifastsystemcall 뭐임
---

## 한 줄 요약
`SYSENTER`/`SYSEXIT`는 인텔이 만든 오래된(주로 32비트에서 쓰이는) "빠른 시스템 콜" 명령어 쌍이다 — `SYSENTER`는 유저 모드에서 커널이 정한 고정 진입점으로 전환하고, `SYSEXIT`는 반대로 유저 모드로 복귀한다. AMD의 `SYSCALL`/`SYSRET`([SYSCALL: x86-64 시스템 콜](./rev-0077-syscall.md) 참고)과 목적은 같지만 세부 동작이 다르다.

## 언제 검색해야 하나
- 32비트 Windows 바이너리의 `ntdll.dll`을 디스어셈블해봤는데 `KiFastSystemCall` 같은 함수 안에 `sysenter`가 보일 때
- 32비트 리눅스 바이너리에서 `__kernel_vsyscall`이라는 이름과 함께 `sysenter`가 나올 때
- WOW64(64비트 윈도우에서 32비트 프로그램 실행)로 동작하는 바이너리를 분석하는데 낯선 진입 코드가 보일 때
- SYSCALL과 SYSENTER가 뭐가 다른지 헷갈릴 때 ("sysenter syscall 차이")
- 안티후킹/안티디버깅 기법 조사 중 `sysenter`를 직접 호출하는 코드를 만났을 때

## 핵심 개념

### 이 글의 위치: 레거시/32비트 자료
이 명령어 쌍은 [REV-0077 SYSCALL](./rev-0077-syscall.md)이 다루는 현대적인 64비트 방식과 대비되는 **레거시/32비트 관련 자료**다. 실무에서 마주치는 경로는 대략 세 가지다.
- **32비트 Windows / ntdll**: Windows XP/2003 이후 오랫동안 `ntdll.dll`의 `Nt*`/`Zw*` API 진입점(`KiFastSystemCall`)이 `SYSENTER`를 사용했다.
- **32비트 리눅스 / vDSO**: 커널이 프로세스 주소공간에 매핑해주는 `__kernel_vsyscall`이 `INT 0x80`의 빠른 대안으로 `SYSENTER` 기반 경로를 지원했다.
- **WOW64**: 64비트 Windows에서 32비트 프로그램을 돌릴 때, 그 32비트 코드 내부에는 여전히 이런 레거시 진입 패턴이 남아있을 수 있다.

**핵심 판단 기준**: 진짜 64비트 코드라면 `sysenter`가 아니라 `syscall`(REV-0077)을 기대해야 한다. `sysenter`가 보인다는 것 자체가 "이 코드는 32비트이거나 32비트 호환 경로"라는 신호다.

### Intel 문법
`SYSENTER`와 `SYSEXIT` 둘 다 **오퍼랜드가 전혀 없다**. SYSCALL과 마찬가지로 모든 "인자"는 레지스터를 통해 암묵적으로 전달된다.

### SYSENTER가 하는 일
`SYSENTER`는 IA32_SYSENTER_CS, IA32_SYSENTER_EIP, IA32_SYSENTER_ESP라는 MSR(모델 지정 레지스터)에서 CS:EIP와 SS:ESP를 읽어와 로드하고 Ring 0로 전환한다. MSR 이름을 외울 필요는 없고, "부팅 시 커널이 정해둔 고정 주소로 간다"는 사실만 기억하면 된다.

**SYSCALL과의 결정적인 차이**: `SYSENTER`는 **호출자의 반환 EIP나 ESP를 어디에도 자동으로 저장하지 않는다.** SYSCALL이 하드웨어적으로 RCX/R11에 저장해주는 것과 완전히 다르다. 그래서 이 정보를 저장하는 일은 순전히 **소프트웨어 규약**으로 해결해야 한다. Windows ntdll과 Linux vDSO가 공통으로 쓰는 관례는:
- **EDX**에 복귀할 주소(반환 EIP)를 넣는다.
- **ECX**에 복귀할 때 쓸 유저 모드 스택 포인터(ESP)를 넣는다.

이렇게 해두면, 이 규약을 아는 커널 핸들러가 나중에 `SYSEXIT`를 실행할 때 EDX→EIP, ECX→ESP로 정확히 복귀시켜줄 수 있다.

### SYSEXIT가 하는 일
`SYSENTER`의 반대 동작이다. MSR에서 파생된 셀렉터와 **EDX**(호출자가 넣어둔 반환 주소)로 CS:EIP를 설정하고, **ECX**(호출자가 넣어둔 스택 포인터)로 SS:ESP를 설정한 뒤 Ring 3로 복귀한다.

### 플래그: SYSCALL보다 덜 자동화되어 있음
SYSCALL은 R11/FMASK를 통해 RFLAGS 저장·마스킹을 명령어 차원에서 처리해준다. 반면 **SYSENTER/SYSEXIT는 EFLAGS를 자동으로 저장·복원하지 않는다.** 이 역시 OS의 fast-syscall 스텁 코드가 직접 챙겨야 하는 부분이다 — SYSCALL보다 "덜 자동화된" 명령어 쌍이라고 이해하면 된다.

### 레지스터 효과
EDX와 ECX는 SYSENTER 규약상 반환 주소/반환 스택 포인터 저장용으로 소모된다. 이건 SYSCALL의 RCX/R11 클로버링과 비슷한 결과(그 레지스터를 인자로 자유롭게 못 씀)를 낳지만, 성격은 다르다 — **SYSCALL의 RCX/R11 소모는 하드웨어가 강제하는 것이고, SYSENTER의 EDX/ECX 소모는 순전히 소프트웨어 관례일 뿐 하드웨어가 강제하는 게 아니다.**

### 스택과 RIP 변화
RIP는 커널이 정한 고정 핸들러로 점프한다. SYSCALL과 마찬가지로 **SYSENTER도 스택에 반환 주소를 push하지 않는다** — 대신 위에서 설명한 대로 EDX/ECX 관례를 통해 복귀 정보를 넘긴다.

### 흔한 패턴: Windows KiFastSystemCall
과거 32비트 Windows에서 `ntdll.dll`의 시스템 콜 진입부는 대략 이런 모양이었다:
```asm
KiFastSystemCall:
    mov     edx, esp        ; edx = 현재 사용자 스택 포인터(인자들이 스택에 쌓여있음) -> 커널이 인자 위치를 알기 위함
    sysenter                ; 커널 진입, 실제로는 커널이 다시 sysexit로 복귀시켜줌
```
여기서 인자 자체는 스택에 쌓여 있고, EDX는 그 스택 포인터(즉 인자 위치)를 커널에 알려주는 역할을 겸한다.

리눅스의 `__kernel_vsyscall`도 개념적으로 동일하게 SYSENTER 전에 EDX/ECX를 세팅한다. 이때 syscall 번호는 여전히 EAX, 인자는 EBX/ECX/EDX/ESI/EDI/EBP로 `INT 0x80`과 비슷한 배치를 쓰는데, ECX가 복귀 스택 포인터 트릭에 재사용되기 때문에 커널의 vsyscall 페이지가 내부적으로 값을 조심스럽게 섞어(shuffle) 처리한다. 이 저수준 디테일까지 외울 필요는 없고, "이런 패턴이 있다" 정도만 알아두면 된다.

### 컴파일러/OS 패턴
일반 C 컴파일러가 애플리케이션 코드에서 `SYSENTER`를 직접 뱉는 일은 사실상 없다. SYSCALL처럼 이 명령어는 OS가 제공하는 시스템 콜 스텁 함수 내부(Windows의 `Nt*`/`Zw*` 함수, 리눅스의 vDSO)에만 등장하고, 애플리케이션 코드는 그 스텁을 평범하게 `CALL`로 호출할 뿐이다.

따라서 `sysenter`가 보인다는 것은 "지금 시스템 콜 스텁 아주 깊숙한 곳을 보고 있다"는 뜻이지, 일반적인 CTF crackme 로직에서 직접 나올 일은 거의 없다. 예외적으로, **유저모드 API 후킹(예: EDR/보안 제품의 ntdll 후킹)을 우회하기 위해 `sysenter`/`syscall`을 직접 호출하는 기법은 안티후킹/안티디버깅 기법 중 하나로 알려져 있다** — 높은 레벨의 `Nt*` 래퍼 함수에 걸린 후킹을 건너뛰고 곧바로 커널로 진입하려는 목적이다.

## 화면/코드에서 보이는 징후
- `ntdll.dll`의 `Nt*`/`Zw*` 함수 내부에 `mov edx, esp` 다음 `sysenter`가 나오는 패턴
- `__kernel_vsyscall`이라는 이름의 작은 함수, 그 안에 `sysenter`
- 32비트(x86) 바이너리인데 자체적으로 `sysenter`를 직접 호출하는 코드 — 안티후킹 의심
- 64비트 바이너리에서는 이 패턴이 거의 안 보임 (SYSCALL을 기대해야 함)

## 가장 먼저 할 것
`sysenter`/`sysexit`를 만나면:
1. 바이너리가 32비트인지(또는 WOW64인지) 확인 — 64비트라면 이 패턴 자체가 이례적
2. 그 코드가 `ntdll.dll`/vDSO 내부의 정상적인 syscall 스텁인지, 아니면 애플리케이션 코드가 직접 호출하는 이례적 위치인지 확인
3. EDX/ECX에 어떤 값이 세팅되는지 확인 (반환 주소/스택 포인터 관례)
4. 애플리케이션 코드가 직접 호출하는 경우라면 안티후킹/안티디버깅 목적일 가능성을 의심

## 단계별 절차

**1) KiFastSystemCall류 패턴 식별**
```asm
mov     edx, esp
sysenter
```
이 두 줄만 보여도 "SYSENTER 기반 syscall 스텁"이라고 판단할 수 있다.

**2) 어떤 syscall인지 확인**
스텁 함수 시작 부분에서 `mov eax, N` (Windows의 경우 시스템 콜 번호, 버전마다 값이 다름)을 찾는다. 정적 분석만으로는 번호와 실제 `Nt*` 함수 대응이 버전마다 다를 수 있으므로, 심볼이 있는 `ntdll.dll` 함수 이름을 그대로 참고하는 편이 실용적이다.

**3) 애플리케이션 코드가 직접 sysenter/syscall을 호출하는지 확인**
정상적인 프로그램은 `Nt*` 함수를 `CALL`로 부르지, `sysenter`를 직접 인라인으로 넣지 않는다. 애플리케이션 코드 한가운데 `sysenter`가 인라인되어 있다면 후킹 우회 목적을 의심하고 주변 코드를 자세히 본다.

## 명령어/단축키
- IDA/Ghidra: `ntdll.dll` 내 `Nt*`/`Zw*` 함수를 검색해 `sysenter` 존재 확인, X(Xrefs to)로 누가 이 스텁을 직접 호출하는지 추적
- x64dbg/x32dbg: 32비트 타겟에서 `sysenter` 명령에 브레이크포인트를 걸어 EDX/ECX 값 확인
- GDB: 32비트 프로세스에서 `info registers edx ecx` 로 확인

## 출력 해석
- 디버거에서 `sysenter` 실행 직전 EDX/ECX 값을 확인하면, 그것이 곧 커널이 복귀에 사용할 반환 주소/스택 포인터다.
- IDA 디컴파일은 SYSCALL과 마찬가지로 SYSENTER의 암묵적 인자 전달을 깔끔한 이름 있는 함수 호출로 잘 모델링하지 못한다 — `mov edx, esp` / `sysenter` 조합 자체를 지문(fingerprint)으로 인식하는 게 더 실용적이다.

## 흔한 실수
- SYSENTER/SYSEXIT가 SYSCALL/SYSRET와 완전히 똑같이 자동으로 반환 주소를 저장해준다고 착각하는 것 — SYSCALL은 하드웨어가 RCX/R11에 자동 저장하지만, SYSENTER는 EDX/ECX를 **수동으로(소프트웨어 관례로)** 세팅해야 한다. 이 차이를 헷갈리면 안 된다.
- 현대 64비트 전용 바이너리에서도 이 패턴을 기대하는 것 — 64비트 코드에서는 SYSENTER 대신 SYSCALL(REV-0077)을 봐야 정상이다.
- 인텔 전용 명령어라고 AMD CPU에서 못 쓴다고 생각하는 것 — 오늘날 인텔/AMD CPU 모두 호환을 위해 두 명령어 쌍(SYSCALL/SYSRET, SYSENTER/SYSEXIT)을 다 지원한다. 실제로 어떤 걸 쓰는지는 OS/바이너리의 설계에 달려 있다.

## 막혔을 때 다음 체크
- 64비트 바이너리인데 `sysenter`가 보여서 당황스럽다면 → WOW64(32비트 프로세스가 64비트 윈도우 위에서 도는 경우)인지, 아니면 실제로 32비트 모듈을 보고 있는 건 아닌지 모듈 비트수부터 재확인한다.
- 어떤 `Nt*`/`Zw*` 함수인지 특정이 안 되면 → 심볼이 있는 `ntdll.dll` 원본과 오프셋/이름을 대조하거나, 같은 버전의 참조용 ntdll을 나란히 열어 비교한다.
- 애플리케이션 코드가 왜 `sysenter`를 직접 호출하는지 이해가 안 되면 → 그 함수를 호출하는 곳들을 X(Xrefs to)로 추적해서 이 코드가 후킹 탐지/우회 목적의 별도 모듈(락커, 안티치트, EDR 등)인지 문맥을 넓혀서 본다.
- EDX/ECX 관례가 실제로 지켜지는지 확신이 안 서면 → 디버거로 `sysenter` 직전에 멈춰서 두 레지스터 값이 실제로 "복귀할 만한" 코드 주소/스택 주소처럼 보이는지 눈으로 확인한다.

## 미니 예제

**예제 1 — Windows KiFastSystemCall 스타일**
```asm
KiFastSystemCall:
    mov     edx, esp        ; edx = 사용자 스택 포인터 (인자 위치를 커널에 전달)
    sysenter                ; 커널 진입
    ; 커널이 sysexit로 복귀시켜주면 여기로 돌아옴
    ret
```

**예제 2 — 개념적인 SYSENTER/SYSEXIT 핸드셰이크**
```asm
; 유저 모드 스텁
user_stub:
    mov     edx, return_here   ; 복귀할 EIP를 EDX에
    mov     ecx, esp           ; 복귀할 ESP를 ECX에
    sysenter
return_here:
    ; 커널이 SYSEXIT로 여기까지 복귀시켜줌
    ret

; (커널 내부, 개념 설명용 — 실제로는 OS 소스에 존재)
kernel_handler:
    ; ... 시스템 콜 처리 ...
    sysexit                    ; edx -> eip, ecx -> esp 로 유저 모드 복귀
```

## 관련 C 코드
SYSCALL과 마찬가지로 일반 C 코드는 `sysenter`를 직접 만들어내지 않는다. 이건 순전히 OS가 제공하는 syscall 스텁 내부의 일이며, 평범한 `write()`/`read()`류 C 코드는 그냥 OS가 제공한 스텁 함수를 보통의 `CALL`로 부를 뿐이다.

## 관련 글
- [SYSCALL: x86-64 시스템 콜](./rev-0077-syscall.md) — 현대 64비트에서 이 명령어 쌍을 대체한 카운터파트
- [CALL: 함수 호출, 반환 주소, 인자 추적](./rev-0071-call.md)
- [FLAGS 레지스터 개요](./rev-0088-flags-overview.md)
- REV-0072 — RET: 함수 반환과 스택 변화
- REV-0079 — INT와 INT 0x80: 인터럽트 기반 시스템 콜

## 출처/검증
- SYSENTER/SYSEXIT 동작(MSR 기반 진입, EDX/ECX 관례, 플래그 비자동 저장): Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2B, "SYSENTER—Fast System Call" / "SYSEXIT—Fast Return from Fast System Call" 섹션 기준 (2026-09-08 검증).
- Windows `KiFastSystemCall`/ntdll 시스템 콜 진입 방식, 리눅스 `__kernel_vsyscall`(vDSO) 관례: 공개된 리버싱/OS 내부 구조 일반 자료 기준.
