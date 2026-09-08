---
id: REV-0019
title: "바이너리와 실행 파일의 기본 구조"
slug: "rev-0019-binary-basics"
category: "binary-basics"
difficulty: "beginner"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [file, readelf, objdump, HxD, "PE-bear", "Detect It Easy", IDA]
keywords: ["바이너리 구조", "실행 파일 구조", "ELF 헤더", "PE 헤더", "entry point", "진입점", "컴파일 링크 과정", "OS 로더"]
aliases: ["바이너리가 뭔지 모르겠음", "실행파일 안에 뭐가 들었는지", "exe 구조가 궁금함", "elf가 뭔지 모르겠음", "실행 파일 만들어지는 과정이 궁금함"]
symptom_keywords: ["바이너리 파일 열었는데 뭐가뭔지 모르겠음", "실행 파일 구조를 전혀 모르겠음", "entry point가 뭔지 모르겠음", "main이 왜 시작점이 아닌지 모르겠음", "readelf 출력이 무슨 뜻인지 모르겠음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
바이너리(실행 파일)는 컴파일러와 링커를 거쳐 만들어진 **기계어 코드와 데이터의 바이트 나열**이며, Windows의 PE와 Linux의 ELF는 형식은 달라도 공통적으로 "헤더(매직 바이트 + 메타데이터) + 섹션/세그먼트 테이블 + 실제 코드/데이터 + entry point(진입점) 주소"라는 골격을 갖는다.

## 언제 검색해야 하나
- 리버싱을 막 시작했는데 "바이너리 안에 대체 뭐가 들어있는가"부터 감이 안 잡힐 때
- `file`, `readelf -h`, `dumpbin /headers` 같은 명령을 처음 쳐보고 출력이 무슨 뜻인지 모를 때
- IDA/Ghidra로 파일을 열었을 때 "Entry point"라고 표시되는 주소가 왜 `main()`이 아닌지 궁금할 때
- 실행 파일이 어떻게 메모리에 올라가서 실행되는지, OS가 정확히 무슨 일을 하는지 궁금할 때

## 핵심 개념

### 바이너리란 무엇인가
"바이너리(binary)"는 사람이 읽는 소스 코드(`.c`, `.cpp` 등)가 **컴파일러**를 거쳐 CPU가 직접 실행할 수 있는 기계어(machine code)로 변환된 파일이다. 텍스트 에디터로 열면 대부분 읽을 수 없는 바이트들로 보이는 이유가 이것이다 — 그 바이트들이 곧 CPU 명령어의 opcode이거나, 프로그램이 쓰는 데이터(문자열, 상수, 초기화된 전역 변수 등)다.

바이너리가 만들어지는 과정(컴파일/링크 파이프라인)은 대략 다음과 같다.

1. **소스 코드** (`hello.c`) 작성
2. **컴파일러**(`gcc`, `clang`, `cl.exe` 등)가 소스를 컴파일해서 **오브젝트 파일**(Linux는 `.o`, Windows는 `.obj`)을 만든다. 오브젝트 파일은 이미 기계어로 번역돼 있지만, 아직 최종 실행 파일이 아니다 — 예를 들어 `printf` 같은 외부 함수의 실제 주소를 모르는 "미해결(unresolved) 심볼" 상태다.
3. **링커**(`ld`, `link.exe`)가 여러 오브젝트 파일과 라이브러리(libc, kernel32.dll 등)를 하나로 합치면서, 미해결 심볼들의 실제 주소를 채워 넣고(relocation), 섹션들을 배치하고, 최종 실행 파일 포맷(ELF 또는 PE)으로 출력한다.

즉 `hello.c` → (컴파일) → `hello.o` → (링크) → `hello`(ELF 실행 파일) 또는 `hello.exe`(PE 실행 파일)의 흐름이다.

### PE와 ELF가 공유하는 공통 뼈대
Windows의 PE(Portable Executable)와 Linux의 ELF(Executable and Linkable Format)는 세부 필드 이름과 배치는 다르지만, 개념적으로 동일한 4가지 요소를 갖는다.

| 요소 | ELF에서의 이름 | PE에서의 이름 | 역할 |
|---|---|---|---|
| 헤더 | ELF 헤더 | DOS 헤더 + NT 헤더(파일/옵션 헤더) | 매직 바이트로 포맷 식별, 아키텍처·엔트리포인트 등 메타데이터 |
| 섹션/세그먼트 테이블 | 섹션 헤더 테이블 / 프로그램 헤더 테이블 | 섹션 테이블 | 코드·데이터가 파일의 어디 있고 메모리 어디에 매핑되는지 기술 |
| 실제 콘텐츠 | `.text`, `.data`, `.rodata`, `.bss` 등 | `.text`, `.data`, `.rdata` 등 | 실제 기계어 코드와 상수/변수 데이터 |
| 진입점 | Entry point address | AddressOfEntryPoint | 실행이 시작되는 첫 명령어의 주소 |

두 포맷을 처음 구분하는 방법(매직 바이트로 파일 종류 알아내기)은 [REV-0020](./rev-0020-magic-bytes.md)(Magic Byte와 파일 시그니처)에서 자세히 다룬다. 이 문서에서는 개념적 골격에 집중한다.

### Entry Point는 main()이 아니다
아주 중요한 오해가 하나 있다: **바이너리의 entry point는 `main()` 함수가 아니다.** entry point는 C 런타임(CRT)이 프로그램을 실행할 준비를 하는 작은 시작 스텁(stub)의 주소다.

- Linux/ELF: entry point는 보통 `_start`라는 심볼이다. `_start`는 어셈블리로 작성된 아주 짧은 코드로, `__libc_start_main`을 호출한다. `__libc_start_main`이 `argc`/`argv`/`envp`를 정리하고, 전역 생성자(C++이면 정적 객체 생성자 등)를 실행한 뒤, 비로소 우리가 작성한 `main()`을 호출한다. `main()`이 리턴하면 `exit()`를 호출해서 프로세스를 정리하고 종료한다.
- Windows/PE: entry point는 `mainCRTStartup`(콘솔 프로그램) 또는 `WinMainCRTStartup`(GUI 프로그램)이다. 이 스텁이 CRT 초기화(힙 설정, 표준 입출력 초기화, C++ 정적 생성자 실행 등)를 마친 뒤 우리가 작성한 `main()`이나 `WinMain()`을 호출한다.

그래서 IDA나 Ghidra에서 파일을 처음 열었을 때 "Entry point"로 점프해보면 우리가 짠 코드가 아니라 컴파일러/런타임이 자동으로 넣은 낯선 어셈블리가 나오는 것이 정상이다. 진짜 우리 코드를 보려면 여기서 몇 단계 더 따라가거나(x64 기준 `__libc_start_main` 호출 인자에서 진짜 `main` 주소를 확인), IDA의 함수 목록에서 `main`을 직접 찾아가는 편이 빠르다.

### 이후 시리즈에서 다룰 용어 미리 보기
이 문서는 이후 이어지는 시리즈의 입구다. 아래 용어들은 여기서는 한두 문장으로만 짚고, 각각 전용 문서에서 깊게 다룬다.

- **매직 바이트(Magic Bytes)**: 파일 맨 앞 몇 바이트로 포맷을 식별하는 서명. ELF는 `7F 45 4C 46`(`\x7fELF`), PE는 `4D 5A`(`MZ`)로 시작한다 → [REV-0020](./rev-0020-magic-bytes.md).
- **아키텍처(x86 vs x64)**: 같은 ELF/PE라도 32비트용인지 64비트용인지에 따라 헤더 필드와 레지스터 크기가 다르다 → [REV-0021](./rev-0021-x86-vs-x64.md).
- **레지스터 폭**: 32비트 `EAX`와 64비트 `RAX`처럼 같은 역할의 레지스터가 비트폭만 다르게 존재한다 → [REV-0022](./rev-0022-register-widths.md).
- **엔디안(Endianness)**: 멀티바이트 값을 메모리에 어떤 바이트 순서로 저장하는지. x86/x64는 리틀 엔디안이다 → [REV-0023](./rev-0023-endianness.md).
- **2의 보수**: 음수를 비트로 표현하는 방식(이미 작성된 [REV-0024](./rev-0024-twos-complement.md)에서 상세히 다룸).
- **Signed/Unsigned 해석**: 같은 비트 패턴을 부호 있는 값으로 볼지, 없는 값으로 볼지 → [REV-0025](./rev-0025-signed-unsigned.md).
- **비트 마스크**: `AND` 연산으로 특정 비트폭만 남기는 기법(이미 작성된 [REV-0026](./rev-0026-bit-masks.md)).
- **정수 오버플로/Wraparound**: 값이 표현 범위를 넘을 때 벌어지는 일 → [REV-0027](./rev-0027-integer-overflow.md).
- **VA/RVA/File Offset**: 파일 안에서의 위치와 메모리에 올라간 뒤의 주소가 왜 다른지 → [REV-0028](./rev-0028-va-rva-offset.md).
- **Section vs Segment**: 링커 관점(섹션)과 로더 관점(세그먼트)의 차이 → [REV-0029](./rev-0029-section-vs-segment.md).

## 화면/코드에서 보이는 징후
- 터미널에서 `file 어떤파일`을 쳤을 때 `ELF 64-bit LSB pie executable, x86-64` 같은 문장이 나오는데 각 단어의 의미를 모르는 경우
- `readelf -h`나 `objdump -f`, Windows의 `dumpbin /headers` 출력에 `Entry point address`, `Machine`, `Class` 같은 필드가 나열되는데 뭘 봐야 할지 모르는 경우
- IDA/Ghidra로 파일을 열자마자 진입점으로 이동했더니 `_start`, `mainCRTStartup` 같은 낯선 함수 안에 있고, 우리가 짠 코드가 안 보이는 경우
- PE-bear나 Detect It Easy(DIE)로 파일을 열었을 때 섹션 목록(`.text`, `.data`, `.rdata` 등)과 그 옆의 크기·주소 값들이 나열되는데 전체 그림이 안 잡히는 경우

## 가장 먼저 할 것
분석 대상 파일을 받으면 손대기 전에 항상 **`file` 명령(Linux) 또는 Detect It Easy(Windows)로 파일 종류부터 확인**한다. 진짜 ELF/PE가 맞는지, 32비트인지 64비트인지, 어떤 아키텍처인지, 패킹돼 있는지를 1초 만에 알 수 있다. 이 정보를 모르고 IDA부터 열면 잘못된 아키텍처 모드로 분석하게 되는 실수가 흔하다.

## 단계별 절차

**1) 가장 단순한 C 프로그램을 컴파일한다**

