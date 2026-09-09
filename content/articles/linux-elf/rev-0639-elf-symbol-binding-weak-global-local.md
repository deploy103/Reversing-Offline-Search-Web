---
id: REV-0639
title: "ELF 심볼 바인딩(WEAK/GLOBAL/LOCAL) 빠른 참조"
slug: "rev-0639-elf-symbol-binding-weak-global-local"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [readelf, nm, objdump]
keywords: ["STB_LOCAL", "STB_GLOBAL", "STB_WEAK", "ELF32_ST_BIND", "심볼 바인딩", "symbol binding", "st_info"]
aliases: ["ELF 심볼 바인딩", "weak symbol", "global symbol", "local symbol", "nm 대문자 소문자 의미"]
symptom_keywords: ["nm 출력에서 대문자 소문자 차이", "readelf -s Bind 열 의미", "같은 이름 심볼이 두 개 있음", "LD_PRELOAD로 함수가 덮어써짐"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
ELF 심볼 테이블의 각 항목은 `st_info` 필드 하나에 **바인딩(누가 볼 수 있고 링크 시 어떻게 취급되는지)**과 **타입(함수인지 데이터인지)**을 함께 담고 있으며, 바인딩은 `LOCAL`(파일 내부 전용) / `GLOBAL`(외부에 노출, 유일해야 함) / `WEAK`(외부에 노출되지만 같은 이름의 GLOBAL 심볼에 밀려도 됨) 세 가지가 핵심이다.

## 언제 검색해야 하나
- `readelf -s`나 `nm` 출력의 `Bind` 열(`LOCAL`/`GLOBAL`/`WEAK`)이 무슨 의미인지 헷갈릴 때
- `nm` 결과에서 같은 함수 이름이 대문자(`T`)와 소문자(`t`)로 다르게 표시되는 이유가 궁금할 때
- `LD_PRELOAD`로 `malloc` 같은 함수를 후킹하는 원리(왜 덮어쓰기가 가능한지)를 이해하고 싶을 때

## 핵심 개념

### st_info 필드 구조
ELF 심볼 테이블(`Elf64_Sym`/`Elf32_Sym`)의 `st_info`는 1바이트 필드로, 상위 4비트가 바인딩, 하위 4비트가 타입이다.
```c
#define ELF32_ST_BIND(info)   ((info) >> 4)
#define ELF32_ST_TYPE(info)   ((info) & 0xf)
#define ELF32_ST_INFO(b, t)   (((b) << 4) + ((t) & 0xf))
// ELF64도 매크로 이름만 ELF64_ST_BIND/TYPE로 동일한 구조
```

### 바인딩(Binding) 값
| 값 | 이름 | 의미 |
|---|---|---|
| 0 | `STB_LOCAL` | 그 오브젝트 파일 안에서만 보임. 다른 파일의 같은 이름 심볼과 충돌하지 않음(예: `static` 함수/전역변수, 컴파일러가 만든 내부 라벨) |
| 1 | `STB_GLOBAL` | 링크 단위 전체에서 보임. **같은 이름의 GLOBAL 심볼이 여러 오브젝트에 있으면 링커 에러**(multiple definition) |
| 2 | `STB_WEAK` | GLOBAL과 비슷하게 외부에 보이지만, 같은 이름의 STB_GLOBAL 심볼이 있으면 그쪽이 우선하고 충돌 에러도 안 남. GLOBAL이 없으면 WEAK 심볼 자체가 쓰임 |
| 10~12 | `STB_LOOS`~`STB_HIOS` | OS별 확장 범위 |
| 13~15 | `STB_LOPROC`~`STB_HIPROC` | 프로세서별 확장 범위 |

### 타입(Type) 값 — 참고로 함께 알아두면 좋음
`STT_NOTYPE`(0), `STT_OBJECT`(1, 데이터), `STT_FUNC`(2, 함수), `STT_SECTION`(3), `STT_FILE`(4), `STT_COMMON`(5), `STT_TLS`(6, `__thread` 변수), `STT_GNU_IFUNC`(10, GNU 확장 — ifunc resolver).

### 왜 WEAK가 필요한가 — 심볼 인터포지션(Interposition)의 핵심
동적 링커가 여러 공유 라이브러리에서 같은 이름의 심볼을 찾을 때, 로드 순서상 먼저 만난 **STB_GLOBAL** 심볼이 최종 승자가 된다. `LD_PRELOAD=./my_malloc.so ./chall`로 `malloc`을 후킹하는 것이 가능한 이유가 바로 이것 — 프리로드된 라이브러리의 `malloc`(GLOBAL)이 libc의 `malloc`보다 먼저 심볼 검색 순서에 들어와 우선권을 갖는다. glibc 내부에서도 `__malloc_hook` 같은 확장 지점이나, `pthread_*` 함수들이 libpthread가 없을 때 동작하도록 libc 안에 WEAK 버전의 스텁을 두는 패턴에 이 바인딩 규칙이 쓰인다.

## 화면/코드에서 보이는 징후
- `readelf -s ./chall` 출력에서 `Bind` 열에 `LOCAL`, `GLOBAL`, `WEAK` 문자열이 그대로 보임
- `nm ./chall` 출력에서 타입 문자가 **소문자면 LOCAL, 대문자면 GLOBAL**, `W`/`w`는 WEAK(대문자 `W`는 기본값이 지정된 weak, 소문자 `w`는 값이 없는 weak)
- 정적 분석 중 같은 이름의 심볼이 여러 오브젝트/라이브러리에 걸쳐 나타나는데 링크 에러가 안 나는 경우 → WEAK일 가능성

## 가장 먼저 할 것
`readelf -s ./chall | less`로 심볼 테이블을 열고, 관심 있는 함수 이름을 검색해 `Bind` 열을 확인한다. 함수 후킹/오버라이드 문제라면 WEAK 여부부터 본다.

## 단계별 절차

**1) readelf로 심볼과 바인딩 함께 보기**
```bash
readelf -s ./chall | grep -i printf
```
출력 예:
```
    45: 0000000000401136    21 FUNC    GLOBAL DEFAULT   14 printf
```
열 순서는 `Num: Value Size Type Bind Vis Ndx Name`이다.

