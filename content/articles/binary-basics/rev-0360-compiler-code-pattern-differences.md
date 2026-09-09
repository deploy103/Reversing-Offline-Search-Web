---
id: REV-0360
title: "컴파일러별(MSVC/GCC/Clang) 코드 패턴 차이 기초"
slug: "rev-0360-compiler-code-pattern-differences"
category: "binary-basics"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, GDB, x64dbg]
keywords: ["MSVC", "GCC", "Clang", "컴파일러 코드 패턴", "컴파일러 지문", "compiler fingerprint", "함수 프롤로그 차이", "security cookie", "stack protector"]
aliases: ["MSVC GCC Clang 차이가 뭔가요", "어떤 컴파일러로 만들었는지 어떻게 아나요", "컴파일러마다 코드가 왜 다르게 나오나요", "컴파일러 식별하는 법"]
symptom_keywords: ["함수 프롤로그 패턴이 낯설어서 어느 컴파일러인지 모르겠음", "security cookie 코드가 나오는데 스택 카나리랑 뭐가 다른지 모르겠음", "이 바이너리가 MSVC로 만든건지 GCC로 만든건지 모르겠음", "같은 로직인데 IDA에서 함수 시작 모양이 매번 다르게 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
MSVC, GCC, Clang은 모두 C/C++ 표준을 따르지만 각자 다른 코드 생성기(codegen)를 갖고 있어서, 같은 소스 코드라도 함수 프롤로그 모양, 스택 보호 방식, 예외 처리 코드, 심볼 네이밍(mangling), 특정 라이브러리 함수 사용 여부 등이 컴파일러마다 다르게 나타나며, 이 차이를 알아두면 낯선 바이너리를 처음 열었을 때 "어떤 도구로 만들어졌는가"를 빠르게 짐작할 수 있다.

## 언제 검색해야 하나
- 처음 보는 바이너리의 함수 프롤로그 모양이 지금까지 봐온 패턴과 달라서 "이게 어떤 컴파일러 결과물인가" 궁금할 때
- 스택 카나리(보호 쿠키) 관련 코드가 나왔는데 `__security_cookie`인지 `__stack_chk_guard`인지에 따라 분석 접근법이 달라지는 이유가 궁금할 때
- C++ 함수 이름이 `?func@@YAHH@Z` 같은 이상한 형태(MSVC 네임 맹글링)이거나 `_Z4funci` 같은 형태(Itanium ABI, GCC/Clang)인 것을 보고 어느 쪽인지 구분하고 싶을 때
- Windows에서 뽑힌 바이너리인데 특이하게 `_start`가 있거나, Linux ELF인데 MSVC 특유의 패턴이 보여서 헷갈릴 때(크로스 컴파일, MinGW 등 예외 케이스 확인)
- CTF 문제 바이너리를 열었을 때 어느 컴파일러/버전으로 빌드했는지 짐작해서 로컬 환경을 맞추고 싶을 때

## 핵심 개념

### 왜 컴파일러마다 코드가 달라지는가
C/C++ 표준은 "무엇을 계산해야 하는가"(동작)만 규정하고, "어떻게 어셈블리로 표현하는가"는 전혀 규정하지 않는다. MSVC(Microsoft Visual C++), GCC(GNU Compiler Collection), Clang(LLVM 기반)은 각각 독립적으로 개발된 코드 생성기를 갖고 있어서, 같은 최적화 목표(속도, 크기)를 추구하더라도 세부 구현이 다르다. 이 차이는 리버싱에서 "지문(fingerprint)"처럼 활용된다 — 특정 패턴을 보면 어느 컴파일러/버전으로 만들어졌는지 짐작할 수 있고, 이는 곧 어떤 라이브러리 시그니처(REV-0646의 FLIRT/Function ID 등)를 적용할지 결정하는 데 도움이 된다.

### 1) 함수 프롤로그 모양의 차이
```c
int add(int a, int b) { return a + b; }
```

**MSVC (x64, `/Od`)** — 인자를 항상 스택에 저장하는 습관이 강함:
```asm
add proc near
    mov     [rsp+8], ecx     ; shadow space에 인자 저장(REV-0124)
    mov     [rsp+10h], edx
    mov     eax, [rsp+8]
    add     eax, [rsp+10h]
    ret
add endp
```

**GCC (x64 SysV, `-O0`)** — RBP 기반 프레임을 명시적으로 만드는 경향:
```asm
add:
    push    rbp
    mov     rbp, rsp
    mov     [rbp-4], edi
    mov     [rbp-8], esi
    mov     eax, [rbp-4]
    add     eax, [rbp-8]
    pop     rbp
    ret
```

**Clang (x64 SysV, `-O0`)** — GCC와 유사하지만 스택 슬롯 배치나 레지스터 선택이 미묘하게 다를 때가 많고, 종종 더 적은 중간 저장으로 정리된 코드를 냄. 최적화(`-O2`)를 켰을 때 GCC보다 더 공격적으로 벡터화/인라이닝하는 경향이 있다고 알려져 있다.

### 2) 스택 보호(카나리) 구현 차이
스택 버퍼 오버플로우 방어 코드가 있다면, 어떤 심볼/함수를 쓰는지로 컴파일러를 구분할 수 있다.
- **MSVC**: `__security_cookie` 전역 변수와 `__security_check_cookie` 함수를 사용. `/GS` 옵션으로 활성화되며, 프롤로그에서 `mov rax, [__security_cookie]` 후 `xor rax, rbp`(또는 스택 위치)로 섞고, 에필로그에서 `call __security_check_cookie`로 검증한다.
- **GCC/Clang**: `__stack_chk_guard` 전역 변수와 `__stack_chk_fail` 함수를 사용. `-fstack-protector`(또는 `-fstack-protector-all`, `-fstack-protector-strong`) 옵션으로 활성화되며, 검증 실패 시 `call __stack_chk_fail`로 바로 점프한다.

두 방식은 목적(스택 카나리)은 같지만 심볼 이름과 세부 구현이 명확히 달라서, 어느 심볼이 보이는지만으로 컴파일러 계열을 즉시 구분할 수 있다.

### 3) C++ 이름 맹글링(Name Mangling) 방식 차이
C++ 함수는 오버로딩 때문에 이름만으로는 어떤 함수인지 구분이 안 되어, 컴파일러가 인자 타입 정보를 포함한 "맹글된" 이름을 심볼 테이블에 남긴다.
- **MSVC**: `?add@@YAHHH@Z` 형태(고유한 MSVC 맹글링 규칙).
- **GCC/Clang**: `_Z3addii` 형태(Itanium C++ ABI 표준을 따름 — 그래서 GCC와 Clang의 맹글링 결과는 거의 동일하다).

이 차이는 GCC와 Clang을 구분하는 데는 큰 도움이 안 되지만(둘 다 Itanium ABI를 따름), MSVC와 GCC/Clang 계열을 즉시 구분하는 가장 확실한 신호 중 하나다.

### 4) 예외 처리 메커니즘의 차이
- **Windows/MSVC**: SEH(Structured Exception Handling)와 `.pdata`/`.xdata` 섹션 기반의 테이블 주도 예외 처리(x64)를 사용한다.
- **Linux/GCC·Clang**: DWARF 기반 `.eh_frame` 섹션을 사용한 예외 처리(Itanium C++ ABI의 zero-cost exception handling)를 사용한다.

이는 플랫폼(PE vs ELF) 차이에 가깝지만, MinGW(Windows에서 GCC 사용)처럼 플랫폼과 컴파일러 계열이 어긋나는 예외적인 조합도 있으므로, 섹션 이름과 심볼 이름을 함께 봐야 정확하다.

### 5) 라이브러리 함수 사용 패턴 차이
- MSVC는 자체 CRT(`msvcrt.dll`, `ucrtbase.dll`, 또는 정적 링크된 CRT)를 사용하며, `_initterm`, `__scrt_common_main_seh` 같은 MSVC 고유의 초기화 함수들이 진입점 근처에 나타난다.
- GCC/Clang(Linux)은 glibc(또는 musl)를 쓰며, `__libc_start_main`, `__libc_csu_init` 같은 함수가 나타난다(REV-0097, REV-0099 참고).
- 짧은 문자열 복사/비교(`strlen`, `memcpy`)에 대해 각 컴파일러/라이브러리가 서로 다른 인라인 SIMD 패턴을 쓰는 경우가 많아(REV-0448 등), 이 역시 컴파일러 식별에 참고가 된다.

## 화면/코드에서 보이는 징후
- 함수 프롤로그가 인자를 스택에 습관적으로 먼저 저장하는 모양(MSVC 계열 경향) vs RBP 기반 프레임을 먼저 세우는 모양(GCC/Clang 계열 경향)
- `__security_cookie`/`__security_check_cookie`(MSVC) vs `__stack_chk_guard`/`__stack_chk_fail`(GCC/Clang) 심볼의 존재
- C++ 심볼이 `?`로 시작(MSVC) vs `_Z`로 시작(Itanium ABI, GCC/Clang)
- `.pdata`/`.xdata` 섹션(PE, MSVC SEH) vs `.eh_frame` 섹션(ELF, GCC/Clang DWARF 예외 처리)
- `__libc_start_main`(glibc, Linux) vs `__scrt_common_main_seh`(MSVC CRT, Windows) 같은 진입점 근처 초기화 함수

## 가장 먼저 할 것
낯선 바이너리를 열면 먼저 `strings`(또는 IDA/Ghidra 문자열 창)로 컴파일러/링커가 남긴 흔적(예: "Microsoft (R) C/C++", "GCC:", "clang version")을 찾아보고, 없다면 스택 카나리 관련 심볼(`__security_cookie` vs `__stack_chk_guard`)이나 C++ 맹글링 스타일(`?` vs `_Z`)을 확인해서 컴파일러 계열을 짐작한다.

## 단계별 절차

**1) 파일 포맷과 헤더 메타데이터 확인**

