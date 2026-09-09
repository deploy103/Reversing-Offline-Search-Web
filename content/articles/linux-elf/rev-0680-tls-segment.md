---
id: REV-0680
title: "Thread Local Storage가 ELF에서 구현되는 방식(TLS 세그먼트)"
slug: "rev-0680-tls-segment"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["TLS", "PT_TLS", ".tdata", ".tbss", "TCB", "thread pointer", "__thread", "fs:0x28", "TPOFF", "__tls_get_addr"]
aliases: ["tls가 뭔가요", "pt_tls 세그먼트", "thread local storage 구현 원리", "__thread 변수 어셈블리"]
symptom_keywords: ["readelf -l에 tls 세그먼트가 보임", "gdb에서 fs 레지스터로 접근하는 변수가 뭔지 모르겠음", "__thread로 선언한 변수가 disassembly에서 이상하게 보임", "tbss와 tdata 차이를 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`__thread`로 선언된 스레드별 전역 변수는 ELF의 `PT_TLS` 프로그램 헤더가 가리키는 `.tdata`/`.tbss` 템플릿을 스레드 생성 시마다 복제해서 만들어지며, x86-64 리눅스에서는 이 데이터가 `fs` 세그먼트 레지스터가 가리키는 스레드 제어 블록(TCB) 바로 앞의 음수 오프셋 영역에 배치된다.

## 언제 검색해야 하나
- `readelf -l ./chall`에서 `TLS` 타입의 프로그램 헤더를 발견했는데 이게 뭔지 모를 때
- 디스어셈블리에서 `mov eax, DWORD PTR fs:0xfffffffffffffffc` 같은, 음수처럼 보이는 오프셋으로 `fs`를 참조하는 코드를 만났을 때
- 소스에 `__thread int counter;` 또는 `thread_local` 변수가 있는데 컴파일된 결과에서 이게 전역 변수와 다르게 컴파일되는 이유가 궁금할 때
- REV-0676(AT_RANDOM과 스택 카나리)에서 언급된 `fs:0x28`이 TLS와 무슨 관계인지 더 깊이 알고 싶을 때
- `__tls_get_addr` 함수 호출이 왜 등장하는지 궁금할 때

## 핵심 개념

### TLS가 필요한 이유
멀티스레드 프로그램에서 스레드마다 독립적인 값을 가져야 하는 전역 변수가 있다(예: `errno`, 각 스레드의 난수 시드, 각 스레드 전용 캐시 포인터). 일반 전역 변수는 프로세스 전체에서 단 하나의 메모리 위치를 공유하므로 스레드 안전하지 않다. C11의 `_Thread_local`(또는 GCC 확장 `__thread`, C++11 `thread_local`)로 선언하면, 컴파일러/링커/런타임이 협력해서 "같은 심볼이지만 스레드마다 서로 다른 실제 메모리"를 갖도록 만들어준다.

### ELF가 TLS를 표현하는 방법: PT_TLS
컴파일러는 TLS 변수를 일반 `.data`/`.bss`가 아니라 별도의 섹션인 `.tdata`(초기값이 있는 TLS 변수)와 `.tbss`(0으로 초기화되는 TLS 변수)에 배치한다. 링커는 이 두 섹션을 하나의 **PT_TLS 프로그램 헤더**로 묶는다. 이 세그먼트는 실행 파일에 실제로 매핑되는 데이터가 아니라, 스레드가 생성될 때마다 복제할 **템플릿**이다.
```
readelf -l ./chall 예시:
  Type   Offset             VirtAddr           PhysAddr
         FileSiz            MemSiz              Flags  Align
  TLS    0x0000000000002dc0 0x0000000000003dc0 0x0000000000003dc0
         0x0000000000000004 0x0000000000000008  R      0x4
```
여기서 `FileSiz`(파일에 실제로 존재하는 초기값 크기, `.tdata` 분량)와 `MemSiz`(런타임에 필요한 전체 크기, `.tdata` + `.tbss`)가 다르다는 점이 중요하다. `MemSiz`가 `FileSiz`보다 크면 그 차이만큼은 `.tbss`이며, 스레드 생성 시 0으로 채워진다.

### 런타임에 스레드마다 어떻게 복제되는가
프로세스(메인 스레드)가 시작될 때, 그리고 `pthread_create`로 새 스레드가 만들어질 때마다, 런타임(정적 바이너리는 자체 초기화 코드가, 동적 바이너리는 `ld.so`/`pthread` 라이브러리가)은 다음을 수행한다.
1. `PT_TLS` 세그먼트가 지정한 크기만큼 메모리를 새로 할당한다.
2. `.tdata`의 초기값을 그 메모리에 복사하고, 나머지(`.tbss` 분량)는 0으로 채운다.
3. 이 TLS 블록을 가리키는 **스레드 제어 블록(TCB)**을 만들고, CPU의 세그먼트 레지스터(x86-64는 `fs`, x86은 `gs`)의 베이스를 이 TCB 주소로 설정한다(`arch_prctl(ARCH_SET_FS, ...)` 시스템 콜, 또는 `set_thread_area`).

### x86-64 리눅스의 TLS 메모리 배치 (Variant II)
리눅스 x86-64는 "Variant II" TLS 모델을 쓴다. 이 모델의 특징은 스레드 포인터(`fs:0`)가 **TCB 자신을 가리키고, TLS 변수들은 TCB보다 낮은 주소(음수 오프셋)에 배치된다**는 점이다.
```
낮은 주소 ─────────────────────────────────────────► 높은 주소
[ TLS 블록 (.tdata + .tbss 복사본) ][ TCB (tcbhead_t) ] ← fs:0이 여기를 가리킴
                                     ^ stack_guard는 TCB 안 offset 0x28
```
그래서 컴파일러가 생성하는 "Local Exec"(자기 실행 파일 안에 정의된 TLS 변수에 접근하는, 가장 흔한) 모델의 코드는 다음과 같은 형태를 띤다.
```asm
mov eax, DWORD PTR fs:0xfffffffffffffffc   ; fs + (-4) 위치의 4바이트 읽기
```
`0xfffffffffffffffc`는 64비트로 표현된 `-4`다. 즉 `fs` 베이스보다 4바이트 낮은 주소에 있는 TLS 변수를 읽는 코드다. 링커가 이 음수 오프셋(TPOFF, Thread Pointer OFFset)을 `R_X86_64_TPOFF64` 재배치로 계산해서 채워 넣는다.

### TLS 접근 모델 4가지
컴파일러는 그 변수가 정의된 위치(같은 실행 파일 안인지, 공유 라이브러리인지)와 링크 방식에 따라 4가지 접근 모델 중 하나를 고른다.
- **Local Exec (LE)**: 실행 파일 자신에 정의된 TLS 변수. 가장 빠름 — 위 예시처럼 `fs:상수오프셋`으로 직접 접근.
- **Initial Exec (IE)**: 프로그램 시작 시 로드가 확정되는 공유 라이브러리의 TLS 변수. GOT에 있는 오프셋 값을 한 번 읽은 뒤 `fs`에 더해서 접근(`R_X86_64_GOTTPOFF`).
- **Local Dynamic (LD)**: 같은 모듈 내 여러 TLS 변수를 한 번의 `__tls_get_addr` 호출로 묶어 접근. dlopen처럼 나중에 로드될 수 있는 모듈에서 씀.
- **General Dynamic (GD)**: 가장 범용적이지만 가장 느림. 매 접근마다 `__tls_get_addr(모듈ID, 오프셋)`을 호출해서 주소를 구한다. `dlopen`된 라이브러리의 TLS 변수 등에 쓰인다.

리버싱 중 `call __tls_get_addr@PLT` 호출이 보이면 GD/LD 모델이 쓰인 TLS 접근이라고 판단하면 된다.

### fs:0x28 카나리와의 연결
REV-0676에서 다룬 스택 카나리(`__stack_chk_guard`)는 사실 TCB(`tcbhead_t`) 구조체의 `stack_guard` 필드이며, 이 필드가 ��확히 `fs:0x28`에 위치한다. 즉 스택 카나리는 "TLS 메커니즘이 제공하는 인프라(스레드별 고정 오프셋 접근)"를 그대로 재활용해서 구현된 것이다 — glibc 입장에서는 카나리도 "스레드마다 다를 수 있는 값"이므로 TCB에 두는 것이 자연스럽다.

## 화면/코드에서 보이는 징후
- `readelf -l ./chall`에 `TLS` 타입 프로그램 헤더가 존재한다.
- 디스어셈블리에 `fs:` 또는 `gs:` 세그먼트 접두사가 붙은 메모리 접근이 `fs:0x28`(카나리) 외에도 여러 개 보인다.
- 심볼 테이블(`nm`, `readelf -s`)에서 특정 변수의 타입이 `TLS`로 표시된다(`nm`에서는 소문자 `b`가 아니라 별도 표기가 나올 수 있음, `readelf -s` 출력의 `Type` 칸에 `TLS`).
- `call __tls_get_addr` 호출 직전에 `lea rdi, [rip+오프셋]`으로 `(모듈ID, 오프셋)` 쌍을 가리키는 GOT 참조가 보인다.

## 가장 먼저 할 것
`readelf -l`으로 `PT_TLS` 세그먼트의 유무와 `FileSiz`/`MemSiz`를 확인한다. 세그먼트가 없으면 이 바이너리는 `__thread` 변수를 쓰지 않는다는 뜻이므로 TLS 관련 코드 경로를 신경 쓸 필요가 없다. 있다면 `MemSiz - FileSiz`로 `.tbss` 크기를 계산해두면, 이후 디스어셈블리에서 나오는 음수 오프셋들이 이 범위 안에 있는지 가늠할 수 있다.

## 단계별 절차

**1) PT_TLS 세그먼트 확인**
```bash
readelf -l ./chall | grep -A1 TLS
```

