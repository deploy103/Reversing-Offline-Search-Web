---
id: REV-0461
title: "예외 처리(try/catch)가 어셈블리에 남기는 흔적"
slug: "rev-0461-try-catch-assembly-traces"
category: "assembly"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra, x64dbg, GDB]
keywords:
  - try catch assembly
  - C++ exception assembly
  - zero cost exception
  - 제로 코스트 예외
  - "__cxa_throw"
  - "__cxa_begin_catch"
  - "_CxxThrowException"
  - "__CxxFrameHandler"
  - eh_frame
  - pdata xdata
  - landing pad
  - 랜딩 패드
  - unwind table
aliases:
  - try catch 어셈블리
  - 예외처리 디스어셈블리
  - C++ 예외 바이너리 흔적
  - throw 코드 어디
symptom_keywords:
  - try catch인데 분기가 안보임
  - throw 호출이 어디 있는지 모르겠음
  - 함수가 갑자기 다른 곳으로 실행이 넘어감
  - catch 블록을 못찾겠음
  - pdata xdata가 뭔지 모르겠음
source_ids: ["SRC-INTEL-SDM", "SRC-GENERAL-ASM"]
last_verified: "2026-09-08"
---

## 한 줄 요약
현대 C++ 예외 처리는 "제로 코스트(zero-cost)" 모델을 쓰기 때문에 `try` 블록의 정상 실행 경로에는 추가 명령어가 전혀 없고, 대신 예외가 실제로 던져질 때만 참조되는 별도의 언와인드 테이블(`.pdata`/`.xdata` on PE, `.eh_frame`/`.gcc_except_table` on ELF)과 코드 밖 "랜딩 패드(landing pad)" 블록이 흔적으로 남는다.

## 언제 검색해야 하나
- `try`/`catch`를 쓴 C++ 소스가 있다고 알고 있는데 정작 디스어셈블리에서 눈에 띄는 분기나 표시가 안 보여서 어디가 try 블록인지 못 찾을 때
- `call __cxa_throw`, `call _CxxThrowException`, `call __cxa_begin_catch`처럼 낯선 함수 호출이 보여서 예외 관련 코드인지 확인하고 싶을 때
- IDA/Ghidra가 함수 하나를 이상하게 여러 조각(청크, chunk)으로 쪼개서 보여주거나, 정상적으로는 도달할 수 없어 보이는 코드 블록을 만났을 때
- PE의 `.pdata`/`.xdata`나 ELF의 `.eh_frame`이 뭔지 몰라서 예외/언와인드 정보를 어떻게 읽어야 할지 궁금할 때

## 핵심 개념

### "제로 코스트" 모델이란
과거(및 일부 임베디드/구형 컴파일러)의 예외 처리는 `setjmp`/`longjmp` 스타일로, `try` 블록에 들어갈 때마다 현재 상태(레지스터, 스택 포인터)를 저장하는 코드를 **매번 실행**해야 했다. 반면 현대 GCC/Clang(Itanium C++ ABI)과 MSVC(x64)는 **"예외가 실제로 발생하지 않는 한 아무 비용도 들지 않는다"**는 설계를 쓴다. 이는 곧:
- `try` 블록 진입/이탈 자체에는 **어떤 추가 명령어도 삽입되지 않는다.** try 블록 안의 코드는 try가 아닌 코드와 어셈블리 수준에서 구별할 수 없다.
- 대신 컴파일러는 **함수 코드와 완전히 분리된 별도의 메타데이터 테이블**을 만들어, "이 RIP 범위에서 예외가 발생하면 어느 정리(cleanup)/catch 코드로 가야 하는지, 어떤 로컬 변수의 소멸자를 불러야 하는지"를 기록해둔다.
- 예외가 실제로 `throw`될 때만, 런타임 언와인더(unwinder)가 이 테이블을 찾아 읽고 스택을 거슬러 올라가며(stack unwinding) 해당하는 처리 코드로 점프한다.

### 예외를 던지는 지점의 흔적
`throw` 문이 실제로 실행되는 지점에는 명확한 함수 호출이 남는다.
- **Linux/Itanium ABI (GCC/Clang)**: `__cxa_allocate_exception`으로 예외 객체 메모리를 할당하고, 예외 객체를 생성한 뒤 `__cxa_throw`를 호출한다. `__cxa_throw`는 절대 정상 반환하지 않는(noreturn) 함수다.
- **Windows (MSVC x64)**: `_CxxThrowException`을 호출한다. 역시 noreturn이다.