PE라면 Rich Header(REV-0558)에서 정확한 MSVC 툴셋 버전까지 추출할 수 있고, ELF라면 `.comment` 섹션에 GCC/Clang 버전 문자열이 남아있는 경우가 많다(`readelf -p .comment ./bin`).

**2) 스택 보호 심볼로 계열 구분**

`__security_check_cookie`가 있으면 MSVC, `__stack_chk_fail`이 있으면 GCC/Clang 계열이다.

**3) C++ 심볼 맹글링 스타일 확인**

C++ 바이너리라면 심볼이 `?`로 시작하는지 `_Z`로 시작하는지 봐서 MSVC와 Itanium ABI(GCC/Clang) 계열을 구분한다.

**4) 함수 프롤로그의 습관적 패턴 비교**

작은 leaf 함수 여러 개를 훑어보며, 인자를 곧바로 스택에 저장하는 습관(REV-0450에서 다룬 shadow space 스타일)이 두드러지는지, RBP 프레임을 먼저 세우는 습관이 두드러지는지 관찰한다.

**5) GCC와 Clang 세부 구분이 필요하면 `.comment` 섹션/최적화 스타일 참고**

GCC와 Clang은 Itanium ABI를 공유해서 위 3단계까지는 잘 구분이 안 될 수 있다. `.comment` 섹션에 명시적인 버전 문자열이 남아있는지 먼저 확인하고, 없다면 벡터화/인라이닝 스타일의 미묘한 차이(예: Clang이 특정 루프를 더 적극적으로 벡터화)로 추정 수준의 판단만 가능하다.

