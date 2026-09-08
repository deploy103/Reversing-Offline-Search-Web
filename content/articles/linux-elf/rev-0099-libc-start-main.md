---
id: REV-0099
title: "__libc_start_main이 무엇이고 main을 찾는 법"
slug: "rev-0099-libc-start-main"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, "objdump", "readelf", "binutils"]
keywords: ["__libc_start_main", "__libc_start_call_main", "libc_start_main 시그니처", "glibc 버전 차이", "main 함수 포인터"]
aliases: ["libc_start_main이란", "__libc_start_main 시그니처", "libc_start_main 인자", "libc_start_main main 찾기"]
symptom_keywords: ["__libc_start_main 인자가 몇개인지 모름", "libc_start_main 버전마다 다름", "stripped에서 libc_start_main으로 main 찾기"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`__libc_start_main`은 glibc가 제공하는 "진짜 프로그램 초기화 담당자"로, `_start`로부터 넘겨받은 함수 포인터(그 중 **첫 번째 인자가 `main`**)를 이용해 C 런타임을 완전히 세팅한 뒤 `main`을 호출하고, `main`이 끝나면 `exit()`까지 처리하는 함수다 — glibc 버전에 따라 내부 구현이 갈렸지만 "첫 번째 인자가 main"이라는 사실은 변하지 않는다.

## 언제 검색해야 하나
- `_start`에서 `__libc_start_main`을 호출하는 걸 봤는데, 이 함수가 정확히 무슨 일을 하는지, 인자가 몇 개고 순서가 어떻게 되는지 알고 싶을 때
- glibc 버전에 따라 `__libc_start_main`의 동작이나 심볼 이름이 달라 보여서(`__libc_start_main@GLIBC_2.34` vs 그냥 `__libc_start_main`) 혼란스러울 때
- strip된 바이너리에서 `main` 심볼 자체는 지워졌지만 `__libc_start_main` 호출은 여전히 보일 때, 이걸 이용해 `main`을 어떻게 찾는지 구체적인 방법이 필요할 때

> 이 문서는 `__libc_start_main` 자체의 시그니처, 인자 순서, glibc 버전 차이, stripped 바이너리에서 실제로 어떻게 보이는지를 깊이 다룬다. "IDA/Ghidra에서 main을 못 찾을 때 전체적으로 뭘 해야 하는지"에 대한 더 넓은 범위의 실전 가이드는 [REV-0009 main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)을 먼저 참고하고, 이 문서는 그 안에서 언급된 `__libc_start_main` 메커니즘 자체를 파고드는 심화 문서로 보면 된다.

## 핵심 개념

### 전통적인(구버전) 시그니처
glibc 2.33 이전까지 `__libc_start_main`은 대략 다음과 같은 시그니처를 가진 하나의 큰 함수였다(`csu/libc-start.c`, 실제로는 `#ifdef` 매크로로 미묘하게 변형되지만 개념적으로는 이 형태):

```c
int __libc_start_main(
    int (*main)(int, char **, char **),  // 1번째 인자 = 진짜 main
    int argc,                            // 2번째 인자 = argc
    char **argv,                         // 3번째 인자 = argv
    void (*init)(void),                  // 4번째 인자 = __libc_csu_init
    void (*fini)(void),                  // 5번째 인자 = __libc_csu_fini
    void (*rtld_fini)(void),             // 6번째 인자 = 동적 로더 정리 함수
    void *stack_end                      // 7번째 인자 = 스택 최상단 주소
);
```

x86-64 SysV 호출 규약이므로 이 인자들은 순서대로 **RDI, RSI, RDX, RCX, R8, R9, (스택)**에 담겨 전달된다. REV-0098에서 본 `_start` 코드가 정확히 이 순서로 레지스터를 채웠던 것을 떠올리면 된다: `rdi=main`, `rsi=argc`, `rdx=argv`, `rcx=init`, `r8=fini`, `r9=rtld_fini`, 스택 맨 위=`stack_end`.

이 함수 내부가 실제로 하는 일:
1. TLS(Thread-Local Storage) 초기화 및 스택 보호(카나리) 관련 초기값 세팅.
2. `argc`/`argv`/`environ`을 전역 변수로 등록(그래서 `main`의 세 번째 인자 없이도 전역 `environ`으로 환경변수에 접근 가능).
3. `init` 콜백(보통 `__libc_csu_init`) 호출 → 이 안에서 `.init_array` 섹션에 등록된 함수 포인터들을 순서대로 호출(전역 C++ 생성자, `__attribute__((constructor))` 함수들).
4. **`main(argc, argv, envp)` 호출** — 드디어 사용자 코드 실행.
5. `main`의 리턴값을 받아 `exit(리턴값)` 호출 → 이 안에서 `fini`(`.fini_array`, 전역 소멸자) 처리 후 프로세스 종료.

### glibc 2.34 이후: __libc_start_call_main으로 분리
glibc 2.34(2021년경 배포)부터 내부 구현이 리팩터링되어, `main` 호출과 `exit` 처리를 담당하는 부분이 `__libc_start_call_main`이라는 별도의(주로 인라인되는) 함수로 분리되었다. `__libc_start_main`이라는 심볼 이름과 외부에서 보이는 동작(첫 번째 인자가 `main`)은 호환성을 위해 그대로 유지되지만, 디스어셈블리 레벨에서는 이 변화 때문에:
- 최신 Ubuntu/Debian 등에서 빌드된 바이너리는 `__libc_start_main@GLIBC_2.34`처럼 **버전이 명시된 심볼**로 참조가 걸린다(`nm`/`readelf -s` 출력에서 확인 가능, REV-0093 참고).
- 실제 `main` 호출 지점이 `__libc_start_main` 함수 몸체 안이 아니라 `__libc_start_call_main`(정적 인라인이라 별도 심볼로 안 보이는 경우가 많음) 안일 수 있다.

리버서 입장에서 실전적으로 중요한 결론은 하나다: **glibc 버전이 무엇이든, `_start`가 `__libc_start_main`을 호출할 때 그 첫 번째 인자(RDI)로 넘기는 값은 항상 `main`이다.** 내부 구현이 어떻게 리팩터링되었든 이 외부 계약(ABI)은 바뀌지 않았다.

### musl libc 등 다른 C 라이브러리라면
Alpine Linux 등 musl libc로 빌드된 바이너리는 `__libc_start_main`이라는 이름 자체가 없고, musl 자체의 `_start_c`/`__libc_start_main` 유사 함수(구현이 다름)를 쓴다. 이 문서는 glibc 기준이며, musl 바이너리를 만났다면 `_start`가 호출하는 유일한 큰 함수를 같은 논리(첫 인자 = main)로 접근하되 함수 이름은 다를 수 있다는 점을 감안해야 한다.

## 화면/코드에서 보이는 징후
- `nm ./chall` 또는 `objdump -T ./chall` 결과에 `__libc_start_main@GLIBC_2.34`처럼 버전 접미사가 붙어 있음
- `_start`의 마지막 CALL 대상이 `__libc_start_main@plt`로 표시됨(동적 링킹인 경우 PLT를 거침, REV-0100 참고)
- strip된 바이너리인데도 `__libc_start_main@plt`라는 이름은 여전히 보이는 경우가 많음 — 하지만 바로 그 위에서 `rdi`에 로드되는 `main` 주소 쪽은 이름이 없고 그냥 숫자 주소로만 보임

## 가장 먼저 할 것
`objdump -d -M intel ./chall | grep -B3 'libc_start_main'`로 `_start` 안에서 `__libc_start_main` 호출 직전 코드를 바로 뽑아본다. 그 중 `rdi`에 값을 로드하는 명령어의 대상 주소가 `main`이다.

## 단계별 절차

**1) __libc_start_main 호출부 찾기**
```bash
objdump -d -M intel ./chall | grep -B8 'call.*libc_start_main'
```

