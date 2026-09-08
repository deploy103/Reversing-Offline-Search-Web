---
id: REV-0090
title: "ELF Program Header와 Section Header 차이"
slug: "rev-0090-program-vs-section-header"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, "readelf", "objdump", "binutils"]
keywords: ["Program Header", "Section Header", "PT_LOAD", "세그먼트", "섹션", "readelf -l", "readelf -S"]
aliases: ["program header란", "section header란", "elf 세그먼트 섹션 차이", "phdr shdr 차이"]
symptom_keywords: ["program header와 section header 차이를 모름", "세그먼트와 섹션 헷갈림", "strip해도 실행이 되는 이유"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
**Program Header(세그먼트 테이블)**는 커널/로더가 프로세스를 실제로 메모리에 올릴 때 사용하는 "실행용 지도"이고, **Section Header(섹션 테이블)**는 링커와 분석 도구(readelf, objdump, IDA)가 코드를 의미 단위로 나눠 보기 위한 "분석용 지도"다 — 실행에는 Program Header만 있으면 되고, `strip`으로 Section Header를 지워도 프로그램은 여전히 정상 실행된다.

## 언제 검색해야 하나
- `readelf -l`(Program Header)과 `readelf -S`(Section Header) 결과가 왜 이렇게 다르게 생겼는지 헷갈릴 때
- strip된 바이너리인데도 실행은 잘 되는 이유가 궁금할 때
- `.text`, `.data` 같은 섹션이 `LOAD` 세그먼트와 무슨 관계인지 알고 싶을 때
- IDA/Ghidra가 섹션 이름을 못 찾는(strip된) 바이너리에서도 코드/데이터 영역을 구분하는 원리가 궁금할 때

## 핵심 개념

### 두 개의 서로 다른 "보는 방식"
ELF 파일 하나의 코드와 데이터를 **두 가지 방식으로 동시에 설명**한다.

1. **Program Header Table (세그먼트, Segment)** — "실행 관점". 커널이 `execve()`로 이 파일을 프로세스로 만들 때, 파일의 어느 부분을 메모리의 어느 주소에 어떤 권한(R/W/X)으로 매핑할지 알려준다. 커널은 섹션 이름 같은 건 전혀 신경 쓰지 않는다. 오직 Program Header만 보고 `mmap`을 몇 번 호출하듯이 파일을 메모리에 얹는다.
2. **Section Header Table (섹션, Section)** — "링킹/분석 관점". 컴파일러와 링커가 코드(`.text`), 초기화된 전역 변수(`.data`), 초기화 안 된 전역 변수(`.bss`), 문자열(`.rodata`), 심볼 테이블(`.symtab`), 재배치 정보(`.rela.*`) 등을 의미 단위로 나눠 이름표를 붙인 것이다. 이건 링커가 여러 `.o` 파일을 하나로 합칠 때와, 사람이(또는 readelf/IDA가) 바이너리를 분석할 때 필요한 정보이지, **커널이 프로세스를 실행하는 데는 전혀 필요 없다.**

### 왜 이 둘이 필요한가: 실행 파일과 오브젝트 파일의 목적 차이
- `.o`(오브젝트 파일, `ET_REL`)는 아직 실행되지 않고 다른 파일과 **링크**되어야 하므로 Section Header가 필수다. 이 단계에서는 Program Header가 아예 없다(아직 메모리에 어떻게 올릴지 결정할 필요가 없다).
- 최종 실행 파일(`ET_EXEC`/`ET_DYN`)은 Program Header가 필수다. 커널이 이걸 보고 로드한다. Section Header는 **있으면 분석에 편하지만 없어도 실행에는 지장이 없다.** `strip` 명령이 지우는 것이 바로 이 Section Header 관련 정보(주로 `.symtab`, `.strtab` 섹션과 섹션 헤더 테이블 자체)다.

### PT_LOAD: 가장 중요한 세그먼트 타입
Program Header 엔트리(`Elf64_Phdr`)에는 `p_type`, `p_offset`(파일 오프셋), `p_vaddr`(로드될 가상 주소), `p_filesz`, `p_memsz`, `p_flags`(R/W/X)가 들어있다. 여러 타입 중 실전에서 가장 중요한 것들:
- **PT_LOAD**: "이 부분을 이 주소에 이 권한으로 메모리에 매핑해라." 보통 실행 파일 하나에 PT_LOAD가 2~4개 있다 — 예: 코드용(R+X), 읽기전용 데이터용(R), 쓰기 가능 데이터용(R+W). 각 PT_LOAD는 여러 섹션(`.text`, `.rodata`, `.data`, `.bss` 등)을 한꺼번에 포함한다.
- **PT_INTERP**: 동적 링커(인터프리터) 경로, 보통 `/lib64/ld-linux-x86-64.so.2`. 이 세그먼트가 있으면 동적 링킹된 실행 파일이라는 뜻.
- **PT_DYNAMIC**: 동적 링킹에 필요한 정보(필요한 라이브러리 목록, 심볼 테이블 위치 등)가 담긴 `.dynamic` 섹션을 가리킴.
- **PT_GNU_STACK**: 스택이 실행 가능(NX 여부)한지 나타냄. 리버싱에서 스택 실행 가능 여부(`checksec`의 `NX` 항목)와 직결된다(REV-0096 참고).
- **PT_GNU_RELRO**: RELRO 보호 관련 세그먼트(REV-0100 GOT 설명과 연결).
- **PT_NOTE**: 빌드 ID 등 부가 메타데이터.

### Section의 대표 이름들
- `.text` — 실행 코드
- `.rodata` — 읽기 전용 데이터(문자열 리터럴 등)
- `.data` — 초기화된 전역/정적 변수
- `.bss` — 초기화되지 않은(0으로 시작하는) 전역/정적 변수. **파일 크기에는 공간을 차지하지 않는다**(`p_filesz` < `p_memsz`인 이유가 여기 있다) — 파일에는 존재하지 않고 로드 시 커널이 0으로 채운 메모리만 할당한다.
- `.symtab`/`.strtab` — 심볼 테이블과 이름 문자열(strip 시 제거됨)
- `.dynsym`/`.dynstr` — 동적 심볼 테이블(동적 링킹에 필요하므로 strip해도 보통 남음)
- `.plt`/`.got`/`.got.plt` — REV-0100 참고
- `.rela.dyn`/`.rela.plt` — 재배치(relocation) 정보

## 화면/코드에서 보이는 징후
- `readelf -S`는 결과가 나오는데 `readelf -l`은 나오는 게 이상하게 적거나(비정상 파일), 반대로 `readelf -S`에서 `.symtab`이 안 보이면 strip된 파일
- IDA/Ghidra가 로드 시 "세그먼트 정보 없음"류 경고 없이도 잘 열리는 이유는 Program Header만으로 로드가 가능하기 때문
- strip된 바이너리에서도 `readelf -l`은 정상 출력되지만 `readelf -S`는 섹션 이름 없이 나오거나 목록이 짧아짐

## 가장 먼저 할 것
헷갈리면 이 한 문장만 기억한다: **"세그먼트(Program Header)는 실행을 위한 것, 섹션(Section Header)은 분석을 위한 것."** 실행이 어떻게 되는지 궁금하면 `readelf -l`, 코드/데이터 구조를 세밀하게 보고 싶으면 `readelf -S`를 쓴다.

## 단계별 절차

**1) Program Header 확인**
```bash
readelf -l ./chall
```
출력 예(일부):
```
Program Headers:
  Type           Offset             VirtAddr           PhysAddr
                 FileSiz            MemSiz              Flags  Align
  PHDR           0x0000000000000040 0x0000000000000040 0x0000000000000040
                 0x00000000000002d8 0x00000000000002d8  R      0x8
  INTERP         0x0000000000000318 0x0000000000000318 0x0000000000000318
                 0x000000000000001c 0x000000000000001c  R      0x1
      [Requesting program interpreter: /lib64/ld-linux-x86-64.so.2]
  LOAD           0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x0000000000000640 0x0000000000000640  R      0x1000
  LOAD           0x0000000000001000 0x0000000000001000 0x0000000000001000
                 0x0000000000000195 0x0000000000000195  R E    0x1000
  LOAD           0x0000000000002000 0x0000000000002000 0x0000000000002000
                 0x00000000000001a8 0x00000000000001a8  R      0x1000
  LOAD           0x0000000000002e10 0x0000000000003e10 0x0000000000003e10
                 0x0000000000000228 0x0000000000000230  RW     0x1000
  DYNAMIC        0x0000000000002e20 0x0000000000003e20 0x0000000000003e20
                 0x00000000000001d0 0x00000000000001d0  RW     0x8

 Section to Segment mapping:
  Segment Sections...
   00
   01     .interp
   02     .interp .note.gnu.build-id .note.ABI-tag .gnu.hash .dynsym .dynstr .gnu.version ...
   03     .init .plt .plt.sec .text .fini
   04     .rodata .eh_frame_hdr .eh_frame
   05     .init_array .fini_array .dynamic .got .data .bss
```
마지막 "Section to Segment mapping"이 핵심이다 — 각 LOAD 세그먼트 안에 어떤 섹션들이 포함되는지 보여준다. 실행 코드가 들어있는 `.text`가 `R E`(읽기+실행) 세그먼트 안에, 쓰기 가능한 `.data`/`.bss`가 `RW` 세그먼트 안에 있는 걸 확인할 수 있다.

