---
id: REV-0952
title: "Obfuscator 흔적으로 원본 언어/컴파일러 추정하기"
slug: "rev-0952-obfuscator-traces-language-compiler-guess"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [DIE, x64dbg]
keywords: ["원본 언어 추정", "컴파일러 추정", "obfuscator 흔적", "런타임 라이브러리 흔적", "MinGW 흔적", "MSVC 흔적", "Delphi 바이너리 특징", "Go 바이너리 특징"]
aliases: ["이 파일 어떤 언어로 짰는지", "컴파일러 특정하는 법", "난독화되어도 언어 알아내는 법", "실행파일 원본 언어 추정"]
symptom_keywords: ["die에서 컴파일러 정보가 안나옴", "난독화때문에 언어를 모르겠음", "strings에 이상한 런타임 심볼이 보임", "함수 이름이 mangled 되어있음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
패킹/난독화가 걸려 있어 DIE의 컴파일러 자동 인식이 실패하더라도, 런타임 라이브러리 특유의 초기화 루틴 패턴, 예외 처리 구조, 문자열 스타일, 심볼 네이밍 규칙 같은 "언패킹 이후에도 남는 간접 단서"들을 조합하면 원본이 C/C++(MSVC/MinGW/GCC), Delphi, Go, Rust 중 어느 쪽으로 컴파일되었는지 상당히 좁혀서 추정할 수 있다.

## 언제 검색해야 하나
- DIE로 컴파일러 자동 인식을 시도했는데 패킹 때문에 `Unknown compiler`만 나올 때
- 언패킹은 끝났지만(REV-0944~0946) 원본이 어떤 언어/컴파일러로 만들어졌는지 알아야 다음 분석 전략(예: C++ vtable 구조 가정, Go의 goroutine 구조 가정)을 세울 수 있을 때
- 함수 이름이 mangled(예: `_Z3fooi`, `?foo@@YAHH@Z`)되어 있어서 C++ 계열임은 알겠는데 정확히 어떤 컴파일러인지 궁금할 때
- CTF 문제 바이너리가 특이하게 생겨서(예: 굉장히 큰 파일 크기에 런타임 관련 심볼이 많음) Go나 Rust로 짜인 것 아닌가 의심될 때

## 핵심 개념

### 왜 원본 언어/컴파일러를 알아야 하는가
원본 언어를 알면 분석 전략이 크게 달라진다. C++로 컴파일된 바이너리는 vtable과 가상 함수 호출 패턴을 예상해야 하고, Go 바이너리는 goroutine 스케줄러와 자체 런타임 문자열 테이블을 예상해야 하며, Delphi 바이너리는 독자적인 문자열 표현 방식(길이 접두 문자열)과 VCL 프레임워크 흔적을 예상해야 한다. 패킹/난독화가 이런 단서 상당수를 지워버리지만, 완전히 지우기는 어렵다 — 언어/런타임 자체의 구조적 특징까지 지우려면 훨씬 정교한 처리가 필요하기 때문이다.

### 언패킹 후에도 남는 단서들

**1) 런타임 초기화 루틴 패턴**
- **MSVC**: `__scrt_common_main`, `_initterm`, `_CRT_INIT` 계열 함수 호출 순서. 언패킹 후 FLIRT 시그니처가 이 함수들을 인식하는 경우가 많다.
- **MinGW/GCC**: `__mingw_CRTStartup`, `_gnu_exception_handler` 같은 이름이나, MSVC와 다른 예외 처리 방식(SEH 대신 GCC 스타일의 언와인딩 테이블).
- **Go**: 실행 파일 크기가 유난히 크고(정적 링크로 런타임 전체 포함), `runtime.morestack`, `runtime.newproc` 같은 문자열이 심볼이 strip되어도 `.rodata`에 경로 문자열(`/usr/local/go/src/runtime/...`) 형태로 남아있는 경우가 흔하다.
- **Rust**: panic 메시지에 `src/main.rs`, `RUST_BACKTRACE` 같은 문자열, 또는 `core::panicking::panic` 관련 심볼.
- **Delphi**: 진입점 근처에 `System_초기화` 관련 특유의 코드 패턴, VCL 관련 클래스명 문자열(`TForm1`, `TApplication` 등)이 자주 남는다.