**2) 심볼 버전 확인 (glibc 버전 추정)**
```bash
nm -D ./chall | grep libc_start_main
```
출력 예:
```
                 U __libc_start_main@GLIBC_2.34
```
`GLIBC_2.34`가 붙어 있으면 최신 리팩터링 이후 버전으로 빌드/링크된 것이다.

**3) strip된 바이너리에서 main 이름만 사라진 경우**
```bash
$ objdump -d -M intel chall_stripped | grep -B8 'call.*libc_start_main'
    1081:	48 8d 3d c1 00 00 00 	lea    rdi,[rip+0xc1]        # 1149
    1088:	ff 15 12 2f 00 00    	call   QWORD PTR [rip+0x2f12] # 3fa0 <__libc_start_main@GLIBC_2.34>
```
`__libc_start_main`은 여전히 이름이 보이지만(`.dynsym`에 있는 외부 라이브러리 심볼이라 strip으로 안 지워짐), `lea rdi, [rip+0xc1]`이 가리키는 주소(`0x1149`)에는 이름이 없다. **이 주소가 바로 strip으로 이름만 지워진 `main`이다.** 이 주소로 가서 `N`(IDA) 또는 그냥 참고 표시로 `main`이라고 리네임해두면 된다.

**4) GDB로 동적 확인**
```gdb
(gdb) break *_start
(gdb) run
(gdb) x/8i $pc
(gdb) break *0x555555555088   ; call 직전 주소(ASLR 베이스 감안해서 조정)
(gdb) continue
(gdb) print/x $rdi
(gdb) x/4i $rdi
```
`$rdi`가 가리키는 주소를 역어셈블했을 때 `endbr64` / `push rbp` 같은 전형적인 함수 시작 패턴이 보이면 그 함수가 `main`임을 재확인할 수 있다.

