---
id: REV-0086
title: "CPUID: CPU 정보와 안티VM 단서"
slug: "rev-0086-cpuid"
category: "assembly"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - cpuid
  - CPUID
  - cpuid instruction
  - cpuid 명령어
  - anti-vm
  - 안티VM
  - vm 탐지
  - 가상머신 탐지
  - hypervisor bit
  - 하이퍼바이저 비트
  - vendor string
  - VMwareVMware
  - VBoxVBoxVBox
  - KVMKVMKVM
  - sandbox detection
  - 샌드박스 탐지
  - eax ebx ecx edx cpuid leaf
aliases:
  - cpuid가 뭐임
  - cpuid 명령어란
  - vm 탐지 어셈블리
  - 안티vm 체크
  - 가상환경 탐지 코드
symptom_keywords:
  - cpuid 호출 후 분기하는 코드가 이상함
  - vmware에서 프로그램이 다르게 동작함
  - 샌드박스에서 실행이 종료됨
  - hypervisor 비트를 왜 검사하는지 모르겠음
  - vendor string을 비교하는 코드가 있음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`CPUID`는 오퍼랜드 없이 실행하며, `EAX`(및 일부 leaf에서는 `ECX`)에 넣은 "leaf(조회 항목) 번호"에 따라 `EAX/EBX/ECX/EDX`에 CPU 제조사, 기능 지원 여부, 하이퍼바이저 존재 여부 같은 정보를 채워 반환하는 명령이다. 정상적으로는 CPU 기능 감지(예: SSE4.2 지원 여부)에 쓰이지만, 리버싱에서는 **VM/샌드박스 탐지(안티VM) 코드**의 핵심 명령어로 훨씬 더 자주 마주치게 된다.

## 언제 검색해야 하나
- 악성코드나 패킹된 바이너리 분석 중 `cpuid` 명령이 나오는데 뒤에 이어지는 분기 로직이 이해 안 될 때
- `xor eax, eax` / `cpuid` 조합 뒤에 `ebx`, `ecx`, `edx` 값을 문자열과 비교하는 코드를 볼 때
- 프로그램이 VMware/VirtualBox 안에서 실행하면 다르게 동작하거나 조용히 종료되는 이유를 찾을 때
- `eax = 1` 세팅 후 `cpuid` 실행하고 `ecx`의 특정 비트(31번 비트)를 검사하는 코드를 볼 때

## 핵심 개념

### CPUID의 기본 동작
```
입력: EAX = leaf 번호 (필요시 ECX = sub-leaf 번호)
출력: EAX, EBX, ECX, EDX 가 leaf에 따라 정의된 정보로 덮어써짐
```
`CPUID`는 함수 호출처럼 "무엇을 물어볼지"를 `EAX`(leaf)에 넣고 실행하면 결과가 네 개의 레지스터에 채워지는 구조다. 대표적인 leaf:

| EAX (leaf) | 의미 |
|---|---|
| `0` | 최대 지원 leaf 번호 + **벤더 문자열**(`EBX:EDX:ECX` 12바이트, 예: `"GenuineIntel"`, `"AuthenticAMD"`) |
| `1` | 프로세서 정보와 기능 플래그 (`ECX`, `EDX`에 SSE/AVX 등 지원 비트, **`ECX`의 31번 비트가 하이퍼바이저 존재 여부**) |
| `0x40000000` | 하이퍼바이저 존재 시(leaf 1의 31번 비트가 1일 때) **하이퍼바이저 벤더 문자열**(`EBX:ECX:EDX`, 예: `"VMwareVMware"`, `"KVMKVMKVM\0\0\0"`, `"VBoxVBoxVBox"`) |

### 레지스터 효과 (오퍼랜드 없음, 4개 레지스터 전체 갱신)
- **입력**: `EAX`(필수), `ECX`(일부 leaf에서 sub-leaf 지정에 사용).
- **출력**: `EAX`, `EBX`, `ECX`, `EDX` **네 레지스터 모두**가 leaf 정의에 따른 값으로 덮어써진다 — 입력으로 쓰였던 `EAX` 값 자체도 이 시점에 사라진다는 점에 유의(leaf 값을 나중에 또 쓰려면 미리 백업해야 함).
- x64에서는 상위 32비트(`RAX/RBX/RCX/RDX`의 상위 절반)가 0으로 클리어된다.