**2) 예외 처리 구조**
- MSVC C++는 SEH(Structured Exception Handling) 기반 예외 테이블을 쓴다.
- GCC/Clang 계열은 DWARF 기반 언와인딩 정보(`.eh_frame` 유사 구조, PE에서는 `.pdata`/`.xdata`)를 쓰는 경우가 많다.
- 이 차이는 언패킹된 PE의 예외 관련 디렉토리(Exception Directory)나 함수 프롤로그 패턴에서 드러난다.

**3) 심볼 네이밍(Name Mangling) 규칙**
- C++ MSVC: `?funcName@ClassName@@QAEXXZ` 형태의 독자적 mangling
- C++ Itanium ABI(GCC/Clang/MinGW): `_Z3fooi` 형태
- 이 mangling 규칙은 strip되지 않은 심볼이 하나라도 남아있으면(예외 처리 관련 RTTI 정보 등) 바로 컴파일러 계열을 확정해준다.

**4) 문자열 스타일**
- Delphi/Pascal 계열: 문자열 앞에 길이 바이트/워드가 붙는 "길이 접두 문자열(length-prefixed string)" 구조를 쓰는 경우가 있어 일반 널 종단 문자열과 바이트 배치가 다르게 보인다.
- Go: UTF-8 기반이며 문자열이 (포인터, 길이) 구조체 쌍으로 표현되어, 문자열 리터럴 접근 코드에 항상 길이 값이 함께 로드되는 패턴이 보인다.

### 종합 판단 원칙
하나의 단서만으로 확정하지 말고 여러 단서를 겹쳐서 판단한다. 예를 들어 "파일 크기가 크다 + `.rodata`에 `runtime.` 접두 경로 문자열이 있다 + 심볼이 많다"가 함께 나오면 Go로 거의 확정할 수 있지만, 파일 크기만 크다고 Go로 단정하면 안 된다(정적 링크된 C/C++일 수도 있다, REV-0646 참고).

## 화면/코드에서 보이는 징후
- `strings unpacked.exe`에서 `/usr/local/go/src/...` 또는 `GOROOT` 유사 경로 문자열 → Go
- `strings`에서 `panicked at`, `RUST_BACKTRACE`, `src/main.rs` → Rust
- IDA에서 심볼이 `?Method@ClassA@@...` 형태 → MSVC C++
- 심볼이 `_ZN5ClassA6MethodEv` 형태 → GCC/Clang(Itanium ABI) C++
- entry point 근처에 `TObject`, `TForm`, `System.@` 관련 흔적 → Delphi

## 가장 먼저 할 것
언패킹이 끝난 파일에 대해 먼저 `strings unpacked.exe | grep -iE "go/src|rust|panic|delphi|borland"` 같은 간단한 필터링부터 돌려본다. 이 한 줄로 상당수의 경우 언어 계열이 바로 드러난다. 안 나오면 DIE로 재스캔(언패킹 후에는 컴파일러 인식이 성공하는 경우가 많다)하고, 그래도 안 되면 심볼 mangling 패턴을 직접 찾는다.

## 단계별 절차
1. 언패킹된 파일에 DIE를 다시 실행 — 언패킹 전에는 실패했던 컴파일러 인식이 성공하는 경우가 흔함
2. `strings unpacked.exe`로 언어별 특징 문자열(경로, panic 메시지, 프레임워크 클래스명) 검색
3. IDA/Ghidra에서 strip되지 않은 심볼이 있다면 mangling 패턴 확인
4. entry point 근처 초기화 루틴 이름/패턴을 REV-0097~0099(ELF 기준이지만 PE도 유사한 CRT 초기화 개념)과 비교
5. 예외 처리 디렉토리(PE의 `.pdata` 유무)와 구조 확인
6. 여러 단서를 종합해서 언어/컴파일러 계열 결론