### catch 블록의 흔적
- **Linux**: 예외를 실제로 처리(catch)하기 시작할 때 `__cxa_begin_catch`를 호출하고, catch 블록이 끝날 때 `__cxa_end_catch`를 호출한다. 재던지기(`throw;`, 인자 없는 rethrow)는 `__cxa_rethrow`, 정리 코드 실행 후 언와인딩을 계속할 때는 `_Unwind_Resume`이 쓰인다.
- **Windows**: `__CxxFrameHandler3`(또는 최신 툴셋에서 `__CxxFrameHandler4`)가 함수의 "personality routine"으로 언와인드 테이블에 등록되어, 언와인더가 예외 타입에 맞는 catch 핸들러를 찾을 때 이 함수를 호출한다.

### 랜딩 패드(Landing Pad)와 코드 배치
`catch` 블록이나 지역 변수의 소멸자를 호출해야 하는 "정리(cleanup)" 코드는 함수의 정상 실행 흐름에서 **직접 분기해 들어오는 경로가 없다** — 오직 언와인더가 테이블을 보고 강제로 그 주소로 실행을 옮겨줄 때만 도달한다. 그래서:
- 컴파일러는 이런 코드를 정상 코드와 분리해 함수 뒤쪽이나 별도의 "cold" 영역에 배치하는 경우가 많다(정상 실행에서 자주 안 타는 코드를 멀리 떨어뜨려 캐시 지역성을 높이는 것과 같은 이유).
- IDA는 이런 "일반적인 제어 흐름 그래프상 진입 간선이 없는" 코드 블록을 함수의 별도 청크(chunk)로 취급하거나, 참조가 안 되는 고아 코드로 표시하기도 한다. Ghidra는 종종 이런 블록을 별도 함수처럼 분리해서 보여주고 이름에 `catch`, `cleanup`, `unwind` 등의 힌트가 자동으로 붙기도 한다(심볼이 남아있는 경우).

### 메타데이터 위치: PE의 .pdata/.xdata, ELF의 .eh_frame
- **PE(Windows x64)**: `.pdata` 섹션에 `RUNTIME_FUNCTION` 배열이 있어 함수의 시작/끝 RVA와 언와인드 정보(`.xdata`에 있는 `UNWIND_INFO`) 위치를 매핑한다. 이 인프라는 SEH(REV-0134 참고)와 C++ 예외가 **공유**한다 — 차이는 personality routine이 SEH용(`_except_handler4` 등)이냐 C++용(`__CxxFrameHandler3/4`)이냐뿐이다.
- **ELF(Linux)**: `.eh_frame` 섹션에 DWARF CFI(Call Frame Information) 형식으로 언와인드 정보가 있고, `.gcc_except_table`에는 어떤 예외 타입을 어느 catch 핸들러로 보낼지의 매핑(LSDA, Language-Specific Data Area)이 들어있다.

### 왜 디컴파일 결과가 "조각나 보이는" 경우가 많은가
try/catch가 많은 C++ 함수를 디컴파일하면, 정상 로직과 무관해 보이는 작은 블록들(각 지역 객체의 소멸자를 호출하는 정리 코드)이 함수 여기저기, 혹은 함수 끝에 뭉쳐서 나타나는 경우가 흔하다. 이는 컴파일러가 "예외 전파 중 스택을 되감으며 살아있던 지역 객체들을 순서대로 정리"해야 하는 각 시점마다 별도의 작은 정리 루틴을 만들어두기 때문이다. 정상 흐름에서 이 블록들로 직접 점프하는 코드가 없으므로, 디컴파일러의 그래프 기반 재구성 로직이 이들을 제대로 함수 본문에 편입시키지 못하고 따로 표시하는 경우가 많다.