**2) Section Header 확인**
```bash
readelf -S ./chall
```
출력 예(일부):
```
Section Headers:
  [Nr] Name              Type             Address           Offset
       Size              EntSize          Flags  Link  Info  Align
  [ 0]                   NULL             0000000000000000  00000000
  [13] .text             PROGBITS         0000000000001060  00001060
       00000000000001a5  0000000000000000  AX       0     0     16
  [17] .rodata           PROGBITS         0000000000002000  00002000
       0000000000000010  0000000000000000   A       0     0     4
  [24] .data             PROGBITS         0000000000003e10  00002e10
       0000000000000010  0000000000000000  WA       0     0     8
  [25] .bss              NOBITS           0000000000003e20  00002e20
       0000000000000008  0000000000000000  WA       0     0     1
  [26] .symtab           SYMTAB           0000000000000000  00003000
       0000000000000318  0000000000000018          27    12     8
```
`.bss`의 `Type`이 `NOBITS`인 점에 주목한다 — 파일 안에 실제 데이터가 없다는 뜻이다(파일 오프셋은 있지만 그 자리에서 바로 다음 섹션이 이어진다).

**3) strip 전/후 비교로 차이를 직접 확인**
```bash
cp chall chall_stripped
strip chall_stripped
readelf -S chall_stripped | grep -c .    # 섹션 개수가 크게 줄어듦
readelf -l chall_stripped | grep -c .    # Program Header는 거의 그대로
./chall_stripped                          # 여전히 정상 실행됨
```