## 명령어/단축키
```bash
# ELF에서 컴파일러 흔적 찾기
readelf -p .comment ./bin
strings ./bin | grep -iE "gcc|clang|LLVM"
nm ./bin | grep -E "__stack_chk_fail|__libc_start_main"

# PE에서 컴파일러 흔적 찾기 (예: 오프라인 도구 사용)
# Rich Header 파싱 도구, 또는 IDA에서 자동 표시되는 Rich Header 정보 확인
strings ./bin.exe | findstr /I "Microsoft Visual"
```
IDA: Imports 창에서 `__security_check_cookie` 또는 `__stack_chk_fail` 검색. Ghidra: Symbol Table에서 동일 검색.

## 출력 해석
- `__stack_chk_fail`과 `__security_check_cookie`가 둘 다 없다면 스택 보호가 비활성화된 빌드이거나, 라이브러리가 정적으로 링크되어 관련 코드가 인라인/최적화되어 심볼이 사라졌을 수 있다.
- `.comment` 섹션에서 GCC 버전 문자열이 나오면 정확한 GCC 버전까지 확인 가능하며, 이는 특정 버전에서만 나타나는 최적화 버그나 코드 패턴을 조사할 때 유용하다.
- Rich Header(MSVC, REV-0558)에서 추출한 툴셋 버전은 실제 컴파일에 사용된 Visual Studio 버전과 빌드 도구 조합까지 알려줄 수 있어 MSVC 식별에서 가장 신뢰도가 높다.