## 화면/코드에서 보이는 징후
- `call __cxa_throw`, `call _CxxThrowException`처럼 이후 다시 원래 흐름으로 돌아오지 않는(다음 명령이 `ret`나 다른 함수로 이어지지 않고 뜬금없는) `call`
- `call __cxa_begin_catch` 뒤에 catch 블록 본문, `call __cxa_end_catch`로 마무리되는 패턴
- 함수 정상 흐름 어디서도 점프해 들어오지 않는(참조되는 간선이 없는) 코드 블록의 존재
- PE 바이너리의 `.pdata`/`.xdata` 섹션, ELF 바이너리의 `.eh_frame`/`.gcc_except_table` 섹션이 비어있지 않고 상당한 크기를 차지함
- `noreturn`으로 보이는 `call` 직후에 `ud2`, `int3`처럼 "여기 도달하면 안 됨"을 명시하는 트랩 명령이 놓여있음(컴파일러가 안전장치로 넣는 경우)

## 가장 먼저 할 것
1. 예외 관련 함수 이름(`__cxa_throw`, `_CxxThrowException`, `__cxa_begin_catch`, `__CxxFrameHandler3`)이 Imports/심볼 목록에 있는지 확인한다.
2. 있다면 그 함수들의 xref를 따라가 throw 지점과 catch 진입점을 각각 특정한다.
3. PE라면 `.pdata`, ELF라면 `.eh_frame`을 열어 해당 함수의 언와인드 범위가 등록되어 있는지 확인한다.

## 단계별 절차

**1) throw 지점 찾기 (Linux 예시)**
```asm
lea   rdi, [rip+exc_size]      ; __cxa_allocate_exception 호출 준비 (개념 흐름)
call  __cxa_allocate_exception
; ... 예외 객체 생성자 호출 ...
lea   rdx, [rip+MyException_type_info]
lea   rcx, [rip+MyException_destructor]
call  __cxa_throw                ; 여기서 절대 정상 반환하지 않음
```

**2) catch 진입점 찾기**
```asm
; 예외 타입이 일치해 이 catch로 언와인더가 점프해 들어옴 (정상 흐름 간선 없음)
call  __cxa_begin_catch
; catch 블록 본문
call  __cxa_end_catch
jmp   L_after_try
```

**3) 메타데이터로 함수 범위 확인 (Linux)**
```bash
readelf --debug-dump=frames <binary> | less   # .eh_frame CFI 확인
objdump -h <binary> | grep -E "eh_frame|gcc_except_table"
```

**4) 메타데이터로 함수 범위 확인 (Windows)**
```text
dumpbin /unwindinfo target.exe
```
또는 IDA에서 자동 로드된 Exception Handling 정보를 확인한다(IDA가 PE의 `.pdata`를 인식하면 함수 속성에 예외 처리 관련 표시가 붙는 경우가 있다).

## 명령어/단축키
- IDA: `Alt+T`(텍스트 검색)로 `cxa_throw`, `CxxThrowException` 등 문자열/함수명 검색, `X`(Xrefs to)로 호출 지점 추적
- Ghidra: Symbol Tree에서 `__cxa_*`, `_CxxThrowException` 검색, Function Graph로 정상 흐름에서 분리된 블록(진입 간선 없는 노드) 시각적으로 확인
- Linux: `readelf --debug-dump=frames <binary>`, `objdump --dwarf=frames <binary>`
- Windows: `dumpbin /unwindinfo <binary>`, `dumpbin /headers <binary>`로 `.pdata` 존재 확인

## 출력 해석
- `.eh_frame`/`.pdata`가 비어있거나 매우 작다 → 예외를 쓰지 않는 코드(순수 C, 또는 `-fno-exceptions`로 빌드된 C++)일 가능성이 높다.
- `__cxa_throw`/`_CxxThrowException` xref가 많다 → 예외를 적극적으로 활용하는 코드베이스이며, 각 호출 지점을 에러 처리 로직의 단서로 활용할 수 있다.
- 정상 흐름에서 도달 불가능해 보이는 블록이 함수 끝에 뭉쳐있다 → 대부분 소멸자 정리(cleanup) 코드/catch 핸들러이며, 버그나 데드 코드가 아니다.