### 플래그 변화
`CPUID`는 **EFLAGS를 바꾸지 않는다.** 순수하게 정보를 조회하는 명령이라 플래그 갱신이 없다.

### 스택/RIP 변화
직접적인 영향 없음. 커널 개입 없이 사용자 모드에서 바로 실행되는 명령이다(단, 가상화 환경에서는 하이퍼바이저가 이 명령을 가로채 결과를 조작할 수 있다 — 아래 안티VM 섹션 참고).

## 안티VM / 안티분석 관점에서의 의미 (핵심)
`CPUID`는 리버싱 학습에서 "패킹/안티분석" 단계로 넘어가기 전에 반드시 알아야 하는 명령이다. 이유는 **가상화 소프트웨어(하이퍼바이저)가 `CPUID`의 반환값을 조작하거나 자신의 존재를 흔적으로 남기기 때문**이다.

1. **하이퍼바이저 비트 검사**: `EAX=1`로 `CPUID`를 실행한 뒤 `ECX`의 **31번 비트**가 1이면 "이 CPU는 하이퍼바이저(가상화 계층) 위에서 실행 중"이라는 뜻이다(Intel/AMD 공식 문서에 정의된 소프트웨어 관례 비트). 악성코드나 CTF의 안티VM 로직이 이 비트 하나만 검사해서 "가상환경이면 정상 동작을 숨기거나 종료"하는 경우가 매우 흔하다.
   ```asm
   mov     eax, 1
   cpuid
   test    ecx, 80000000h   ; 31번 비트(0x80000000) 검사
   jnz     vm_detected
   ```
2. **하이퍼바이저 벤더 문자열 비교**: 하이퍼바이저 비트가 켜져 있으면 `EAX=0x40000000`으로 다시 `CPUID`를 실행해 `EBX:ECX:EDX`에서 벤더 문자열을 얻고, `"VMwareVMware"`, `"VBoxVBoxVBox"`, `"KVMKVMKVM\0\0\0"`, `"Microsoft Hv"`(Hyper-V) 등 알려진 문자열과 비교해 어떤 가상화 제품인지 특정한다. 문자열 상수가 코드 안에 하드코딩되어 있으므로 IDA/Ghidra의 문자열 뷰(Strings 창)에서 `"VMware"`, `"VBox"`, `"KVM"` 같은 키워드로 먼저 검색하면 이 로직을 빠르게 찾을 수 있다.
3. **일반 벤더 문자열 확인**: `EAX=0`으로 얻는 `"GenuineIntel"`/`"AuthenticAMD"` 자체는 보통 안티VM에 직접 안 쓰이지만, 일부 오래된/조악한 탐지 코드는 CPU 모델명(`EAX=0x80000002~0x80000004`로 얻는 브랜드 문자열)에 `"Virtual"`, `"QEMU"` 같은 단어가 들어있는지도 검사한다.
4. **타이밍과 조합**: `CPUID`는 하이퍼바이저가 가로채서 처리해야 하는(트랩되는) 명령이라 **실행 시간이 일반 명령보다 눈에 띄게 오래 걸린다.** `RDTSC`(REV-0087 참고)로 `CPUID` 실행 전후 시간을 재서 "비정상적으로 느리면 VM/에뮬레이터"라고 판단하는 결합 기법도 존재한다 — `CPUID`와 `RDTSC`가 안티분석 코드에서 나란히 등장하는 이유다.

**분석 시 대응**: `cpuid` 뒤에 나오는 분기(`test`/`jnz`/`cmp` 등)가 안티VM 체크라고 의심되면, 디버거로 그 지점에서 결과 레지스터 값을 직접 확인하거나(x64dbg/GDB), 해당 분기를 패치(NOP 처리 또는 조건 반전)해서 우회하는 것이 표준적인 대응이다. 단, 방어적/교육적 목적(CTF, 자체 분석)에 한해서만 이런 우회를 시도해야 한다.

## 컴파일러 패턴
일반 애플리케이션 코드에서 `CPUID`는 주로 **런타임에 CPU가 특정 명령 확장(SSE4.2, AVX, AVX2, BMI 등)을 지원하는지 확인**하는 목적으로 프로그램 시작 시 한 번 호출된다(예: `__cpuid()` 인트린식, `__builtin_cpu_supports()`). 이런 "정상적인" `CPUID` 사용은 보통 leaf 1이나 leaf 7을 쓰고, 결과에 따라 다른 최적화된 코드 경로(예: AVX2 버전 함수 vs 일반 버전 함수)로 분기한다 — 안티VM 코드와 구분하려면 **비교 대상 비트/문자열이 "CPU 기능"인지 "하이퍼바이저 존재/벤더"인지**를 보면 된다.