```c
// hello.c
#include <stdio.h>
int main(void) {
    printf("hello\n");
    return 0;
}
```

```bash
gcc hello.c -o hello
```

이 한 줄로 `hello.c` → `hello.o`(중간 산출물, 화면에 안 보이지만 내부적으로 생성됨) → 링크를 거쳐 최종 실행 파일 `hello`가 만들어진다.

**2) `file`로 포맷을 확인한다**

```bash
$ file hello
hello: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV),
dynamically linked, interpreter /lib64/ld-linux-x86-64.so.2, ...
```

- `ELF 64-bit`: ELF 포맷, 64비트(Class = ELF64)
- `LSB`: Least Significant Byte first, 즉 리틀 엔디안([REV-0023](./rev-0023-endianness.md) 참고)
- `pie executable`: 위치 독립 실행 파일(Position-Independent Executable). 매번 다른 베이스 주소에 로드될 수 있는 최신 기본 컴파일 옵션이다.
- `x86-64`: 아키텍처([REV-0021](./rev-0021-x86-vs-x64.md) 참고)
- `dynamically linked`: `printf` 같은 함수가 파일 안에 직접 들어있지 않고, 실행 시점에 `libc.so`에서 불러온다는 뜻

**3) `readelf -h`로 헤더를 자세히 본다**