**2) nm으로 빠르게 대소문자만 보기**
```bash
nm ./chall | grep printf
```
```
                 U printf@GLIBC_2.2.5   # U = undefined (외부에서 채워짐)
```
정의된 GLOBAL 함수라면 `T`(text 섹션의 함수), LOCAL이면 `t`가 보인다.

**3) WEAK 심볼만 골라보기**
```bash
readelf -s ./chall | awk '$5=="WEAK"'
nm -D ./libtarget.so | grep ' W \| w '
```

**4) 동적 심볼 테이블에서 확인 (동적 링킹된 라이브러리 함수)**
```bash
readelf --dyn-syms ./chall
```

## 명령어/단축키
```bash
readelf -s ./chall
readelf --dyn-syms ./chall
nm ./chall
nm -D ./lib.so   # 동적 심볼만
```

## 출력 해석
`nm` 타입 문자 요약: `T`/`t` = text(코드, 대문자 GLOBAL/소문자 LOCAL), `D`/`d` = 초기화된 데이터, `B`/`b` = BSS, `U` = undefined(다른 오브젝트에서 정의됨, 링크 시 채워짐), `W`/`w` = weak. 대문자/소문자 규칙은 GLOBAL/LOCAL을 가리키고, `W` 계열만 별도 카테고리다.

## 흔한 실수
- `nm` 결과의 대문자를 "중요한 함수", 소문자를 "안 중요한 함수"로 오해하는 것 — 실제로는 단지 바인딩(가시성) 차이일 뿐 중요도와 무관하다.
- WEAK 심볼이 항상 "약해서 무시된다"고 오해하는 것 — GLOBAL 정의가 **없으면** WEAK 정의가 그대로 사용된다. WEAK는 "있으면 쓰이지만 다른 GLOBAL한테는 양보한다"는 뜻이다.
- `STB_LOCAL` 심볼을 다른 컴파일 유닛/공유 라이브러리에서 참조하려 하는 것 — LOCAL은 애초에 그 오브젝트 파일 밖에서는 안 보이므로 링크 자체가 안 된다.

## 막혔을 때 다음 체크
- PLT/GOT를 통한 실제 심볼 해석 흐름이 궁금하면 → REV-0100 PLT와 GOT 기초.
- 동적 링킹 자체의 큰 그림이 궁금하면 → REV-0101 Dynamic Linking과 Import 함수 추적.
- 심볼 해석에 쓰이는 `.dynamic` 섹션의 각 태그가 궁금하면 → REV-0641 ELF Dynamic Section 태그(DT_*) 빠른 참조.

## 미니 예제
```c
// a.c
int shared_val = 1;          // GLOBAL
static int local_val = 2;    // LOCAL
__attribute__((weak)) void hook(void) { /* 기본 구현 */ }  // WEAK
```
```bash
$ gcc -c a.c && nm a.o
0000000000000000 D shared_val
0000000000000004 d local_val
0000000000000000 W hook
```
`shared_val`은 대문자 `D`(GLOBAL 데이터), `local_val`은 소문자 `d`(LOCAL 데이터), `hook`은 `W`(WEAK 함수)로 정확히 구분되어 나온다.

## 관련 글
- REV-0100 — PLT와 GOT 기초
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0641 — ELF Dynamic Section 태그(DT_*) 빠른 참조
- REV-0093 — nm으로 심볼 찾기

## 출처/검증
- `st_info`/`ELF32_ST_BIND`/`ELF32_ST_TYPE` 매크로 및 `STB_*`/`STT_*` 상수 값: System V Application Binary Interface(generic ABI) "Symbol Table" 챕터 기준.
- `nm` 타입 문자(`T`/`t`/`U`/`W`/`w` 등) 의미: `nm(1)` man page 기준 (2026-09-08 검증).
- WEAK 심볼과 동적 링커 인터포지션 동작: glibc 동적 로더 심볼 해석 순서 및 `LD_PRELOAD` 관련 표준 문서 기준.