## IDA/Ghidra 디컴파일에서 보이는 방식
`CPUID`는 대부분 인트린식 함수 호출 형태(`__cpuid(regs, leaf)` 또는 `__get_cpuid(leaf, &eax, &ebx, &ecx, &edx)`)로 디컴파일되거나, 인라인 어셈블리 그대로 남는 경우도 있다. IDA는 `cpuid` 명령 자체를 특별히 재해석하지 않고 레지스터 대입 형태로 보여주는 경우가 많으므로, leaf 값(직전 `EAX` 세팅)과 그 뒤의 비트 마스크 비교를 직접 읽어야 무엇을 조회하는지 알 수 있다.

## 리버싱 관점에서의 의미
- 안티VM 체크의 존재 자체가 "이 바이너리가 분석 회피를 시도한다"는 강한 신호이며, 악성코드나 상용 패커/프로텍터(패킹/안티디버깅 단계에서 다룰 VMProtect, Themida 등)에서 흔히 쓰인다.
- CPU 기능 감지용 정상 `CPUID`와 안티VM용 `CPUID`를 구분하는 습관을 들이면 분석 시간을 크게 아낄 수 있다.
- `cpuid` 호출은 프로그램에서 상대적으로 드물게 등장하므로(일반 함수 로직에 비해), Strings/Xref로 그 사용처를 전수 조사하는 것이 현실적이다.

## 가장 먼저 할 것
`cpuid`를 봤다면 가장 먼저 확인할 것:
1. **직전에 `EAX`(그리고 필요하면 `ECX`)에 어떤 leaf 번호가 들어갔는지.** `1`이면 기능 플래그/하이퍼바이저 비트, `0x40000000`이면 하이퍼바이저 벤더 문자열이다.
2. **`cpuid` 직후 결과 레지스터(`EBX`/`ECX`/`EDX`)를 어떻게 쓰는지** — 특정 비트 하나만 `test`하는지, 문자열째로 `cmp`하는지.
3. **그 결과가 곧바로 조건 분기로 이어지는지** — 이어진다면 안티VM/안티분석일 가능성이 높다. 단순히 다른 최적화 코드 경로(AVX vs 일반)로만 갈리면 정상적인 기능 감지다.

## 단계별 절차
1. `cpuid` 직전 줄에서 `EAX`에 세팅된 leaf 번호를 확인한다(`mov eax, 1`, `mov eax, 40000000h` 등).
2. leaf 번호를 본문의 표(또는 Intel SDM)와 대조해 무엇을 조회하는지 특정한다.
3. `cpuid` 직후 코드에서 `EBX`/`ECX`/`EDX` 중 무엇을 검사하는지 본다 — `test ecx, 80000000h`이면 하이퍼바이저 비트 검사, 문자열 상수와 `cmp`하면 벤더 문자열 비교다.
4. IDA Strings 창(`Shift+F12`)에서 `"VMware"`, `"VBox"`, `"KVM"`, `"Microsoft Hv"` 같은 키워드를 검색해서 이 `cpuid` 코드와 같은 함수에 있는지 대조하면 안티VM 여부를 빠르게 확증할 수 있다.
5. 결과 레지스터를 따라가는 분기(`jnz`/`je` 등)의 목표 블록으로 이동해서 "탐지됨" 처리(조용히 종료, 다른 동작 등)가 있는지 확인한다.
6. 우회가 필요하면(교육/CTF 목적) 그 분기 명령을 디버거에서 NOP으로 패치하거나 조건을 반전시켜 실행 흐름을 바꾼다.

## 명령어/단축키
- IDA: `Shift+F12`(Strings 창에서 벤더 문자열 검색), `X`(Xrefs to로 cpuid 사용처 전수 조사), `F5`(디컴파일)
- x64dbg: `cpuid` 명령에 브레이크포인트(`F2`) 후 `F9`로 실행, 레지스터 패널에서 `EAX`/`EBX`/`ECX`/`EDX` 확인, 분기 명령을 우클릭 → "Assemble"로 조건 반전 패치
- GDB/Pwndbg: `break *0x<cpuid주소>`, `stepi`로 한 줄 실행 후 `info registers eax ebx ecx edx`, `p/x $ecx`로 특정 비트만 빠르게 확인