```bash
$ readelf -h hello
ELF Header:
  Magic:   7f 45 4c 46 02 01 01 00 00 00 00 00 00 00 00 00
  Class:                             ELF64
  Data:                              2's complement, little endian
  Version:                           1 (current)
  OS/ABI:                            UNIX - System V
  ABI Version:                       0
  Type:                              DYN (Position-Independent Executable file)
  Machine:                           Advanced Micro Devices X86-64
  Version:                           0x1
  Entry point address:               0x1040
  Start of program headers:          64 (bytes into file)
  Start of section headers:          14136 (bytes into file)
  Flags:                             0x0
  Size of this header:               64 (bytes)
  Size of program headers:           56 (bytes)
  Number of program headers:         13
  Size of section headers:           64 (bytes)
  Number of section headers:         30
  Section header string table index: 29
```

각 필드는 아래 "출력 해석"에서 하나씩 설명한다.

**4) (Windows 환경이라면) 개념적으로 `dumpbin /headers hello.exe`**

Windows에서는 Visual Studio 개발자 명령 프롬프트에서 `dumpbin /headers hello.exe`를 치면 PE 버전의 동일한 정보(Machine, `AddressOfEntryPoint`, `ImageBase`, 섹션 테이블 등)를 볼 수 있다. PE 헤더의 세부 필드는 [REV-0028](./rev-0028-va-rva-offset.md)(VA/RVA/File Offset)과 [REV-0029](./rev-0029-section-vs-segment.md)(Section vs Segment)에서 더 깊이 다룬다.

