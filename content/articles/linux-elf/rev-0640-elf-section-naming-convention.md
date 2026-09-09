---
id: REV-0640
title: "ELF Section 이름 관례 사전(.text .rodata .bss 등)"
slug: "rev-0640-elf-section-naming-convention"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, objdump]
keywords: [".text", ".rodata", ".data", ".bss", ".plt", ".got", ".dynamic", "ELF section", "섹션 이름"]
aliases: ["ELF 섹션 이름", "text rodata data bss 차이", "섹션 헤더 이름 사전", "readelf -S 해석"]
symptom_keywords: [".bss 섹션이 파일 크기를 안 차지함", "섹션 이름이 낯섬", "readelf -S 출력 해석", "섹션과 세그먼트 차이"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
ELF의 섹션 이름(`.text`, `.rodata`, `.data`, `.bss` 등)은 표준이 강제하는 것이 아니라 **컴파일러/링커가 따르는 관례**지만, 어느 도구로 어떤 바이너리를 열어도 거의 항상 같은 이름 규칙을 쓰기 때문에 이름만 보고도 그 섹션에 무엇이 들었을지 바로 짐작할 수 있다.

## 언제 검색해야 하나
- `readelf -S`나 IDA의 섹션 목록에 나온 이름(`.init_array`, `.got.plt`, `.eh_frame` 등)이 뭔지 몰라서 찾아볼 때
- 어떤 데이터가 어느 섹션에 있는지 보고 "이게 상수인지, 변수인지, 초기화됐는지"를 빠르게 판단하고 싶을 때
- `.bss` 섹션 크기는 큰데 파일 크기에는 반영이 안 되는 이유가 궁금할 때

## 핵심 개념

### 섹션과 세그먼트는 다른 개념
섹션 헤더(`Elf64_Shdr`, REV-0090 참고)는 **링커/디버거용** 정보이고, 프로그램 헤더(세그먼트)는 **로더가 실제로 메모리에 매핑할 때** 쓰는 정보다. 여러 섹션이 하나의 세그먼트(예: `LOAD`)로 묶여 매핑된다. 이 글은 섹션 이름에 집중한다.

### 코드/읽기 전용 데이터
| 이름 | 내용 | 권한 |
|---|---|---|
| `.text` | 실제 실행 코드(명령어) | R-X |
| `.init` | 프로그램 시작 시 실행되는 초기화 코드(레거시, `_init`) | R-X |
| `.fini` | 종료 시 실행되는 정리 코드(레거시, `_fini`) | R-X |
| `.plt` / `.plt.sec` | PLT 스텁 코드. `.plt.sec`는 CET(Intel Control-flow Enforcement) 지원 최신 glibc/바이너리에서 추가되는 IBT용 별도 PLT(REV-0100 참고) | R-X |
| `.rodata` | 문자열 리터럴, `const` 전역 변수 등 읽기 전용 데이터 | R-- |
| `.init_array` / `.fini_array` | 생성자/소멸자 함수 포인터 배열(`__attribute__((constructor))`, C++ 전역 객체 생성자 등). `_start` → `__libc_start_main`이 `.init_array`를 순회 호출 | R-- |
| `.eh_frame` / `.eh_frame_hdr` | 예외 처리/스택 언와인딩용 메타데이터(C++ 예외, 백트레이스 계산에 사용) | R-- |
| `.interp` | 동적 링커(ELF Interpreter) 경로 문자열, 예: `/lib64/ld-linux-x86-64.so.2` | R-- |
| `.note.*` | ABI 태그, 빌드 ID 등 메타데이터 노트 | R-- |
| `.comment` | 컴파일러 버전 문자열 등 | 없음(비적재) |

### 쓰기 가능한 데이터
| 이름 | 내용 | 권한 |
|---|---|---|
| `.data` | 0이 아닌 값으로 초기화된 전역/정적 변수 | RW- |
| `.bss` | 0으로 초기화되거나 초기화되지 않은 전역/정적 변수. **`SHT_NOBITS` 타입이라 파일 안에 실제 바이트를 갖지 않고 크기 정보만 있음** — 로더가 이 섹션 크기만큼 0으로 채운 메모리를 할당한다. 그래서 `.bss`가 아무리 커도 파일 크기는 늘지 않는다 | RW- |
| `.tdata` / `.tbss` | 스레드 로컬 저장소(`__thread` 변수)의 초기화됨/안됨 버전 | RW- |

### 링킹/심볼 관련
| 이름 | 내용 |
|---|---|
| `.dynamic` | 동적 링커용 태그 배열(`DT_NEEDED`, `DT_SYMTAB` 등, REV-0641 참고) |
| `.dynsym` / `.dynstr` | 동적 심볼 테이블 / 그 이름 문자열 테이블 — **스트립해도 보통 남아있음**(런타임 심볼 해석에 필수) |
| `.symtab` / `.strtab` | 전체 심볼 테이블 / 문자열 테이블 — 디버깅/링크용, `strip` 명령으로 가장 먼저 제거되는 대상 |
| `.got` / `.got.plt` | 전역 오프셋 테이블(REV-0100 참고) |
| `.rela.dyn` / `.rela.plt` | 재배치 엔트리(`Elf64_Rela` 구조체 배열). `.rela.plt`는 PLT/GOT 관련 지연 바인딩용, `.rela.dyn`은 그 외 전역 변수/포인터용 |
| `.hash` / `.gnu.hash` | 심볼 이름을 빠르게 찾기 위한 해시 테이블(SysV 방식 / GNU 확장 방식) |
| `.shstrtab` | 섹션 이름 문자열 테이블 자체(섹션 헤더의 `sh_name`이 여기를 가리킴) |

## 화면/코드에서 보이는 징후
- `readelf -S ./chall`을 실행하면 `[Nr] Name Type Address Offset Size ... Flg` 형식으로 모든 섹션이 나열됨
- IDA/Ghidra의 Segments 뷰에 위 이름들이 그대로 표시됨
- `.bss`의 `Type`이 `NOBITS`로 표시되고, `Size`는 크지만 파일 오프셋(`Offset`) 이후 실제로 그만큼의 바이트가 파일에 없음

## 가장 먼저 할 것
`readelf -S ./chall`로 전체 섹션 목록과 `Flg`(권한: `W`=쓰기, `A`=alloc, `X`=실행)를 한 번 훑어서 코드/상수/변수 영역이 각각 어디인지 감을 잡는다.

## 단계별 절차

**1) 전체 섹션 목록**
```bash
readelf -S ./chall
```