**5) 정적 링킹 + strip 조합 (가장 어려운 경우)**
`__libc_start_main` 자체도 이름이 없다. 이 경우 REV-0098에서 설명한 `_start`의 **고유한 코드 패턴**(레지스터를 순서대로 채운 뒤 함수 하나만 CALL하고 리턴하지 않음)으로 `_start` 자체를 식별하고, 그 안의 유일한 CALL 대상을 `__libc_start_main`으로 간주한 뒤, 그 함수 안에서 다시 SysV 인자 규약(RDI가 담고 있던 원래 값)이 어디로 전달되는지 데이터 흐름을 추적해야 한다. IDA의 FLIRT 시그니처가 정적 링킹된 libc 함수를 자동 인식해주는 경우가 많아 실전에서는 이 수작업까지 갈 일이 드물다.

## 명령어/단축키
```bash
objdump -d -M intel ./chall | grep -B8 'call.*libc_start_main'
nm -D ./chall | grep libc_start_main
readelf -s ./chall | grep libc_start_main
```
GDB: `break *_start`, `x/8i $pc`, `print/x $rdi`, `x/4i $rdi`

## 출력 해석
- `__libc_start_main@GLIBC_2.34` 같은 버전 문자열은 "이 바이너리가 링크된 glibc가 최소 2.34 이상의 ABI를 요구한다"는 뜻이지, 실행 시스템의 glibc가 정확히 2.34여야 한다는 뜻은 아니다(하위 호환은 유지됨).
- `main` 위치를 가리키는 `lea rdi, [rip+offset]`에서 계산된 절대 주소는, PIE 바이너리라면 정적 분석 상의 상대 주소일 뿐이고 실제 실행 시에는 ASLR 베이스가 더해진다는 걸 REV-0089/REV-0096에서 다룬 PIE 개념과 함께 기억해야 한다.

## 흔한 실수
- `__libc_start_main`의 인자가 항상 정확히 7개라고 암기하는 것 — glibc 버전 리팩터링에 따라 세부 인자 구성이 조금씩 바뀌었다. 외워야 할 건 인자 개수가 아니라 **"첫 번째 인자가 main"** 이라는 불변 규칙이다.
- strip된 바이너리에서 `__libc_start_main`이라는 이름이 안 보인다고 착각하는 것 — 동적 링킹이라면 `.dynsym`에 남아있어 대부분 그대로 보인다. 이름이 진짜로 안 보이는 경우는 정적 링킹 + strip 조합뿐이다.
- `main`의 세 번째 인자(`envp`)가 항상 존재한다고 프로그램 안에서 가정하는 것 — 표준 C에서 `main(int argc, char **argv)` 두 인자만 선언해도 문제없이 컴파일되고 동작한다(POSIX 확장으로 `envp`가 세 번째 인자로 추가 제공될 뿐).

## 막혔을 때 다음 체크
- entry point부터 이어지는 전체 흐름을 먼저 정리하고 싶으면 → [REV-0097 ELF Entry Point에서 main까지](./rev-0097-entry-to-main.md)
- `_start` 코드 자체를 명령어 단위로 다시 보고 싶으면 → [REV-0098 _start 함수 읽는 법](./rev-0098-start-function.md)
- main을 못 찾는 상황에 대한 더 넓은 범위의 실전 절차는 → [REV-0009 main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)
- 심볼이 아예 없는 stripped 바이너리 전반의 대응법은 → [REV-0010 stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)

## 미니 예제
```bash
$ nm -D chall | grep libc_start_main
                 U __libc_start_main@GLIBC_2.34

$ objdump -d -M intel chall | grep -B2 'call.*libc_start_main'
    1081:	48 8d 3d c1 00 00 00 	lea    rdi,[rip+0xc1]        # 1149 <main>
    1088:	ff 15 12 2f 00 00    	call   QWORD PTR [rip+0x2f12] # __libc_start_main@GLIBC_2.34
```
`main`(0x1149)이 `rdi`에 로드된 직후 바로 `__libc_start_main`이 호출된다 — glibc 2.34 이상 ABI를 요구하는 동적 링킹 바이너리라는 것과, `main`의 정확한 위치를 동시에 확인했다.

## 관련 글
- [REV-0097 — ELF Entry Point에서 main까지](./rev-0097-entry-to-main.md)
- [REV-0098 — _start 함수 읽는 법](./rev-0098-start-function.md)
- [REV-0009 — main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)
- [REV-0010 — stripped 바이너리에서 시작점 잡는 방법](../triage/rev-0010-stripped-entry-point.md)
- [REV-0093 — nm으로 심볼 찾기](./rev-0093-nm-basics.md)

## 출처/검증
- `__libc_start_main` 전통적 시그니처와 동작: glibc 소스 `csu/libc-start.c`(2.33 이전 계열) 기준 (2026-09-08 검증).
- glibc 2.34 리팩터링(`__libc_start_call_main` 분리): glibc 공식 저장소 커밋 로그 및 NEWS 파일의 "csu" 관련 변경 사항 기준.
- x86-64 SysV 인자 전달 규약: System V AMD64 ABI 문서 기준.