**5) OS가 이 파일을 어떻게 "실행"으로 바꾸는지 이해한다**

`./hello`를 치는 순간 OS(로더, loader)는 대략 다음 순서로 동작한다.

1. 파일을 열고 앞부분(헤더)을 읽어 매직 바이트로 ELF/PE인지 확인한다.
2. 헤더의 `Class`(32/64비트)와 `Machine`(아키텍처)이 현재 CPU와 맞는지 확인한다.
3. 프로그램 헤더 테이블(ELF) 또는 섹션 테이블(PE)을 순회하며, `PT_LOAD` 타입으로 표시된 세그먼트마다 파일의 해당 바이트 범위를 **가상 메모리에 매핑**한다. 이때 세그먼트마다 읽기(R)/쓰기(W)/실행(X) 권한이 다르게 설정된다 — 예를 들어 코드가 들어있는 `.text`는 보통 R+X(읽기+실행, 쓰기 금지)로, 전역 변수가 들어있는 `.data`는 R+W(읽기+쓰기, 실행 금지)로 매핑된다. 이 권한 분리 덕분에 코드 영역에 쓰기를 시도하는 공격(셸코드 주입 등)을 하드웨어(NX/DEP) 수준에서 막을 수 있다.
4. 동적 링킹이 필요하면(위 예시의 `dynamically linked`) 헤더에 적힌 인터프리터(`/lib64/ld-linux-x86-64.so.2`)를 먼저 실행해서 필요한 `.so`/`.dll`들을 메모리에 올리고 심볼 주소를 연결한다.
5. CPU의 명령어 포인터 레지스터(32비트는 `EIP`, 64비트는 `RIP`)를 헤더에 적힌 **entry point 주소**로 설정한다.
6. CPU가 그 주소부터 명령어를 하나씩 가져와(fetch) 실행하기 시작한다 — 이것이 곧 `_start`(또는 `mainCRTStartup`) 코드의 실행이며, 여기서부터 CRT 초기화 → `main()` 호출로 이어진다.

## 명령어/단축키

```bash
# Linux
file hello                 # 파일 종류, 비트수, 아키텍처, 정적/동적 링크 여부 요약
readelf -h hello            # ELF 헤더 전체 필드 출력
readelf -l hello            # 프로그램 헤더(세그먼트) 목록, 로더가 매핑하는 단위
readelf -S hello            # 섹션 헤더 목록, 링커/디버거가 쓰는 단위
objdump -f hello             # 파일 포맷 요약(간략판 readelf -h)
objdump -d hello             # 디스어셈블
```

```text
# Windows (Developer Command Prompt)
dumpbin /headers hello.exe   # PE 헤더 + 섹션 테이블 전체 출력
```

IDA/Ghidra: 진입점으로 바로 이동하는 단축키/메뉴는 대개 "Jump to entry point" 항목이나 함수 목록에서 `entry`로 검색하면 찾을 수 있다. IDA의 Exports 창(`Ctrl+E` 또는 Imports/Exports 서브뷰)에서 `start`/`entry` 항목을 더블클릭해도 된다.

## 출력 해석
위 `readelf -h` 예시 출력을 필드별로 해석하면 다음과 같다.

