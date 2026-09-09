---
id: REV-0666
title: "nm으로 정적 바이너리에서 원하는 심볼 찾기"
slug: "rev-0666-nm-static-binary-symbol-search"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [nm, GDB, Pwndbg, readelf, objdump]
keywords: ["nm", "정적 링킹", "static binary", "심볼 테이블", "symbol table", ".symtab"]
aliases: ["nm 정적 바이너리", "static binary nm 사용법", "nm grep 심볼 찾기", "정적 바이너리 함수 이름 찾기"]
symptom_keywords: ["nm으로 아무것도 안 나옴", "nm -D 결과가 비어있음", "정적 바이너리라 함수 이름을 모르겠음", "strip 안 됐는데 함수가 너무 많음"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
정적 링킹된 ELF는 `printf`, `malloc`, `strcpy` 같은 glibc 내부 함수 수천 개가 바이너리 안에 통째로 박혀 있는데, `strip`이 안 된 상태라면 `nm ./chall`과 `grep`만으로 그중 원하는 함수의 정확한 주소를 몇 초 만에 찾아낼 수 있다.

## 언제 검색해야 하나
- `file ./chall` 결과에 `statically linked`가 보이고, IDA/Ghidra에서 함수가 수천 개 나와서 어디가 진짜 `main`이고 어디가 glibc 내부 함수인지 헷갈릴 때
- GDB에서 `break malloc`을 걸었는데 `Function "malloc" not defined`라고 나올 때 — 정적 바이너리라 심볼 이름으로 바로 안 걸릴 수 있어 주소를 직접 찾아야 할 때
- `nm -D ./chall`을 돌렸는데 결과가 텅 비어서 당황스러울 때

## 핵심 개념

### 정적 바이너리에는 "동적 심볼 테이블"이 없다
공유 라이브러리를 쓰는 일반 바이너리는 `.dynsym`(동적 심볼 테이블)에 실제로 링크 시점에 해석해야 할 외부 함수 이름들이 들어있고, `nm -D`는 이 `.dynsym`만 읽는다. 그런데 정적 링킹(REV-0101 Dynamic Linking과 Import 함수 추적 참고)된 바이너리는 `malloc`, `printf` 같은 함수의 실제 코드가 이미 바이너리 안에 다 복사되어 있어서 런타임에 더 이상 해석할 게 없고, 그래서 `.dynsym` 자체가 없거나 텅 비어 있다. 이럴 때 `nm -D`는 아무것도 출력하지 않거나 `nm: no symbols`라고 나온다.

### 필요한 건 `.symtab`이다
심볼 이름과 주소 정보는 대신 `.symtab`(전체 심볼 테이블)에 들어있다. `nm`을 옵션 없이 그냥 실행하면 기본적으로 `.symtab`을 읽는다. `.symtab`은 디버깅/링킹 편의를 위한 정보라 `strip` 명령으로 통째로 제거될 수 있는데, strip이 안 된 정적 바이너리라면 glibc가 컴파일될 때 만들어진 함수 이름 수천 개가 그대로 남아있다.

### nm 심볼 타입 문자
`nm` 출력의 두 번째 컬럼 한 글자가 심볼 종류를 나타낸다.
- `T` / `t`: `.text` 섹션의 전역/지역(대문자/소문자) 함수 — 실제 실행 코드
- `D` / `d`: 초기화된 전역/지역 데이터
- `B` / `b`: `.bss`(초기화 안 된 데이터)의 전역/지역 심볼
- `U`: undefined — 이 파일 안에서 정의되지 않고 외부에서 와야 하는 심볼(정적 바이너리에서는 거의 안 보임)
- `W`: weak 심볼(다른 곳에 같은 이름이 있으면 그쪽이 우선)
- `R` / `r`: 읽기 전용 데이터(`.rodata`)

대문자는 전역(global/외부에서 링크 가능), 소문자는 그 파일(정확히는 그 컴파일 단위) 안에서만 보이는 지역 심볼이라는 규칙을 기억해두면 `T malloc`처럼 대문자로 나온 함수 심볼을 우선적으로 신뢰할 수 있다.

## 화면/코드에서 보이는 징후
- IDA/Ghidra Functions 창에 `sub_4xxxxx` 같은 무명 함수가 아니라 이미 `malloc`, `free`, `__libc_csu_init` 같은 이름이 붙어있다면 심볼 테이블이 살아있는 정적 바이너리라는 뜻이다.
- `checksec ./chall`(REV-0096) 결과에 `Statically linked` 또는 `No PIE` + 매우 큰 파일 크기(수백 KB~수 MB)가 같이 보이면 정적 링킹 가능성이 높다.

## 가장 먼저 할 것
```bash
file ./chall
```
결과에 `statically linked`가 보이면, 바로 이어서 다음을 실행해 심볼이 살아있는지부터 확인한다.
```bash
nm ./chall | wc -l
```
수백~수천 줄이 나오면 심볼 테이블이 살아있는 것이고, `nm: ./chall: no symbols`가 나오면 strip된 정적 바이너리(REV-0668 참고)라 다른 접근이 필요하다.

## 단계별 절차

**1) 전체 심볼 개수와 대략적인 형태 확인**
```bash
nm ./chall | wc -l
nm ./chall | head -20
```

**2) 원하는 이름으로 grep**
```bash
nm ./chall | grep -w malloc
nm ./chall | grep -iE "scanf|printf"
```
`-w`로 단어 경계를 맞추면 `malloc`을 찾을 때 `malloc_consolidate`, `malloc_trim` 같은 관련 함수까지 같이 딸려 나오는 걸 막을 수 있다.