## 흔한 실수
- 정상 실행 경로만 훑어보고 "이 함수엔 try/catch가 없다"고 단정하는 것 — 제로 코스트 모델 때문에 try 블록은 정상 경로에서 시각적으로 전혀 티가 안 난다. 반드시 언와인드 메타데이터나 예외 관련 함수 호출 유무로 판단해야 한다.
- 도달 불가능해 보이는 코드 블록을 컴파일러 버그나 죽은 코드(dead code)로 오해해서 무시하는 것 — 대부분 예외 전파 시에만 실행되는 정당한 정리/catch 코드다.
- SEH(REV-0134)와 C++ 예외를 완전히 다른 메커니즘이라고 생각하는 것 — Windows x64에서는 둘 다 같은 `.pdata`/`.xdata` 언와인드 인프라를 공유하며, 차이는 personality routine뿐이다.
- `__cxa_throw`/`_CxxThrowException` 호출 직후에도 다음 명령이 정상적으로 실행될 것이라 가정하는 것 — 이 함수들은 noreturn이므로 그 다음에 오는 코드(있다면)는 대개 컴파일러가 넣은 트랩(`ud2`) 이거나 아예 다른 기본 블록의 시작이다.

## 막혔을 때 다음 체크
- 예외 관련 함수가 스트립되어 이름이 안 보이면 → 문자열 xref로 `.what()`이 반환할 만한 에러 메시지 문자열을 먼저 찾고 거기서 역추적한다.
- `.pdata`/`.eh_frame`을 어떻게 읽는지 막막하면 → REV-0134(SEH 기초)에서 다루는 예외 디렉터리 구조 설명을 먼저 참고한다.
- 안티디버깅 목적의 예외 남용(예외를 던지고 디버거가 멈추는지 관찰)이 의심되면 → REV-0239(Exception 기반 안티디버깅 기초)로 이동한다.

## 미니 예제

**예제 1 — 제로 코스트: try 블록 자체는 평범한 코드**
```cpp
try {
    int x = risky();     // 예외를 던질 수도 있는 함수
    use(x);
} catch (const std::exception& e) {
    handle(e);
}
```
```asm
; try 블록 정상 경로: 특별한 표시 전혀 없음, 그냥 함수 호출 두 개
call  risky
mov   [rbp-4], eax
mov   edi, [rbp-4]
call  use
jmp   L_after_try     ; 예외 없이 끝까지 갔으면 catch를 건너뜀
; --- 여기부터는 정상 흐름에서 절대 도달 안 함(언와인더 전용) ---
L_catch:
    call  __cxa_begin_catch
    ...
    call  handle
    call  __cxa_end_catch
L_after_try:
```

**예제 2 — throw 지점 (Linux)**
```cpp
throw std::runtime_error("bad input");
```
```asm
mov   edi, 32                       ; 예외 객체 크기
call  __cxa_allocate_exception
lea   rsi, [rip+str_bad_input]
mov   rdi, rax
call  std::runtime_error::runtime_error
lea   rdx, [rip+_ZTIN...]           ; typeinfo for std::runtime_error
lea   rcx, [rip+_ZN...D1Ev]         ; 소멸자 포인터
mov   rdi, rax
call  __cxa_throw                    ; noreturn
```

**예제 3 — Windows, `_CxxThrowException`**
```cpp
throw MyError();
```
```asm
lea   rcx, [rbp-0x20]        ; 예외 객체 주소
call  MyError::MyError
lea   rdx, [rip+MyError_ThrowInfo]
lea   rcx, [rbp-0x20]
call  _CxxThrowException      ; noreturn
```

## 관련 글
- REV-0134 — SEH와 예외 기반 제어 흐름 기초
- REV-0239 — Exception 기반 안티디버깅 기초
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0072 — RET: 함수 반환과 스택 변화

## 출처/검증
- Itanium C++ ABI의 제로 코스트 예외 모델과 `__cxa_throw`/`__cxa_begin_catch`/`__cxa_end_catch`: Itanium C++ ABI 공식 문서(C++ ABI Exception Handling) 기준.
- Windows x64 예외 처리(`_CxxThrowException`, `__CxxFrameHandler3/4`, `.pdata`/`.xdata`): Microsoft Learn 공식 문서 "x64 exception handling" 기준.
- Linux `.eh_frame`(DWARF CFI)과 `.gcc_except_table`(LSDA) 구조: DWARF Debugging Information Format 표준 및 GCC 공식 문서(Exception Handling) 기준. (2026-09-08 검증)
