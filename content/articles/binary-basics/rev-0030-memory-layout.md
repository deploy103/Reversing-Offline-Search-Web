---
id: REV-0030
title: "Code Data BSS Stack Heap 기초"
slug: "rev-0030-memory-layout"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords: ["메모리 레이아웃", "memory layout", ".text", ".data", ".bss", "스택", "힙", "stack", "heap", "code segment"]
aliases: ["프로세스 메모리 구조", "메모리 맵이 뭔가요", "스택 힙 차이", "bss가 뭔가요"]
symptom_keywords: ["이 주소가 스택인지 힙인지 모르겠음", "access violation 주소가 어디 영역인지 모르겠음", "bss 섹션이 파일에 없는데 왜 크기가 있는지 모르겠음", ".text .data .bss 차이를 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
실행 파일이 프로세스로 뜨면 메모리 공간은 목적에 따라 **코드(.text), 초기화된 데이터(.data), 초기화 안 된 데이터(.bss), 힙(heap), 스택(stack)** 으로 나뉘어 배치되며, 디버거에서 보는 모든 주소는 반드시 이 중 하나에 속한다.

## 언제 검색해야 하나
- 디버거에서 어떤 주소를 보고 "이게 코드 영역이야, 데이터야, 스택이야?"를 판단해야 할 때
- Access Violation / Segmentation Fault가 난 주소가 어느 영역인지 확인해야 할 때
- IDA의 Segments 창이나 ELF의 `.text`, `.data`, `.bss` 섹션 이름이 무슨 뜻인지 모를 때
- 스택 오버플로우와 힙 오버플로우가 왜 다른 취약점인지 헷갈릴 때

## 핵심 개념
프로그램이 실행되면 운영체제(로더)는 실행 파일의 내용을 읽어서 프로세스의 가상 주소 공간(virtual address space)에 배치한다. 이 공간은 대략 다음과 같은 순서로 구성된다(낮은 주소 → 높은 주소, 실제 배치는 ASLR로 매번 무작위화된다):

```
낮은 주소
+-------------------+
|  Code (.text)     |  실행 가능한 명령어. 보통 읽기+실행(R-X), 쓰기 금지
+-------------------+
|  Data (.data)     |  초기값이 있는 전역/정적 변수. 읽기+쓰기(RW)
+-------------------+
|  BSS (.bss)       |  초기값이 없는(=0으로 초기화되는) 전역/정적 변수. RW
+-------------------+
|  Heap             |  malloc/new로 동적 할당되는 영역. 낮은 주소에서 위로 자람
|        ↓ (자라는 방향)
|        ...
|        ↑ (자라는 방향)
|  Stack            |  함수 호출마다 쓰는 지역 변수/리턴 주소. 높은 주소에서 아래로 자람
+-------------------+
높은 주소
```

각 영역의 역할:

- **Code(.text)**: 컴파일된 기계어 명령어가 그대로 들어 있다. IDA/Ghidra에서 디스어셈블리로 보는 부분이 바로 여기다. 실행 권한(X)은 있지만 대부분 쓰기 권한(W)은 없다 — 코드가 실행 중에 스스로를 덮어쓰지 못하게 막는 보안 장치(W^X, DEP/NX)다.
- **Data(.data)**: `int g_count = 5;`처럼 **컴파일 시점에 이미 값이 정해진** 전역/정적 변수가 들어간다. 실행 파일 자체에 초기값이 저장되어 있으므로 파일 크기에 영향을 준다.
- **BSS(.bss)**: `int g_buffer[1000];`처럼 **초기값을 명시하지 않은(=0으로 초기화되는)** 전역/정적 변수가 들어간다. BSS는 "Block Started by Symbol"의 약자로, 실제 값은 전부 0이라는 사실만 헤더에 적혀 있고 **파일에는 실제 데이터가 저장되지 않는다** — 로더가 프로세스를 띄울 때 그만큼의 공간을 0으로 채워서 만들어준다. 그래서 1000개짜리 배열을 0으로만 선언해도 실행 파일 용량은 거의 늘지 않는다.
- **Heap**: `malloc`, `new`, Windows의 `HeapAlloc` 등으로 **실행 중에 동적으로** 요청한 메모리가 배치되는 영역이다. 프로그래머가 명시적으로 해제(`free`, `delete`)하기 전까지 유지된다. 낮은 주소에서 높은 주소 방향으로 자라는 게 일반적이다.
- **Stack**: 함수가 호출될 때마다 그 함수의 지역 변수, 저장된 레지스터, 리턴 주소가 쌓이는 영역이다. 함수가 리턴하면 자동으로 정리된다. 대부분의 x86/x64 환경에서는 **높은 주소에서 낮은 주소 방향으로** 자란다(스택 프레임의 구체적인 동작은 REV-0031에서 다룬다).

PE(Windows)와 ELF(Linux)는 이름은 다르지만 개념은 동일하게 대응한다:

| 개념 | PE(Windows) 섹션 | ELF(Linux) 섹션 |
|---|---|---|
| 코드 | `.text` | `.text` |
| 초기화된 데이터 | `.data` | `.data` |
| 초기화 안 된 데이터 | `.bss` | `.bss` |
| 읽기 전용 데이터(문자열, 상수) | `.rdata` | `.rodata` |
| 임포트 테이블 | `.idata` | `.dynamic`/`.got`/`.plt` |

실제 프로세스 주소는 실행할 때마다 ASLR(Address Space Layout Randomization)로 랜덤화되지만, **각 영역 간의 상대적인 순서와 역할**은 항상 동일하다. 그래서 리버싱할 때는 "절대 주소가 몇 번지냐"보다 "이 주소가 어느 영역에 속하냐"를 먼저 파악하는 습관이 중요하다.

## 화면/코드에서 보이는 징후
- IDA의 **Segments** 창(단축키 `Shift+F7`)에 `.text`, `.data`, `.bss`, `.rdata` 같은 이름과 각 세그먼트의 시작/끝 주소, 권한(R/W/X)이 나열된다.
- x64dbg의 **Memory Map** 탭(`Alt+M`)에 실행 파일이 로드된 여러 영역과 함께 `Heap`, 스레드별 `Stack` 영역이 별도로 표시된다.
- 디버거에서 크래시가 났을 때 주소가 `00007FF6...`처럼 이미지 베이스 근처면 코드/데이터, `000000...` 스택 근처의 큰 값이면 스택, `힙 핸들` 근처 주소면 힙일 가능성이 높다(정확히는 반드시 메모리 맵으로 확인해야 한다).
- 디컴파일된 코드에서 전역 변수는 `dword_140012000` 같은 고정 주소 이름으로, 스택 변수는 `[rbp-8]`처럼 레지스터 상대 오프셋으로, 힙 포인터는 `malloc`/`operator new` 반환값을 담은 변수로 구분되어 나타난다.

## 가장 먼저 할 것
의심스러운 주소를 만나면 우선 **디버거의 메모리 맵(Memory Map)** 을 열어서 그 주소가 어느 영역에 속하는지부터 확인한다. 영역을 알면 "이건 전역 변수구나", "이건 malloc으로 받은 버퍼구나", "이건 지역 변수구나"처럼 코드의 의도를 훨씬 빠르게 짐작할 수 있다.

## 단계별 절차

**1) 정적 분석에서 섹션 구조 확인하기 (IDA/Ghidra)**