**2) .tdata/.tbss 섹션 크기 확인**
```bash
readelf -S ./chall | grep -E '\.tdata|\.tbss'
```

**3) TLS 심볼 목록 확인**
```bash
readelf -s ./chall | awk '$4=="TLS"'
```

**4) GDB에서 fs 베이스와 TLS 변수 실측**
```gdb
break main
run
p/x $fs_base
x/4xb $fs_base-4     ; Local Exec 모델의 예시 오프셋
```

**5) 재배치 타입으로 접근 모델 판별**
```bash
readelf -r ./chall | grep -E 'TPOFF|DTPMOD|DTPOFF|TLSGD|TLSLD|GOTTPOFF'
```
`TPOFF64`만 보이면 Local/Initial Exec 위주, `DTPMOD64`/`DTPOFF64`가 함께 보이면 Dynamic 모델(GD/LD)이 쓰인 것이다.

## 명령어/단축키
```bash
readelf -l ./chall | grep -A1 TLS
readelf -S ./chall | grep tls
readelf -s ./chall | grep TLS
readelf -r ./chall | grep -i tpoff
```
GDB: `p/x $fs_base`, `x/Nxb $fs_base+오프셋`

## 출력 해석
- `PT_TLS`의 `Align` 칸(예: `0x8`)은 TLS 블록의 정렬 요구사항이다 — TCB 바로 앞에 배치될 때 이 정렬을 맞춰야 한다.
- `FileSiz`가 0이고 `MemSiz`만 있으면, 그 실행 파일의 TLS 변수는 전부 0으로 초기화되는 것들(`.tbss`만 존재)이라는 뜻이다.
- `readelf -r` 결과에 `R_X86_64_DTPMOD64`가 보이면 "이 변수가 속한 모듈(공유 라이브러리 또는 실행 파일)의 ID"를 런타임에 채워 넣으라는 재배치이고, `R_X86_64_DTPOFF64`는 "그 모듈 내에서의 오프셋"을 채우라는 재배치다.