## 흔한 실수
- `CPUID`를 CALL처럼 특정 함수로 착각하는 것 — 이는 하드웨어 명령어이며 오퍼랜드가 없다(입력은 레지스터에 미리 세팅).
- `EAX`(leaf) 값을 백업하지 않고 나중에 다시 쓰려는 것 — `CPUID` 실행 자체가 `EAX`를 결과값으로 덮어쓴다.
- 하이퍼바이저 비트(`ECX` bit 31, leaf 1)를 다른 기능 비트와 혼동하는 것 — 정확한 비트 위치를 매뉴얼로 재확인해야 한다.
- 모든 `cpuid` 호출을 안티VM으로 단정하는 것 — 실제로는 CPU 기능 감지용(SSE/AVX 지원 확인)이 더 흔하다. 뒤따르는 비교 대상이 무엇인지 반드시 확인한다.

## 막혔을 때 다음 체크
- `cpuid` 직전 `EAX`(및 `ECX`) 값이 궁금하면 → 역추적해서 leaf/sub-leaf 번호를 특정하고 Intel SDM에서 해당 leaf의 출력 정의를 찾는다.
- 이게 안티VM인지 기능 감지인지 헷갈리면 → 뒤이은 비교/분기가 문자열(벤더) 비교인지 특정 비트(SSE/AVX 등 알려진 기능 비트) 비교인지 확인한다.
- VM 안에서 실행할 때 프로그램이 이상하게 동작하면 → `cpuid` 호출 위치에 브레이크포인트를 걸고 leaf 1, `ECX` bit 31 검사 여부부터 확인한다.

## 미니 예제

**예제 1 — 하이퍼바이저 비트 검사 (가장 흔한 안티VM 1단계)**
```asm
mov     eax, 1
cpuid
test    ecx, 80000000h   ; bit 31
jnz     is_virtual_machine
```

**예제 2 — 하이퍼바이저 벤더 문자열 조회 및 비교**
```asm
mov     eax, 40000000h
cpuid
; ebx:ecx:edx 에 12바이트 벤더 문자열이 담김
cmp     ebx, 'ausV'      ; "VMwareVMware" 앞 4바이트("Vmwa"를 리틀엔디안 dword로 비교)와 대조 (예시)
je      detected_vmware
```

**예제 3 — 정상적인 CPU 기능 감지 (SSE4.2 지원 확인, 안티VM 아님)**
```c
if (__builtin_cpu_supports("sse4.2")) {
    // SSE4.2 최적화 경로
}
```
```asm
mov     eax, 1
cpuid
test    ecx, 100000h   ; SSE4.2 지원 비트(bit 20)
jz      use_fallback_path
```

**예제 4 — CPUID + RDTSC 결합 타이밍 기반 VM 탐지**
```asm
rdtsc
shl     rdx, 32
or      rax, rdx
mov     r15, rax        ; 시작 타임스탬프 저장

mov     eax, 1
cpuid                    ; 하이퍼바이저에서 트랩되어 비정상적으로 느린 명령

rdtsc
shl     rdx, 32
or      rax, rdx
sub     rax, r15          ; 경과 사이클 수
cmp     rax, THRESHOLD
ja      likely_vm_or_debugger
```

## 관련 글
- [rev-0087-rdtsc.md](./rev-0087-rdtsc.md) — RDTSC: 타이밍 측정과 안티디버깅 (CPUID와 결합되는 타이밍 기반 탐지 기법)
- [rev-0071-call.md](./rev-0071-call.md) — CALL: 함수 호출, 반환 주소, 인자 추적

## 출처/검증
- `CPUID` 명령어 동작과 leaf별 반환 정의: Intel 64 and IA-32 Architectures Software Developer's Manual, Volume 2A, "CPUID—CPU Identification" 섹션 기준 (2026-09-08 검증).
- 하이퍼바이저 존재 비트(leaf 1, `ECX` bit 31)와 하이퍼바이저 벤더 leaf(`0x40000000`): Intel SDM 및 Microsoft "Hypervisor Top Level Functional Specification" 공식 문서 기준.
- VMware/VirtualBox/KVM/Hyper-V 하이퍼바이저 벤더 문자열: 각 하이퍼바이저 공식 문서 및 공개된 CPUID 참조 자료 기준.
