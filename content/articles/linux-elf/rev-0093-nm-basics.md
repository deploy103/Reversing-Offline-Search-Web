---
id: REV-0093
title: "nm으로 심볼 찾기"
slug: "rev-0093-nm-basics"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["nm", "binutils"]
keywords: ["nm", "nm -D", "심볼 테이블", "T t U 심볼 타입", "no symbols"]
aliases: ["nm 사용법", "nm 옵션", "nm 명령어", "nm 심볼 타입"]
symptom_keywords: ["nm no symbols 뜸", "nm 결과 T t 차이 모름", "심볼 목록을 빠르게 뽑고 싶음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`nm`은 ELF 파일의 심볼 테이블(함수/전역 변수 이름과 주소)만 뽑아서 간단한 한 줄 목록으로 보여주는 도구로, `main`이나 특정 함수의 주소를 가장 빠르게 확인할 때 쓴다.

## 언제 검색해야 하나
- `main`이나 특정 함수의 주소를 딱 한 줄로 빠르게 확인하고 싶을 때
- 바이너리가 strip됐는지 아닌지 빠르게 판단하고 싶을 때
- 정적 라이브러리(`.a`)나 오브젝트 파일(`.o`) 안에 어떤 함수가 정의/미정의 상태인지 확인하고 싶을 때

## 핵심 개념
`nm`(name list)은 `readelf -s`, `objdump -t`와 사실상 같은 데이터(심볼 테이블)를 보여주지만, 출력이 훨씬 간결하다 — `주소 타입 이름` 딱 세 컬럼뿐이다. 빠르게 "이 함수가 있나 없나, 주소가 뭔가"만 확인할 때는 `nm`이 가장 타이핑이 짧고 결과도 읽기 쉽다.

### 심볼 타입 문자 (가장 자주 보는 것들)
- `T` (대문자) — `.text`에 정의된 전역(external) 함수. **이 바이너리 안에 코드가 실제로 있다**는 뜻.
- `t` (소문자) — `.text`에 정의된 지역(static/local) 함수.
- `U` — Undefined. 이 심볼은 여기 정의되어 있지 않고 **외부(동적 라이브러리)에서 가져와야 한다.** `printf`, `malloc` 같은 libc 함수가 여기 해당.
- `D` / `d` — 초기화된 데이터(`.data`) 전역/지역 변수.
- `B` / `b` — 초기화 안 된 데이터(`.bss`) 전역/지역 변수.
- `R` / `r` — 읽기 전용 데이터(`.rodata`).
- `W` — Weak symbol(약한 심볼, 다른 곳에서 같은 이름이 정의되면 그쪽이 우선됨).

대문자는 전역(다른 파일에서도 보임, `GLOBAL` bind), 소문자는 지역(그 파일 안에서만 보임, `LOCAL` bind)이라는 규칙을 기억하면 `readelf -s`의 `Bind` 컬럼과 바로 대응된다.

## 화면/코드에서 보이는 징후
- `nm ./chall` 실행 시 `nm: chall: no symbols`라고 나오면 strip된 바이너리(REV-0010 참고)
- 결과가 아주 많이 나오면 동적 심볼(`.dynsym`)까지 포함해서 보고 있는지, `.symtab`(전체 심볼)까지 있는지 구분해서 봐야 함

## 가장 먼저 할 것
```bash
nm ./chall | grep ' T main'
```
`main`이 strip 안 된 상태로 남아있는지, 주소가 무엇인지 한 줄로 바로 확인한다.

## 단계별 절차

**1) 기본 실행 — 전체 심볼 테이블(.symtab)**
```bash
nm ./chall
```
출력 예:
```
0000000000004010 B __bss_start
0000000000004010 b completed.0
                 U __libc_start_main@GLIBC_2.34
0000000000001149 T main
0000000000001060 T _start
0000000000001040 T puts@plt
```
strip된 바이너리라면:
```bash
$ nm ./chall_stripped
nm: chall_stripped: no symbols
```

**2) 동적 심볼만 보기 (`-D`) — strip돼도 대부분 남아있음**
```bash
nm -D ./chall
```
`.symtab`이 지워진 strip 바이너리라도 동적 링킹에 필요한 `.dynsym`은 대부분 남아있어서, `-D` 옵션으로는 `printf`, `puts` 같은 임포트된 라이브러리 함수 이름을 여전히 볼 수 있다(단, `main`처럼 사용자 정의 함수는 안 보임 — 그건 `.symtab`에만 있었기 때문).