IDA에서 `Shift+F7`로 Segments 창을 열면 파일에 존재하는 모든 세그먼트와 각 세그먼트의 시작 주소, 크기, 권한을 볼 수 있다. `.text`는 실행 코드, `.data`/`.bss`는 전역 변수, `.rdata`/`.rodata`는 문자열 리터럴과 상수 테이블이 위치한다.

**2) 명령줄 도구로 섹션 헤더 확인하기 (Linux/ELF)**

```bash
readelf -S ./target
```
출력에서 `.text`, `.data`, `.bss` 행의 `Addr`(가상 주소), `Size`, `Flg`(플래그: `A`=Alloc, `X`=실행, `W`=쓰기)를 확인한다. `.bss`는 `Type`이 `NOBITS`로 표시되는데, 이는 "파일에는 실제 바이트가 없고 로드 시 0으로 채워지는 영역"이라는 뜻이다.

**3) Windows PE에서 섹션 헤더 확인하기**

```bash
dumpbin /headers target.exe
```
또는 PE-bear 같은 GUI 툴로 열어서 `.text`, `.data`, `.rdata`, `.bss`(있는 경우) 섹션의 `VirtualAddress`, `VirtualSize`, `Characteristics`(권한 플래그)를 확인한다.

**4) 실행 중인 프로세스의 실제 메모리 맵 보기**

Linux:
```bash
cat /proc/<pid>/maps
```
또는 GDB/Pwndbg 안에서:
```
(gdb) info proc mappings
pwndbg> vmmap
```

Windows(x64dbg):
`Alt+M`로 Memory Map 탭을 열면 이미지의 각 섹션, 힙, 여러 스레드의 스택이 표에 나열된다. `Protection` 열에서 `RWE`, `R`, `RW` 등을 확인할 수 있다.

**5) 주소를 영역과 대조하기**

크래시 주소나 궁금한 주소를 위 목록의 시작~끝 범위와 대조해서 "이 주소는 스택 영역 안에 있다" 혹은 "힙 청크 안에 있다"는 식으로 결론을 낸다.

## 명령어/단축키
```bash
readelf -S ./target          # ELF 섹션 헤더
readelf -l ./target          # ELF 프로그램 헤더(세그먼트, 런타임 매핑 단위)
objdump -h ./target          # 섹션 헤더 요약
dumpbin /headers target.exe  # PE 헤더/섹션 (Windows, Visual Studio 도구)
cat /proc/<pid>/maps         # 실행 중 프로세스 메모리 맵 (Linux)
```
IDA: `Shift+F7` (Segments 창)
x64dbg: `Alt+M` (Memory Map)
GDB/Pwndbg: `info proc mappings` / `vmmap`