## 명령어/단축키
- `strings unpacked.exe | grep -iE "go/src|rust|panic|delphi|borland|mingw"`
- DIE: `File → Open`으로 재스캔, 상단 배너의 Compiler 항목 확인
- IDA: Functions 창에서 mangled 이름 검색, `Demangled name` 옵션 켜기(Options → Demangled names)

## 출력 해석
- DIE가 `Microsoft Visual C++`, `Borland Delphi`, `Go`처럼 구체적인 컴파일러를 표시하면 그대로 신뢰해도 좋다(언패킹 후에는 정확도가 높다).
- mangled 심볼이 하나라도 발견되면 그 mangling 규칙만으로 C++ 컴파일러 계열(MSVC vs GCC/Clang)이 거의 확정된다.
- `runtime.` 접두 문자열이 다수 발견되면 Go로 거의 확정 가능하다 — Go는 정적 링크가 기본이라 런타임 소스 경로 문자열이 바이너리 안에 대량으로 남는다.

## 흔한 실수
- 파일 크기가 크다는 이유만으로 Go/Rust라고 단정하는 것 — 정적 링크된 C/C++(REV-0646)도 크기가 클 수 있다.
- 패킹되어 있다고 해서 언어 추정 자체를 포기하는 것 — 언패킹 후에는 대부분의 단서가 복원된다.
- 하나의 문자열만 보고 확정하는 것 — 여러 단서를 겹쳐서 판단해야 오판을 줄인다.
- C++ mangled 이름을 보고도 demangle하지 않고 그대로 읽으려 시도하는 것 — IDA의 Demangled names 옵션이나 `c++filt`(리눅스/WSL) 같은 도구로 변환해서 읽는 것이 훨씬 빠르다.

## 막혔을 때 다음 체크
- 원본이 .NET일 가능성이 있다면 → REV-0136 .NET EXE인지 Native EXE인지 구분
- 정적 링크 때문에 함수가 너무 많아 헷갈린다면 → REV-0646 정적 링킹된 ELF 분석 접근법(개념은 PE에도 유사하게 적용)
- 언패킹 자체가 아직 안 끝났다면 → REV-0944 OEP 수동 추적 절차 심화
- 패킹/난독화 여부 판단부터 다시 하고 싶다면 → REV-0953 5분 판단 절차

## 미니 예제
```text
$ strings unpacked.exe | grep -i "go/src"
c:/go/src/runtime/proc.go
c:/go/src/runtime/panic.go

$ strings unpacked.exe | grep -i "runtime\."
runtime.morestack
runtime.newproc
runtime.gopanic
```
이 세 가지 단서(Go 소스 경로, `runtime.` 접두 심볼, 비정상적으로 큰 파일 크기)가 함께 나오면 원본이 Go로 컴파일되었다고 높은 확신으로 결론지을 수 있다. 이후 분석에서는 Go 특유의 문자열 표현(포인터+길이 쌍)과 goroutine 스케줄링 구조를 염두에 두고 진행한다.

## 관련 글
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0942 — 상용 프로텍터(VMProtect/Themida)를 만났을 때 현실적인 대응
- REV-0944 — 패킹된 바이너리에서 OEP를 수동으로 추적하는 절차 심화
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0953 — 패킹/난독화 여부를 실전에서 5분 안에 판단하는 절차

## 출처/검증
- Go 바이너리의 정적 링크 특성과 `runtime.` 접두 심볼/소스 경로 잔존 현상은 Go 공식 문서(build 및 런타임 패키지 설명) 및 다수의 공개 Go 바이너리 리버싱 자료에서 공통적으로 확인되는 내용을 기준으로 정리했다.
- MSVC와 Itanium ABI(GCC/Clang)의 C++ 이름 맹글링 규칙 차이는 각 컴파일러 공식 문서(Microsoft C++ ABI 문서, Itanium C++ ABI 명세)를 기준으로 확인했다(2026-09-09 검증).
- Delphi/Pascal의 길이 접두 문자열 구조는 Embarcadero(Delphi) 공식 문서의 문자열 타입 설명을 참고했다.