**3) 주소순 정렬**
```bash
nm -n ./chall     # 주소 오름차순 정렬 (기본은 이름순)
```

**4) 정의된 심볼만 필터링 (Undefined 제외)**
```bash
nm ./chall | grep -v ' U '
```

**5) Undefined(외부에서 가져오는) 심볼만 보기 — 이 바이너리가 뭘 쓰는지 파악**
```bash
nm -D ./chall | grep ' U '
```

## 명령어/단축키
```bash
nm ./chall              # 심볼 테이블 (.symtab, strip되면 실패)
nm -D ./chall           # 동적 심볼 (.dynsym, strip돼도 대부분 남음)
nm -n ./chall           # 주소순 정렬
nm -C ./chall           # C++ 이름 demangle (예: _Z3fooi -> foo(int))
nm --size-sort ./chall  # 크기순 정렬(큰 함수부터, 핵심 로직 함수 추정에 유용)
```

## 출력 해석
- `nm: no symbols`는 "`.symtab` 섹션이 없다"는 뜻이지 파일이 손상됐다는 뜻이 아니다. strip 명령이 지운 것뿐이며 실행에는 전혀 지장이 없다.
- `--size-sort` 결과에서 가장 큰 함수들이 대개 사용자가 작성한 핵심 로직일 확률이 높다 — 라이브러리 초기화 코드는 대체로 작고 반복적이다.
- `U printf@GLIBC_2.2.5`처럼 버전 문자열이 붙는 것은 glibc의 심볼 버저닝(symbol versioning) 때문 — 같은 이름의 함수가 glibc 버전마다 다른 구현일 수 있어서, 어떤 버전의 ABI를 요구하는지 명시된 것이다.

## 흔한 실수
- `nm: no symbols`가 나오면 "이 파일은 분석 불가능"이라고 포기하는 것 — `nm -D`로 동적 심볼은 여전히 볼 수 있고, `readelf -h`의 Entry point부터 시작해 REV-0010 방식으로 계속 분석 가능하다.
- `nm`의 기본 출력이 이름순 정렬이라는 걸 모르고 "코드 순서"라고 착각하는 것 — 실행 순서를 보려면 `-n`(주소순)을 써야 한다.
- 정적 라이브러리(`.a`) 안의 여러 `.o` 파일 심볼이 섞여 나오는 걸 보고 혼란스러워하는 것 — `nm libfoo.a`는 아카이브 안 모든 오브젝트 파일의 심볼을 순서대로 이어붙여 보여준다.

## 막혔을 때 다음 체크
- strip된 바이너리에서 어떻게 시작점을 잡는지 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- 더 자세한 심볼 정보(바인딩, 가시성 등)가 필요하면 → [REV-0091 readelf 기본 사용법](./rev-0091-readelf-basics.md)의 `-s` 옵션
- 함수 코드 자체를 보고 싶으면 → [REV-0092 objdump 기본 사용법](./rev-0092-objdump-basics.md)

## 미니 예제
```bash
$ nm chall | grep -E ' [Tt] '
0000000000001149 T main
0000000000001060 T _start
0000000000001030 t deregister_tm_clones
0000000000001199 T __libc_csu_init

$ nm chall | grep ' U '
                 U __libc_start_main@GLIBC_2.34
                 U puts@GLIBC_2.2.5
```
`main`(0x1149)과 `_start`(0x1060) 주소를 즉시 확인했고, 이 바이너리가 외부에서 가져다 쓰는 함수가 `__libc_start_main`과 `puts` 둘뿐이라는 것도 함께 파악했다.

## 관련 글
- [REV-0091 — readelf 기본 사용법](./rev-0091-readelf-basics.md)
- [REV-0092 — objdump 기본 사용법](./rev-0092-objdump-basics.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- [REV-0009 — main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)

## 출처/검증
- 심볼 타입 문자 정의: GNU binutils `nm(1)` man page "The symbol type" 섹션 기준 (2026-09-08 검증).
- glibc 심볼 버저닝: glibc 공식 문서 "Symbol Versioning" 개념 기준.