**2) 특정 섹션 헥사 덤프**
```bash
readelf -x .rodata ./chall
objdump -s -j .data ./chall
```

**3) 섹션별 디스어셈블**
```bash
objdump -d -j .text ./chall
```

**4) .bss가 실제 파일 크기에 안 잡히는지 확인**
```bash
readelf -S ./chall | grep -A1 '\.bss'
ls -l ./chall
```
`.bss` 줄의 `Off`(파일 오프셋)와 다음 섹션의 `Off`를 비교하면 `.bss`만큼의 구간이 파일에서는 "차지하지 않는다"는 것을 알 수 있다(Type이 `NOBITS`이기 때문).

## 명령어/단축키
```bash
readelf -S ./chall
readelf -x <섹션이름> ./chall
objdump -h ./chall     # 섹션 요약(readelf -S와 유사)
objdump -d -j .text ./chall
```

## 출력 해석
- `Flg` 열의 `WA`는 Write+Alloc(런타임에 메모리 적재되고 쓰기 가능, `.data`/`.bss`), `AX`는 Alloc+Execute(`.text`), `A`만 있으면 읽기 전용 적재(`.rodata`).
- `Type`이 `PROGBITS`면 파일에 실제 데이터가 있는 섹션, `NOBITS`면 `.bss`처럼 크기만 있고 파일에 바이트가 없는 섹션, `DYNAMIC`이면 `.dynamic`, `SYMTAB`/`DYNSYM`이면 각각 심볼 테이블.

## 흔한 실수
- `.data`와 `.bss`를 혼동하는 것 — `.data`는 0이 아닌 초기값이 있어 **파일에 실제로 그 값이 저장**되지만, `.bss`는 0으로 초기화될 뿐이라 파일에 데이터를 저장할 필요가 없다.
- `.rodata`에 있는 문자열을 함수라고 착각하는 것 — `.rodata`는 실행 권한(`X`)이 없으므로 여기 있는 바이트를 코드로 실행하려 하면 세그멘테이션 폴트가 난다(단, 일부 보호 기법 미적용 구세대 바이너리는 예외적으로 실행 가능한 경우도 있음 — NX 비트 확인 필요).
- 섹션 이름이 없어도(스트립된 바이너리) 프로그램이 실행 안 되는 것으로 착각하는 것 — 섹션 헤더는 로더가 실행에 필수로 요구하지 않는다. 실행에 필수인 것은 프로그램 헤더(세그먼트)다.

## 막혔을 때 다음 체크
- 섹션과 세그먼트(프로그램 헤더) 차이를 더 명확히 하고 싶으면 → REV-0090 Program vs Section Header.
- `.plt`/`.got` 계열이 헷갈리면 → REV-0100 PLT와 GOT 기초.
- `.dynamic` 안의 각 태그(`DT_*`) 의미가 궁금하면 → REV-0641 ELF Dynamic Section 태그(DT_*) 빠른 참조.

## 미니 예제
```bash
$ readelf -S ./chall | grep -E '\.text|\.rodata|\.data|\.bss'
  [14] .text             PROGBITS  ... AX
  [16] .rodata           PROGBITS  ... A
  [24] .data             PROGBITS  ... WA
  [25] .bss              NOBITS    ... WA
```
`.text`는 실행 가능(`AX`), `.rodata`는 읽기 전용(`A`만), `.data`/`.bss`는 쓰기 가능(`WA`)이며 그중 `.bss`만 `NOBITS` 타입임을 한 줄로 확인할 수 있다.

## 관련 글
- REV-0090 — ELF Program Header와 Section Header 차이
- REV-0089 — ELF 헤더 읽는 법
- REV-0100 — PLT와 GOT 기초
- REV-0641 — ELF Dynamic Section 태그(DT_*) 빠른 참조

## 출처/검증
- 섹션 이름 및 역할(`.text`, `.rodata`, `.data`, `.bss`, `.init_array`, `.eh_frame` 등): System V ABI generic ABI "Special Sections" 표 및 GNU Binutils(`ld`, `readelf`) 표준 링커 스크립트 관례 기준.
- `SHT_NOBITS`/`SHT_PROGBITS` 타입 정의: System V ABI "Section Header" 챕터 기준 (2026-09-08 검증).
- `.plt.sec` 도입 배경(CET/IBT): glibc 및 GNU Binutils CET 지원 관련 릴리스 노트 기준.