## 명령어/단축키
```bash
readelf -l ./chall      # Program Header (segments)
readelf -S ./chall      # Section Header (sections)
readelf -e ./chall      # ELF 헤더 + 둘 다 한번에
objdump -p ./chall      # Program Header 요약 (objdump 관점)
```

## 출력 해석
- `readelf -l`에서 `LOAD` 줄이 여러 개인 것은 정상이다 — 보통 코드(R E), 읽기전용 데이터(R), 쓰기가능 데이터(RW)가 각각 별도 세그먼트로 분리되어(권한 최소화 원칙, W^X) 나타난다.
- `FileSiz`와 `MemSiz`가 다른 LOAD 세그먼트(마지막 RW 세그먼트에서 흔함)는 `.bss`처럼 파일에는 없고 메모리에서만 존재하는 영역을 포함한다는 뜻.
- `readelf -S`에서 `Flags` 열의 `A`=Alloc(메모리에 로드됨), `W`=Write, `X`=Execute. `AX`면 실행 가능한 코드 섹션(`.text`, `.plt` 등).

## 흔한 실수
- Program Header와 Section Header를 완전히 같은 정보의 다른 표현이라고 생각하는 것 — 목적 자체가 다르다. 세그먼트는 여러 섹션을 포함할 수 있고, 개수도 이름도 서로 다르다.
- strip하면 프로그램이 실행 안 될 거라 생각하는 것 — Section Header(및 `.symtab`)는 실행에 불필요하므로 strip 후에도 정상 동작한다.
- `.bss` 섹션의 크기만큼 파일 크기가 커질 거라 착각하는 것 — `.bss`는 `NOBITS`라 파일에 실제 바이트를 차지하지 않는다.
- Section Header가 아예 없는(섹션 헤더 테이블 자체가 지워진) 극단적으로 strip된 바이너리를 IDA가 못 열 거라 생각하는 것 — IDA는 Program Header만으로도 세그먼트를 재구성해서 로드할 수 있다.

## 막혔을 때 다음 체크
- ELF 헤더 자체의 필드가 궁금하면 → [REV-0089 ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- `readelf`의 다른 옵션들을 체계적으로 알고 싶으면 → [REV-0091 readelf 기본 사용법](./rev-0091-readelf-basics.md)
- 함수 이름이 다 사라진 stripped 바이너리에서 시작점을 어떻게 잡는지 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- PLT/GOT가 어느 세그먼트/섹션에 있는지 궁금하면 → [REV-0100 PLT와 GOT 기초](./rev-0100-plt-got.md)

## 미니 예제
```bash
$ readelf -l chall | grep -A1 LOAD
  LOAD           0x0000000000000000 0x0000000000000000 0x0000000000000000
                 0x0000000000000640 0x0000000000000640  R      0x1000
  LOAD           0x0000000000001000 0x0000000000001000 0x0000000000001000
                 0x0000000000000195 0x0000000000000195  R E    0x1000

$ readelf -S chall | grep -E '\.text|\.bss'
  [13] .text             PROGBITS         0000000000001060  00001060
  [25] .bss              NOBITS           0000000000003e20  00002e20
```
`.text`의 주소(`0x1060`)가 두 번째 `LOAD`(오프셋 `0x1000`, `R E`) 세그먼트 범위 안에 들어간다는 걸 두 출력을 대조해서 확인할 수 있다.

## 관련 글
- [REV-0089 — ELF 헤더 읽는 법](./rev-0089-elf-header.md)
- [REV-0091 — readelf 기본 사용법](./rev-0091-readelf-basics.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- [REV-0100 — PLT와 GOT 기초](./rev-0100-plt-got.md)
- [REV-0096 — checksec 결과 읽는 법](./rev-0096-checksec.md)

## 출처/검증
- Program Header / Section Header 구조체 정의: System V ABI, "Program Header", "Section Header" 챕터 기준 (2026-09-08 검증).
- `PT_GNU_STACK`, `PT_GNU_RELRO`: LSB(Linux Standard Base) 및 GNU 확장 문서 기준.
- `readelf` 출력 형식: GNU binutils `readelf(1)` 실측 기준.