## 흔한 실수
- TLS 변수를 일반 전역 변수와 동일하게 취급해서 GDB `p 변수명`으로 바로 값을 보려 하는 것 — 스레드별로 실제 메모리 위치가 다르므로, 현재 어떤 스레드 컨텍스트에서 보는지(`thread N` 명령으로 전환했는지)에 따라 값이 달라질 수 있다.
- `fs:` 오프셋을 전부 카나리라고 착각하는 것 — `fs:0x28`은 카나리이지만, 그 외의 음수/양수 오프셋은 다른 TLS 변수이거나 `errno`, `pthread_self()` 관련 필드일 수 있다.
- Variant II(x86-64 리눅스)와 Variant I(TLS 블록이 TCB 뒤, 양수 오프셋에 오는 일부 다른 아키텍처/ABI) 모델을 혼동하는 것 — 아키텍처마다 TLS 배치 방향이 다를 수 있다.
- `__tls_get_addr` 호출을 그냥 평범한 함수 호출로 넘겨버리고 그 반환값이 "그 스레드의 TLS 변수 주소"라는 걸 놓치는 것.

## 막혔을 때 다음 체크
- `fs:0x28` 카나리와 TCB의 관계를 먼저 보고 싶다면 → REV-0676 AT_RANDOM과 스택 카나리 초기화 관계
- 프로그램 헤더/세그먼트의 기본 구조가 헷갈린다면 → REV-0090 ELF Program Header와 Section Header 차이
- `readelf -r`로 다른 종류의 재배치까지 폭넓게 읽는 법이 궁금하다면 → REV-0682 objdump로 relocation 엔트리 읽는 법

