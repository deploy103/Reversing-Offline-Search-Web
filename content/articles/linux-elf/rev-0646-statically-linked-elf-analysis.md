---
id: REV-0646
title: "정적 링킹된(Statically Linked) ELF 분석 접근법"
slug: "rev-0646-statically-linked-elf-analysis"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, Ghidra, GDB, Pwndbg, readelf, objdump, nm]
keywords: ["정적 링킹", "static linking", "statically linked", "FLIRT", "Function ID", "libc 함수 식별", "정적 바이너리 분석"]
aliases: ["static binary 분석", "정적 바이너리란", "statically linked 분석법", "libc가 안에 다 있는 바이너리"]
symptom_keywords: ["ldd가 not a dynamic executable이라고 나옴", "import 목록이 거의 비어있음", "함수가 너무 많고 뭐가 main인지 모르겠음", "strip된 정적 바이너리에서 malloc을 못 찾겠음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
정적 링킹(static linking)된 ELF는 `libc` 코드 전체(또는 사용하는 부분)를 실행 파일 안에 통째로 복사해 넣기 때문에 import 목록이 거의 비어 있고 함수 수가 수천 개로 폭증하는데, 이때는 PLT/GOT를 볼 게 아니라 시그니처 매칭과 진입점 추적으로 `libc` 함수를 골라내는 전략이 필요하다.

## 언제 검색해야 하나
- `file ./chall` 결과에 `statically linked`가 나오고 `ldd ./chall`은 `not a dynamic executable`이라고 할 때
- IDA/Ghidra의 함수 목록(Functions window)에 이름 모를 함수가 수천 개 나열되어 어디서부터 봐야 할지 막막할 때
- Import 창이 텅 비어 있어서 REV-0101에서 배운 "import 목록으로 감 잡기" 전략을 쓸 수 없을 때
- CTF pwn 문제인데 `checksec` 결과에 `Dynamically linked: No`가 나와서 파일 크기가 유난히 크고(수백 KB~수 MB) 분석 방법이 다를 것 같을 때

## 핵심 개념

### 정적 링킹이 만드는 차이
동적 링킹 바이너리는 `printf`, `malloc` 같은 함수의 실제 코드를 갖고 있지 않고 런타임에 `ld.so`가 `libc.so.6`을 매핑해준다(REV-0101). 정적 링킹 바이너리는 컴파일 시점에 링커(`ld`)가 필요한 `libc` 오브젝트 코드를 `.a` 아카이브에서 뽑아 실행 파일 `.text`에 직접 박아 넣는다. 그 결과:

- `readelf -l ./chall`에 `INTERP` 세그먼트가 없다 — 커널이 로더를 거치지 않고 바로 실행한다.
- `readelf -d ./chall`은 `There is no dynamic section in this file`을 출력한다 — `.dynamic`, `.dynsym`, `.got.plt` 자체가 없다(PLT/GOT 개념 자체가 적용 안 됨).
- 파일 크기가 수백 KB에서 수 MB로 커진다. `printf` 하나를 호출해도 `vfprintf`, 포맷 파서, 로케일 코드까지 전부 딸려 들어오기 때문이다.
- strip되지 않았다면 `nm ./chall` 또는 IDA Functions 창에 `malloc`, `free`, `__vfprintf_internal` 같은 함수 이름 수천 개가 그대로 보인다. strip됐다면 이름이 전부 사라지고 `sub_401234` 같은 이름만 남는다.

### 왜 정적 바이너리를 CTF에서 만드는가
배포 편의성 때문이다. 특정 `libc` 버전이 시스템에 설치되어 있지 않아도 실행되므로, Alpine/musl 환경이나 배포판 버전 차이로 인한 "채점 서버에서만 안 돌아가는" 문제를 피할 수 있다. 또한 일부러 분석을 어렵게 만들려고 정적 링킹 + strip 조합을 쓰는 문제도 흔하다.

### 함수가 수천 개일 때의 전략 — 시그니처 매칭
strip되지 않았다면 `nm ./chall | grep ' T '`로 전역 함수 이름을 그대로 볼 수 있으니 어렵지 않다. 문제는 **strip된 정적 바이너리**다. 이 경우 IDA/Ghidra가 제공하는 시그니처 데이터베이스를 활용한다.

- **IDA FLIRT(Fast Library Identification and Recognition Technology)**: IDA는 알려진 컴파일러/라이브러리의 바이트 패턴을 담은 `.sig` 파일(예: `glibc_64_ubuntu.sig` 등 커뮤니티 제작 시그니처 포함)을 갖고 있다. 파일을 열면 자동 적용되기도 하고, 수동으로 File → Load file → FLIRT signature file로 적용할 수 있다. 매칭되면 `sub_401234` 같은 이름이 `malloc`, `_IO_printf` 등으로 자동 치환된다.
- **Ghidra Function ID**: Ghidra는 `.fidb`(Function ID Database) 파일로 같은 역할을 한다. Tools에서 Function ID 관련 옵션을 켜고, 알려진 라이브러리 FID 데이터베이스를 로드하면 분석 시 자동으로 매칭을 시도한다.
- **radare2/rizin zignatures**: `zg`로 시그니처를 생성하고 `z`, `zia`(zignature apply all) 명령으로 알려진 라이브러리 함수와 비교 매칭한다.

시그니처 매칭은 완벽하지 않다 — 컴파일러 버전, 최적화 옵션(`-O2` vs `-O0`), 정적 링크된 `libc` 버전이 시그니처 데이터베이스와 정확히 일치해야 잘 맞는다. 안 맞으면 일부만 매칭되거나 전혀 안 맞을 수 있다.

### 시그니처 없이 수동으로 찾는 법 — 문자열 배너
정적 링크된 `glibc`는 보통 버전 배너 문자열을 `.rodata`에 남긴다.

```bash
strings ./chall | grep -i "GNU C Library"
```

`GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.9) stable release version 2.31.` 같은 줄이 나오면 정확한 `libc` 버전을 알 수 있다. 이 버전 정보로 같은 버전의 `libc-2.31.so`를 로컬에 구해서(예: `libc-database` 프로젝트나 배포판 패키지) IDA/Ghidra에 별도로 로드하고, 함수별 바이트 시퀀스를 정적 바이너리와 눈으로 비교(BinDiff, 또는 단순 objdump 출력 diff)하는 것도 가능한 최후의 수단이다.

### 진입점 체인은 그대로 활용 가능
정적 바이너리도 `_start` → `__libc_start_main` → `main` 흐름(REV-0097, REV-0098, REV-0099)은 동일하게 존재한다. 다만 `__libc_start_main` 자체도 바이너리 안에 정적으로 포함되어 있으므로, `objdump -d ./chall`로 `_start`를 찾고 거기서 호출되는 함수를 하나씩 따라가면 결국 `main`에 도달한다. 이 방법은 시그니처 매칭이 실패해도 항상 통하는 수동 경로다.

## 화면/코드에서 보이는 징후
- `file ./chall` 출력에 `statically linked`
- `ldd ./chall` → `not a dynamic executable`
- `checksec --file=./chall` (pwntools) 출력에 `Dynamically linked: No` 또는 `Static:  Yes` 계열 표시
- IDA/Ghidra Functions 창에 수천 개 함수, strip 전이면 `malloc`, `free`, `vfprintf`, `__stack_chk_fail` 등 낯익은 이름이 섞여 있음
- `readelf -d ./chall` → `There is no dynamic section in this file`

## 가장 먼저 할 것
`file ./chall`과 `checksec`으로 정적 링킹임을 확인한 뒤, `strings ./chall | grep "GNU C Library"`로 내장된 libc 버전 배너부터 찾는다. strip 여부는 `file` 출력의 `not stripped`/`stripped` 문구로 바로 알 수 있다. strip 안 됐으면 `nm ./chall`로 끝, strip 됐으면 FLIRT/Function ID 시그니처 적용을 다음 순서로 진행한다.

## 단계별 절차
1. `file ./chall`로 static/strip 여부 확인
2. `readelf -h ./chall`로 `Type: EXEC`(비-PIE 정적) 또는 `Type: DYN`(static-PIE, `-static-pie`로 빌드된 경우)인지 확인 — static-PIE는 재배치가 있어 실제로는 `.dynamic`에 흔적이 남을 수 있으므로 `readelf -d`도 같이 확인
3. `strings ./chall | grep -i "GNU C Library"`로 내장 libc 버전 확인
4. strip 안 됐으면 `nm ./chall | grep ' T '`로 전역 함수 이름 전체 나열
5. strip 됐으면 IDA FLIRT 또는 Ghidra Function ID 시그니처 적용, 매칭률 확인
6. 시그니처가 안 맞으면 `objdump -d ./chall`에서 `_start`부터 수동으로 콜체인을 따라가며 `main` 위치 특정(REV-0097~0099)
7. `main` 근처에서 반복적으로 호출되는 짧은 함수(가변 인자 없이 포인터 하나 받고 끝나는 형태 등)를 `malloc`/`free`/`strlen` 후보로 지목하고, GDB로 실제 실행시켜 인자·반환값을 관찰해 검증

## 명령어/단축키
```bash
file ./chall
checksec --file=./chall
readelf -h ./chall
readelf -d ./chall
readelf -l ./chall
strings ./chall | grep -i "GNU C Library"
nm ./chall | grep ' T '
objdump -d ./chall > chall.asm
```
IDA: File → Load file → FLIRT signature file. Ghidra: Function ID 분석 옵션(Analysis → Auto Analyze → Function ID Analyzer).

## 출력 해석
- `readelf -d`에서 `There is no dynamic section in this file`이 나오면 완전 정적 링킹 — GOT/PLT 관련 REV-0100, REV-0678 개념이 적용되지 않는다는 뜻이다.
- `strings` 결과에서 나온 libc 버전은 힙 관련 리버싱(tcache/fastbin, REV-0654)을 할 때도 정확히 그 버전 기준으로 구조체 오프셋을 맞춰야 한다.
- FLIRT/Function ID로 이름이 붙은 함수라도 100% 신뢰하지 말고, 인자 개수·호출 패턴이 실제 라이브러리 함수와 맞는지 GDB로 한 번은 검증하는 습관이 안전하다.

## 흔한 실수
- 정적 바이너리에서 REV-0101처럼 Import 창을 찾으며 시간을 낭비하는 것 — 애초에 import가 없다.
- FLIRT 매칭 결과를 검증 없이 그대로 믿고 잘못된 함수 이름으로 로직을 오해하는 것.
- strip된 정적 바이너리를 보고 "분석 불가능"이라 포기하는 것 — `_start`부터 수동 추적은 항상 가능한 경로다.
- static-PIE(`-static-pie`)인데 `readelf -d`에 `.dynamic`이 보인다고 "동적 링킹이네"라고 착각하는 것. static-PIE는 재배치를 위한 최소한의 동적 섹션만 갖고 있을 뿐 외부 라이브러리는 로드하지 않는다(`readelf -d` 결과에 `NEEDED` 항목이 없으면 static-PIE로 의심).

## 막혔을 때 다음 체크
- musl로 정적 링크된 바이너리라 glibc 시그니처가 전혀 안 맞는다면 → REV-0647 musl libc와 glibc 차이가 리버싱에 미치는 영향
- `_start`부터 `main`까지 추적하는 구체적 방법이 기억 안 나면 → REV-0097 ELF Entry Point에서 main까지, REV-0099 __libc_start_main이 무엇이고 main을 찾는 법
- 찾아낸 malloc/free 호출로 힙 구조를 더 깊이 분석하려면 → REV-0654 tcache와 fastbin 등 glibc 힙 구조 개요, REV-0655 glibc malloc 내부 흐름 개요
- 동적 링킹 바이너리의 기본 분석법이 헷갈리면 → REV-0101 Dynamic Linking과 Import 함수 추적

## 미니 예제
```bash
$ file ./chall
chall: ELF 64-bit LSB executable, x86-64, ... statically linked, not stripped, ...

$ readelf -d ./chall
readelf: Warning: no .dynamic section in this file
There is no dynamic section in this file.

$ strings ./chall | grep "GNU C Library"
GNU C Library (Ubuntu GLIBC 2.31-0ubuntu9.9) stable release version 2.31.

$ nm ./chall | grep -E ' T (malloc|free|main)$'
0000000000403c50 T free
0000000000403ae0 T malloc
0000000000401a1d T main
```
strip 안 된 이 예시는 `nm` 한 줄로 `main`, `malloc`, `free`의 정확한 주소를 바로 얻을 수 있다. strip됐다면 이 이름들이 사라지고 같은 주소에 `sub_403c50` 식으로만 보이므로, FLIRT 적용 또는 `_start` 수동 추적이 필요해진다.

## 관련 글
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0097 — ELF Entry Point에서 main까지
- REV-0099 — __libc_start_main이 무엇이고 main을 찾는 법
- REV-0647 — musl libc와 glibc 차이가 리버싱에 미치는 영향
- REV-0648 — glibc 버전별 함수 시그니처 차이 확인법
- REV-0654 — tcache와 fastbin 등 glibc 힙 구조 개요(리버싱 관점)

## 출처/검증
- ELF `INTERP`/`.dynamic` 세그먼트 존재 여부와 정적/동적 링킹 구분: System V ABI 및 ELF Specification 기준.
- IDA FLIRT, Ghidra Function ID 시그니처 매칭 방식: Hex-Rays IDA 공식 문서 및 Ghidra 공식 문서(Function ID Analyzer) 기준.
- glibc 버전 배너 문자열(`GNU C Library ... stable release version`)은 실제 Ubuntu 22.04/20.04 배포 바이너리에서 반복 확인되는 패턴 (2026-09-08 검증).