- **Magic**: `7f 45 4c 46 ...` — 앞 4바이트 `7F 45 4C 46`이 ELF 매직 바이트(`\x7fELF`)다. 이 값이 다르면 애초에 ELF가 아니다([REV-0020](./rev-0020-magic-bytes.md) 참고).
- **Class**: `ELF64` — 32비트면 `ELF32`로 표시된다. 이 값 하나로 레지스터 폭(EAX vs RAX), 포인터 크기(4바이트 vs 8바이트)가 결정된다([REV-0022](./rev-0022-register-widths.md) 참고).
- **Data**: `2's complement, little endian` — 멀티바이트 숫자를 메모리에 저장할 때 하위 바이트를 먼저 쓴다는 뜻. x86/x64는 항상 리틀 엔디안이다([REV-0023](./rev-0023-endianness.md) 참고).
- **Type**: `DYN (Position-Independent Executable file)` — 요즘 배포판의 기본값. 예전 방식인 `EXEC`(고정 주소 실행 파일)와 달리, 로드될 때마다 커널이 임의의 베이스 주소를 골라 거기에 얹는다(ASLR과 함께 동작). 공유 라이브러리(`.so`)도 `DYN`으로 표시된다.
- **Machine**: `Advanced Micro Devices X86-64` — CPU 아키텍처. 32비트 x86이면 `Intel 80386` 등으로 표시된다([REV-0021](./rev-0021-x86-vs-x64.md) 참고).
- **Entry point address**: `0x1040` — 실행이 시작되는 주소. PIE 실행 파일이므로 이 값은 **가상 주소(VA)**이지만 파일 안의 절대 위치가 아니라 "베이스 주소 기준 상대 위치"로 봐야 한다. 실제 실행 시에는 커널이 정한 베이스 주소 + `0x1040`이 진짜 RIP 값이 된다([REV-0028](./rev-0028-va-rva-offset.md)의 VA/RVA/File Offset 참고).
- **Start of program headers**: `64 (bytes into file)` — 프로그램 헤더 테이블(세그먼트 정보)이 파일 시작에서 64바이트 지점부터 있다는 뜻. 로더가 이 테이블을 읽어 메모리 매핑을 수행한다.
- **Start of section headers**: `14136 (bytes into file)` — 섹션 헤더 테이블의 파일 오프셋. 주로 컴파일러/디버거/역어셈블러가 참고하며, 실행에는 필수가 아니다(스트립된 바이너리는 이 정보가 빈약할 수 있다).
- **Number of program headers / section headers**: 각각 13개, 30개 — 세그먼트와 섹션의 개수. 세그먼트(program header)는 로더 관점, 섹션(section header)은 링커/디버거 관점이라는 차이는 [REV-0029](./rev-0029-section-vs-segment.md)에서 자세히 다룬다.

## 흔한 실수
- **entry point를 `main()`이라고 착각하는 것** — 위에서 설명했듯 실제로는 `_start`/`mainCRTStartup` 같은 CRT 시작 스텁이다. `main`을 바로 보고 싶으면 함수 목록에서 이름으로 찾는 편이 빠르다.
- **`file`/`readelf -h`도 안 찍어보고 바로 IDA/Ghidra부터 여는 것** — 아키텍처, 비트수, 정적/동적 링크 여부를 먼저 알아야 분석 방향(디스어셈블 모드, 심볼 유무 기대치 등)을 제대로 잡을 수 있다.
- **섹션(section)과 세그먼트(segment)를 같은 것으로 생각하는 것** — 링커가 쓰는 세밀한 단위(섹션)와 로더가 실제로 메모리에 올리는 단위(세그먼트)는 목적이 다르다. 스트립된 바이너리는 섹션 헤더가 없어도 실행에는 지장이 없다([REV-0029](./rev-0029-section-vs-segment.md) 참고).
- **오브젝트 파일(`.o`/`.obj`)과 최종 실행 파일을 혼동하는 것** — 오브젝트 파일은 아직 링크되지 않아 심볼 주소가 미해결 상태이고, 단독으로 실행할 수 없다.
- **PIE 실행 파일의 Entry point 주소를 절대 메모리 주소로 착각하는 것** — `Type: DYN`인 파일의 주소들은 대부분 베이스 주소 기준 상대값이다. 실제 실행 중 주소를 보려면 디버거로 붙여서 확인해야 한다.