**3) 함수(T/t 타입)만 골라서 보기**
```bash
nm ./chall | awk '$2 == "T" || $2 == "t" {print}'
```

**4) 주소 순으로 정렬해서 흐름 파악**
```bash
nm -n ./chall | less
```
`-n`은 주소 오름차순 정렬이라, `main` 근처에 실제로 어떤 순서로 함수들이 배치되어 있는지 훑어보기 좋다.

**5) C++ 바이너리라면 이름 복원(demangle)**
```bash
nm -C ./chall | grep -i "MyClass"
```
`-C`는 `_ZN7MyClass...` 같은 맹글링된 이름을 `MyClass::method(...)` 형태로 사람이 읽을 수 있게 바꿔준다.

**6) 찾은 주소를 GDB에서 바로 사용**
```bash
nm ./chall | grep -w malloc
# 0000000000401ce0 T malloc
gdb ./chall
(gdb) break *0x401ce0
```
정적 바이너리에서 `break malloc`이 바로 안 먹는 경우, 이렇게 `nm`으로 찾은 주소에 직접 브레이크포인트를 걸면 확실하다. Pwndbg를 쓰고 있다면 심볼이 살아있는 경우 `break malloc`도 대개 정상 작동하니, 안 될 때만 이 방식으로 우회한다.

## 명령어/단축키
```bash
nm ./chall                        # .symtab 전체 출력
nm -D ./chall                     # .dynsym만 출력 (정적 바이너리는 보통 비어있음)
nm -n ./chall                     # 주소 오름차순 정렬
nm -C ./chall                     # C++ 이름 복원(demangle)
nm --defined-only ./chall         # 정의된 심볼만
nm ./chall | grep -w malloc       # 이름으로 필터링
nm ./chall | awk '$2=="T"'        # 전역 함수만
```

## 출력 해석
실전 예시:
```
$ nm ./chall | grep -w malloc
0000000000401ce0 T malloc
$ nm ./chall | grep -w free
0000000000401d90 T free
$ nm ./chall | grep -w __libc_start_main
0000000000401160 T __libc_start_main
```
- 첫 컬럼은 16자리 16진수 주소(파일 내 정적 주소, PIE가 아니면 이 값이 곧 실행 시 가상주소와 같다 — REV-0103 PIE와 주소 계산 참고).
- 둘째 컬럼 `T`는 이 심볼이 `.text`의 전역 함수라는 뜻.
- 셋째 컬럼이 함수 이름. 이 주소를 그대로 GDB `break *0x401ce0`나 IDA `Jump to address(G)`에 넣으면 된다.

## 흔한 실수
- `nm -D`만 돌려보고 "심볼이 없다"고 결론 내리는 것 — 정적 바이너리에서는 옵션 없는 `nm`(즉 `.symtab`)을 먼저 시도해야 한다.
- grep 없이 `nm ./chall`을 그냥 스크롤로 훑는 것 — glibc 정적 링킹 바이너리는 심볼이 수천 개라 반드시 `grep`/`awk`로 좁혀야 한다.
- 주소를 찾고 나서 PIE 바이너리인데 ASLR 오프셋을 더하지 않고 그대로 GDB에 넣는 것 — `nm`이 보여주는 주소는 파일 기준 정적 주소이므로, PIE라면 실행 중 실제 로드 베이스(REV-0104 ASLR)를 더해야 한다.
- `strip`된 바이너리에 대고 계속 `nm`만 붙잡고 있는 것 — strip되면 `.symtab`도 사라지므로 이때는 시그니처 매칭(REV-0668) 같은 다른 접근이 필요하다.

## 막혔을 때 다음 체크
- `nm`이 아무것도 안 보여준다면 → REV-0668 strip된 정적 바이너리에서 libc 함수 식별 개념으로 이동
- 심볼은 있는데 소스 라인 정보까지 필요하다면 → REV-0667 ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기
- 정적 링킹 자체의 특징과 분석 전략이 더 궁금하다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- `nm` 대신 섹션 구조 전체를 보고 싶다면 → REV-0091 readelf 기본 사용법

## 미니 예제
```bash
$ file ./chall
./chall: ELF 64-bit LSB executable, x86-64, ... statically linked, not stripped

$ nm ./chall | wc -l
2143

$ nm ./chall | grep -w scanf
0000000000403a20 T scanf

$ nm ./chall | grep -w main
0000000000401bd6 T main
```
`main`의 주소를 바로 확인했으니 `gdb ./chall` → `break *0x401bd6` → `run`으로 바로 진입할 수 있고, `scanf` 주소에도 브레이크포인트를 걸어 입력 처리 지점을 잡을 수 있다.

## 관련 글
- REV-0668 — strip된 정적 바이너리에서 libc 함수 식별 개념(시그니처 매칭)
- REV-0667 — ELF에서 디버그 심볼(.debug_info)이 남아있는 경우 활용하기
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0093 — nm으로 심볼 찾기
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0101 — Dynamic Linking과 Import 함수 추적

## 출처/검증
- `nm` 옵션(`-D`, `-n`, `-C`, `--defined-only`) 및 심볼 타입 문자(T/t/D/d/B/b/U/W): GNU Binutils `nm(1)` man page 기준.
- 정적 링킹 시 `.dynsym`이 비고 `.symtab`에 심볼이 남는 동작: ELF 스펙 및 GNU ld 동작 기준 (2026-09-08 검증).