## 흔한 실수
- 함수 프롤로그 모양만 보고 100% 확신하는 것 — 최적화 레벨(`-O0` vs `-O2`)에 따라 같은 컴파일러도 완전히 다른 프롤로그를 낼 수 있으므로, 프롤로그 하나만으로 단정하지 말고 스택 카나리 심볼, 맹글링, 섹션 이름 등 여러 신호를 종합해야 한다.
- Windows PE인데 무조건 MSVC라고 가정하는 것 — MinGW(Windows용 GCC), Clang-cl(Windows용 Clang 드라이버) 등으로도 PE가 생성될 수 있어, 심볼과 예외 처리 방식을 반드시 함께 확인해야 한다.
- GCC와 Clang을 프롤로그 모양만으로 확실히 구분하려는 것 — 둘 다 Itanium ABI와 유사한 코드 생성 철학을 공유해서 겉모습이 매우 비슷할 때가 많다. `.comment` 섹션이나 버전 문자열 없이는 정확히 구분하기 어려울 수 있다는 점을 인정해야 한다.
- 스택 카나리가 없다고 해서 "MSVC/GCC가 아니다"라고 판단하는 것 — 단순히 그 옵션(`/GS-`, `-fno-stack-protector`)이 꺼진 빌드일 뿐이다.

## 막혔을 때 다음 체크
- MSVC의 Rich Header에서 정확한 툴셋 버전을 뽑는 구체적 방법이 궁금하면 → REV-0558 Rich Header에서 컴파일러 정보 추출하기
- Debug/Release 빌드 차이가 컴파일러 식별과 겹쳐서 헷갈리면 → REV-0361 Debug 빌드와 Release 빌드의 어셈블리 차이
- Windows x64/Linux x64 호출 규약 자체의 차이가 궁금하면 → REV-0122 Microsoft x64 Calling Convention / REV-0106 SysV AMD64 Calling Convention
- 함수 인자를 스택에 저장하는 MSVC 특유의 습관(shadow space)이 궁금하면 → REV-0124 Shadow Space가 무엇인지
- 정적 링킹되어 라이브러리 심볼조차 안 보이는 경우의 대처법이 궁금하면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
같은 함수를 MSVC와 GCC로 각각 최적화 없이 컴파일했을 때 스택 보호 코드가 어떻게 다르게 나오는지 비교해보자.

```c
void copy_input(char *dst, const char *src) {
    char buf[16];
    strcpy(buf, src);
    strcpy(dst, buf);
}
```

**MSVC(`/GS`, 기본 활성화) 개념적 결과**
```asm
copy_input proc near
    sub     rsp, 38h
    mov     rax, [__security_cookie]
    xor     rax, rsp              ; 쿠키를 스택 위치와 섞어서 저장
    mov     [rsp+28h], rax
    ; ... strcpy 호출들 ...
    mov     rcx, [rsp+28h]
    xor     rcx, rsp
    call    __security_check_cookie   ; 검증
    add     rsp, 38h
    ret
copy_input endp
```

**GCC(`-fstack-protector`, 기본 활성화) 개념적 결과**
```asm
copy_input:
    push    rbp
    mov     rbp, rsp
    sub     rsp, 0x30
    mov     rax, fs:0x28            ; TLS를 통해 __stack_chk_guard 접근(리눅스 특유)
    mov     [rbp-8], rax
    ; ... strcpy 호출들 ...
    mov     rax, [rbp-8]
    xor     rax, fs:0x28
    je      .ok
    call    __stack_chk_fail
.ok:
    leave
    ret
```

두 코드 모두 "카나리 값을 저장했다가 함수 끝에서 검증한다"는 동일한 목적을 갖지만, MSVC는 전역 변수 `__security_cookie`를 직접 읽고 `__security_check_cookie` 함수 호출로 검증하는 반면, GCC는 리눅스 TLS(Thread Local Storage) 세그먼트(`fs:0x28`)를 통해 카나리에 접근하고 실패 시 `__stack_chk_fail`을 직접 호출한다는 점에서 뚜렷이 구분된다.

## 관련 글
- REV-0558 — Rich Header에서 컴파일러 정보 추출하기
- REV-0361 — Debug 빌드와 Release 빌드의 어셈블리 차이
- REV-0122 — Microsoft x64 Calling Convention
- REV-0106 — SysV AMD64 Calling Convention
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법

## 출처/검증
- MSVC `/GS` 스택 보호(`__security_cookie`, `__security_check_cookie`)와 GCC/Clang `-fstack-protector`(`__stack_chk_guard`, `__stack_chk_fail`)의 구현 차이: Microsoft Learn "Security Features in the CRT"/"/GS" 공식 문서 및 GCC 공식 문서 `-fstack-protector` 옵션 설명 기준.
- C++ 이름 맹글링 규칙(Itanium C++ ABI vs MSVC): Itanium C++ ABI 공식 스펙 문서 및 이를 채택한 GCC/Clang 공식 문서 기준.
- 예외 처리 메커니즘 차이(SEH/`.pdata` vs DWARF/`.eh_frame`): Microsoft Learn "x64 exception handling" 공식 문서 및 DWARF 표준 문서 기준 (2026-09-09 검증).