## 출력 해석
- `readelf -S`에서 `.bss`의 `Type`이 `NOBITS`로 나오면 정상이다 — 파일 오프셋은 있지만 실제 데이터가 저장되지 않는다는 뜻이다.
- 메모리 맵에서 권한이 `r-xp`(Linux) 또는 `RX`(Windows)로 표시된 영역은 코드 영역이다. 이런 영역에 대한 쓰기 시도는 크래시(Access Violation/SIGSEGV)를 일으킨다.
- `rw-p`/`RW`로 표시된 영역은 데이터, BSS, 힙, 스택 후보다 — 이름(`[heap]`, `[stack]`, 매핑된 파일명)까지 함께 봐야 정확히 구분된다.
- Linux `/proc/pid/maps`에서 `[heap]`, `[stack]` 태그가 붙은 줄이 각각 힙과 메인 스레드 스택이다.

## 흔한 실수
- 스택과 힙을 혼동하는 것 — 스택은 함수 호출/리턴에 따라 자동으로 관리되는 반면, 힙은 프로그래머가 `malloc`/`free`로 직접 관리해야 한다. "스택 오버플로우(재귀 무한 호출 등)"와 "힙 오버플로우(버퍼 경계를 넘어선 쓰기)"는 완전히 다른 종류의 버그다.
- `.bss`에 있는 배열을 "파일 안에 큰 데이터 블록이 있겠지"라고 착각하는 것 — 실제로는 파일에 아무 내용도 없고 로더가 런타임에 0으로 채운다.
- 한 번 실행에서 확인한 절대 주소를 다른 실행에서도 그대로 쓸 수 있다고 가정하는 것 — ASLR이 켜져 있으면 매 실행마다 코드/힙/스택의 베이스 주소가 바뀐다. 다만 각 영역 간의 상대적인 크기와 순서는 유지된다.
- `.text`(코드)에 쓰기 권한이 없다는 사실을 잊고, 코드를 패치하려다가 권한 오류를 만나는 것 — 코드 패치는 디버거의 메모리 보호 속성을 바꾸거나(x64dbg의 메모리 맵에서 우클릭 → 권한 변경), 정적으로 파일을 수정한 뒤 다시 실행해야 한다.

## 막혔을 때 다음 체크
- 스택 안에서 정확히 지역 변수/리턴 주소가 어떻게 배치되는지 궁금하면 → REV-0031(스택 프레임)로 이동.
- 함수 인자와 반환값이 스택/레지스터 중 어디에 있는지 궁금하면 → REV-0032(함수 인자와 반환값 위치)로 이동.
- 전역 변수나 힙 포인터를 역참조하는 어셈블리 코드를 읽는 법이 궁금하면 → REV-0033(포인터와 역참조)으로 이동.
- 심볼이 없어서 `.text`/`.data` 안의 함수와 변수 이름을 알아볼 수 없다면 → REV-0038(심볼 vs Stripped 바이너리)로 이동.

## 미니 예제
다음 C 코드를 컴파일해서 각 변수가 어느 영역에 배치되는지 살펴보자.

```c
#include <stdlib.h>

int g_initialized = 42;     // .data  : 초기값이 있는 전역 변수
int g_zeroed[1000];         // .bss   : 초기값이 없는 전역 변수(자동 0)

int main(void) {
    int local = 10;                    // Stack : 지역 변수
    int *heap_buf = malloc(4 * 100);   // Heap  : malloc이 반환한 포인터가 가리키는 곳
    heap_buf[0] = local;
    free(heap_buf);
    return 0;
}
```

GDB로 각 주소가 실제로 어느 영역에 속하는지 확인할 수 있다:

```
(gdb) break main
(gdb) run
(gdb) print &g_initialized
$1 = (int *) 0x5555555580 <g_initialized>
(gdb) print &g_zeroed
$2 = (int (*)[1000]) 0x5555555600 <g_zeroed>
(gdb) print &local
$3 = (int *) 0x7fffffffe4bc     # 스택 영역(높은 주소대)
(gdb) print heap_buf
$4 = (int *) 0x555555559260     # 힙 영역
```

전역 변수 두 개의 주소는 실행 파일 베이스 근처의 낮은 주소대에, `local`의 주소는 `0x7fff...`로 시작하는 스택 영역에, `heap_buf`가 가리키는 주소는 그 사이 어딘가의 힙 영역에 위치하는 것을 볼 수 있다. `info proc mappings`로 각 주소 범위를 대조하면 정확히 어떤 영역인지 확인할 수 있다.

## 관련 글
- REV-0024 — 2의 보수와 음수 표현
- REV-0031 — 스택 프레임이 무엇인지
- REV-0032 — 함수 인자와 반환값이 어디에 있는지
- REV-0033 — 포인터와 역참조를 어셈블리에서 읽는 법
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 출처/검증
- ELF 섹션/세그먼트 구조: System V Application Binary Interface 및 `man 5 elf` 기준 일반 개념 설명 (2026-09-08 검증).
- PE 섹션 구조: Microsoft PE Format 공식 문서(`.text`/`.data`/`.rdata`/`.bss` 관례) 기준.
- BSS의 `NOBITS` 저장 방식: `readelf`/`objdump` 표준 동작 및 ELF 스펙 기준.