## 미니 예제
```c
__thread int counter = 0;

void inc(void) { counter++; }
```
```bash
$ gcc -o demo demo.c && readelf -l demo | grep -A1 TLS
  TLS            0x0000000000002014 0x0000000000004014 0x0000000000004014
                 0x0000000000000004 0x0000000000000004  R      0x4

$ objdump -d demo | grep -A3 '<inc>:'
0000000000001149 <inc>:
    1149: mov    eax,DWORD PTR fs:0xfffffffffffffffc
    1150: add    eax,0x1
    1153: mov    DWORD PTR fs:0xfffffffffffffffc,eax
```
`fs:0xfffffffffffffffc`(= `fs` - 4)가 바로 `counter` 변수의 Local Exec 접근 코드이며, `PT_TLS`의 `MemSiz`가 4바이트인 것과 정확히 대응된다.

## 관련 글
- REV-0676 — AT_RANDOM과 스택 카나리 초기화 관계
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0682 — objdump로 relocation 엔트리 읽는 법
- REV-0677 — ELF Auxiliary Vector(auxv) 개요

## 출처/검증
- PT_TLS 세그먼트, `.tdata`/`.tbss` 구조 및 Variant II(x86-64) TLS 메모리 배치: Ulrich Drepper, "ELF Handling For Thread-Local Storage" (구 프리스케일/레드햇 공식 TLS ABI 문서)의 x86-64 Variant II 설명 기준.
- `fs`/`gs` 세그먼트 레지스터를 통한 TCB 접근과 `tcbhead_t`의 `stack_guard` 필드 오프셋(`0x28`): glibc `sysdeps/x86_64/nptl/tls.h` 및 관련 초기화 코드 기준.
- TLS 접근 모델 4종(GD/LD/IE/LE)과 관련 재배치 타입(`R_X86_64_TLSGD`, `TLSLD`, `GOTTPOFF`, `TPOFF64`, `DTPMOD64`, `DTPOFF64`): System V x86-64 psABI 문서의 TLS 재배치 표 기준 (2026-09-08 검증).