## 막혔을 때 다음 체크
- 파일이 ELF인지 PE인지, 애초에 실행 파일이 맞는지 헷갈리면 → [REV-0020](./rev-0020-magic-bytes.md)(Magic Byte와 파일 시그니처)으로 이동.
- `Machine` 필드나 레지스터 이름(`eax`/`rax`)이 헷갈리면 → [REV-0021](./rev-0021-x86-vs-x64.md)(x86와 x64를 구분하는 법), [REV-0022](./rev-0022-register-widths.md)(32비트와 64비트 레지스터 차이)로 이동.
- `Data: little endian` 표시가 실제로 메모리 덤프에서 어떻게 보이는지 궁금하면 → [REV-0023](./rev-0023-endianness.md)(Little Endian과 Big Endian)으로 이동.
- 디컴파일 결과에 이상한 음수나 마스크 연산이 나와서 헷갈리면 → [REV-0024](./rev-0024-twos-complement.md)(2의 보수), [REV-0025](./rev-0025-signed-unsigned.md)(Signed와 Unsigned 해석), [REV-0026](./rev-0026-bit-masks.md)(비트 마스크)로 이동.
- 반복문에서 값이 갑자기 작아지거나 튀는 현상을 만나면 → [REV-0027](./rev-0027-integer-overflow.md)(정수 Overflow와 Wraparound)로 이동.
- `Entry point address`가 파일에서 본 값과 디버거에서 본 값이 달라서 당황하면 → [REV-0028](./rev-0028-va-rva-offset.md)(VA, RVA, File Offset 차이)로 이동.
- 섹션 개수와 세그먼트 개수가 다른 이유, 또는 스트립된 바이너리에 섹션 헤더가 없는 이유가 궁금하면 → [REV-0029](./rev-0029-section-vs-segment.md)(메모리 Section과 Segment 차이)로 이동.

## 미니 예제
`hello.c`를 두 단계로 나눠서 링크 전/후 차이를 직접 확인해보면 "컴파일 vs 링크"가 명확해진다.

```bash
$ gcc -c hello.c -o hello.o     # 컴파일만: 아직 오브젝트 파일
$ file hello.o
hello.o: ELF 64-bit LSB relocatable, x86-64, version 1 (SYSV), not stripped

$ gcc hello.o -o hello           # 링크: 최종 실행 파일
$ file hello
hello: ELF 64-bit LSB pie executable, x86-64, version 1 (SYSV), dynamically linked, ...
```

`hello.o`는 `file` 결과에 **`relocatable`**이라고 표시된다 — "아직 최종 주소가 정해지지 않았고, 링커가 재배치(relocation)해야 한다"는 뜻이다. 반면 `hello`는 **`pie executable`**로, 즉시 로더가 로드해서 실행할 수 있는 완성된 형태다. `readelf -h hello.o`를 찍어보면 `Type: REL (Relocatable file)`로 나오는데, 앞서 본 `hello`의 `Type: DYN`과 대비된다 — 이 `Type` 필드 하나만으로도 "이 파일이 아직 오브젝트 단계인지, 실행 가능한 최종 산출물인지"를 즉시 구분할 수 있다.

## 관련 글
- [REV-0020](./rev-0020-magic-bytes.md) — Magic Byte와 파일 시그니처
- [REV-0021](./rev-0021-x86-vs-x64.md) — x86와 x64를 구분하는 법
- [REV-0022](./rev-0022-register-widths.md) — 32비트와 64비트 레지스터 차이
- [REV-0023](./rev-0023-endianness.md) — Little Endian과 Big Endian
- [REV-0024](./rev-0024-twos-complement.md) — 2의 보수와 음수 표현
- [REV-0025](./rev-0025-signed-unsigned.md) — Signed와 Unsigned 해석
- [REV-0026](./rev-0026-bit-masks.md) — 8비트 16비트 24비트 32비트 64비트 마스크
- [REV-0027](./rev-0027-integer-overflow.md) — 정수 Overflow와 Wraparound
- [REV-0028](./rev-0028-va-rva-offset.md) — 주소 VA, RVA, File Offset 차이
- [REV-0029](./rev-0029-section-vs-segment.md) — 메모리 Section과 Segment 차이

## 출처/검증
- ELF 포맷 구조(헤더/프로그램 헤더/섹션 헤더) 및 필드 정의: 리눅스 `man 5 elf`, System V Application Binary Interface 표준 문서 기준 개념 설명 (2026-09-08 검증, `readelf -h`/`file` 실제 출력으로 교차 확인).
- PE 포맷 구조 개념: Microsoft "PE Format" 공식 문서(learn.microsoft.com, Windows 개발자 문서) 기준 개념 설명.
- CRT 시작 루틴(`_start`, `__libc_start_main`, `mainCRTStartup`)의 역할: glibc 및 Microsoft CRT 소스/문서에 기술된 일반적 동작 기준.
