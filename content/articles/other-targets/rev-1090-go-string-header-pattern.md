---
id: REV-1090
title: "Go 바이너리의 문자열 구조(길이+포인터) 읽는 법"
slug: "rev-1090-go-string-header-pattern"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA, GDB]
keywords: ["Go 문자열 구조", "Go StringHeader", "Go 바이너리 문자열"]
aliases: ["Go 문자열이 이상하게 보임", "Go 바이너리 string header"]
symptom_keywords: ["Go 바이너리에서 문자열을 못 찾음", "Go 바이너리 strings 결과가 이어붙어 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Go로 컴파일된 바이너리의 문자열은 C의 `char*`처럼 널 종료(null-terminated) 방식이 아니라, 데이터를 가리키는 포인터(`Data`)와 바이트 길이(`Len`)를 한 쌍으로 갖는 `StringHeader{ Data uintptr, Len int }` 구조로 표현되므로, `strings` 명령이나 자동 문자열 인식이 문자열 경계를 실제와 다르게 잡는 경우가 많다.

## 언제 검색해야 하나
- IDA/Ghidra의 문자열 창(Strings window)에 문자열 여러 개가 하나로 이어 붙어 보이거나, 반대로 문자열 중간에서 끊겨 보일 때
- `.rodata`/`.rdata`를 헥스 덤프로 봤는데 문자열 사이에 널 바이트(`00`)가 전혀 없을 때
- 함수 호출 직전에 "포인터로 보이는 값 하나"와 "작은 정수 하나"가 항상 쌍으로 세팅되는 패턴이 반복해서 보일 때
- 이미 Go 바이너리임을 확인했고(REV-1088, 예정) 이제 문자열 인자를 실제로 추적해야 할 때

## 핵심 개념

### C 문자열과의 근본적인 차이
C/C++는 문자열 끝에 `\0` 한 바이트를 두어 길이를 알아내지만(그래서 `strlen`이 필요), Go는 런타임 내부적으로 문자열을 다음과 같은 구조로 다룬다.

```go
// reflect.StringHeader (unsafe 패키지 공식 문서에 정의된 형태)
type StringHeader struct {
    Data uintptr // 문자열 바이트가 실제로 저장된 곳의 주소
    Len  int     // 바이트 길이(문자 수가 아니라 UTF-8 바이트 수)
}
```

`Data`가 가리키는 곳에는 UTF-8로 인코딩된 바이트가 널 종료 없이 그대로 있고, 진짜 길이는 `Len` 필드에만 있다. 즉 문자열 하나를 다루려면 항상 "포인터 + 길이"가 함께 전달되어야 하며, 이 두 값이 함수 인자 두 개, 혹은 구조체 필드 두 개로 짝지어 나타난다.

### 어셈블리에서 실제로 보이는 형태
Go 컴파일러(1.17 이후 amd64)는 함수 인자를 레지스터로 전달하는 방식(register-based ABI)을 쓰므로, 문자열 인자 하나는 보통 인접한 레지스터 두 개(하나는 포인터, 다른 하나는 길이)로 전달된다. 더 오래된 버전이나 스택 전달 방식에서는 스택에 8바이트 포인터 다음 8바이트 길이가 연속으로 쌓인다. IDA/Ghidra 의사코드에서는 이것이 흔히 `char *`와 `int64` 두 개의 별개 파라미터로 보이며, 도구가 자동으로 하나의 "문자열"로 묶어 표시해주지 않는다.

### 짧은 문자열 비교는 StringHeader 없이도 일어난다
Go 리버싱 분석에 따르면, 리터럴 문자열을 로컬 변수와 단순 비교만 하는 경우(예: `if s == "abcd"`) 컴파일러가 굳이 `StringHeader`를 메모리에 만들지 않고, 레지스터에 로드한 값을 즉시 4바이트 리터럴 상수(`CMP EAX, 0x64636261`)와 직접 비교하는 코드를 생성하기도 한다. 이 경우 문자열이 `.rodata`에 아예 나타나지 않고 명령어의 immediate 값 안에 인코딩되어 있으므로, 데이터 섹션만 뒤져서는 찾을 수 없다.

### Go 1.17+ 에서 타입 이름 인코딩도 비슷한 패턴
문자열 자체는 아니지만, Go 1.17 이후 런타임 타입 메타데이터(`_type`)에 붙는 타입 이름은 1바이트 길이 접두사 + 이어지는 바이트로 저장된다(첫 바이트가 `0x0a`이면 다음 10바이트가 이름). `StringHeader`와는 형식이 다르지만 "길이 정보가 먼저 있고 그 뒤에 실제 바이트가 이어진다"는 Go 특유의 패턴이 반복해서 나타난다는 점은 함께 기억해두면 좋다.

## 화면/코드에서 보이는 징후
- `.rodata`를 헥스 에디터로 열었을 때 여러 단어가 공백 없이 바로 붙어 있고(`helloworldfoo...`), 그 사이에 널 바이트가 안 보임
- IDA Strings 창(Shift+F12)에 문자열이 실제 사용 범위보다 훨씬 길게 잡히거나, 반대로 중간에서 잘려 보임
- 디스어셈블리에서 `LEA reg, [rodata_addr]` 바로 다음이나 근처에 `MOV reg2, <작은 정수>` 형태로 길이로 보이는 즉시값이 세팅되는 패턴
- 함수 프로토타입이 `func(s string)` 하나인데 실제 어셈블리/의사코드에서는 파라미터가 2개(주소, 길이)로 보임

## 가장 먼저 할 것
`.rodata`(ELF) 또는 `.rdata`(PE)를 `objdump -s -j .rodata`나 헥스 뷰로 열어 문자열이 널 종료 없이 이어 붙어 있는지 먼저 확인한다. 이어 붙어 있다면 Go의 전형적인 문자열 저장 방식이므로, "이 문자열을 가리키는 포인터가 어디서 로드되는지"를 xref로 따라가 그 직후/직전에 길이 값이 어디서 세팅되는지 찾는 순서로 진행한다.

## 단계별 절차
1. `readelf -S ./chall | grep rodata`로 `.rodata` 섹션의 시작 주소와 크기 확인
2. `objdump -s -j .rodata ./chall | less`로 실제 바이트를 보고 널 바이트 유무 확인
3. IDA/Ghidra에서 문자열처럼 보이는 주소에 커서를 놓고 xref(Ctrl+X 또는 Ghidra의 References)로 이 주소를 참조하는 코드 위치를 찾는다
4. 그 참조 지점 근처에서 포인터 로드(`LEA`) 바로 다음 명령어가 정수 상수를 레지스터/스택에 넣는지 확인 — 그 값이 문자열의 `Len`이다
5. 함수 호출 규약(Go register-based ABI 또는 스택 기반)에 맞춰 어느 레지스터/스택 오프셋이 포인터고 어느 것이 길이인지 짝을 맞춰 정리한다
6. 길이 값과 실제 데이터 바이트 수가 일치하는지 대조해 문자열 경계를 수동으로 확정한다
7. 짧은 문자열 비교의 경우 `.rodata`에 값이 없을 수 있으니, 그럴 땐 `CMP`/`MOV` 명령의 immediate 값을 리틀엔디언으로 해석해 ASCII로 바꿔본다

## 명령어/단축키
```bash
readelf -S ./chall | grep -i rodata
objdump -s -j .rodata ./chall | less
objdump -d ./chall | grep -A2 "lea.*rodata"
```
IDA: 문자열 위치에서 `Ctrl+X`(xref to), Strings 창은 `Shift+F12`.
Ghidra: 문자열 위치에서 우클릭 → References → Show References to Address.

## 출력 해석
- `objdump -s -j .rodata` 출력에서 16진수 옆의 ASCII 표현을 보면 널 바이트(`.`으로 표시)가 문자열 사이에 없다는 것을 바로 확인할 수 있다.
- xref로 찾아간 코드에서 포인터 로드와 길이 세팅이 항상 쌍으로 다닌다는 것을 확인했다면, 그 함수의 다른 문자열 인자도 같은 패턴으로 찾아나갈 수 있다.
- 짧은 문자열 비교에서 나온 `CMP` immediate 값은 리틀엔디언이므로 바이트 순서를 뒤집어서 읽어야 원래 문자열이 나온다(예: `0x64636261` → `abcd`).

## 흔한 실수
- `strings ./chall` 결과만 보고 이게 실제로 코드에서 어떻게 잘려 쓰이는지 확인하지 않고 그대로 믿는 것 — Go 문자열은 널 종료가 아니므로 `strings`가 문자열 경계를 실제와 다르게 이어 붙여 보여줄 수 있다.
- 문자열이 항상 `.rodata`에 있다고 가정하고 짧은 문자열 리터럴 비교(`CMP` immediate로 처리되는 경우)를 놓치는 것.
- 포인터만 보고 길이를 추적하지 않아, 실제로는 문자열의 일부만 쓰이는데 전체를 다 쓰는 것으로 착각하는 것.
- C 리버싱 습관대로 `Data` 포인터를 그대로 `char*`로 캐스팅해서 널 종료를 기대하며 읽다가 다음 문자열까지 이어서 읽어버리는 것.

## 막혔을 때 다음 체크
- Go 바이너리인지 자체가 불확실하면 → REV-1088 Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)
- strip된 바이너리라 함수 이름부터 안 보이면 → REV-1089 Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함) (예정)
- 문자열은 찾았는데 그 문자열이 런타임 내부 함수에서만 쓰이는 것 같으면 → REV-1091 Go 바이너리에서 goroutine/런타임 함수 걸러내기
- Ghidra/IDA 자체가 Go 함수 경계나 인터페이스 호출을 이상하게 분석한다면 → REV-1092 Go 바이너리 디컴파일 시 흔한 어려움과 대응(IDA/Ghidra)

## 미니 예제
```
.rodata:00000000004a1000  68 65 6c 6c 6f 77 6f 72  6c 64 62 61 64 5f 6b 65  hellowor ldbad_ke
.rodata:00000000004a1010  79 00 00 00                                        y...
```
`helloworld`와 `bad_key`가 널 바이트 없이 바로 이어 붙어 있다. 디스어셈블리에서는 다음과 같은 패턴으로 나타난다.

```asm
lea  rax, [rodata_4a1000]   ; Data: "helloworld" 시작 주소
mov  ebx, 0xA               ; Len: 10 (helloworld 길이)
call some_func              ; string 인자 하나가 (rax, rbx) 두 레지스터로 전달됨
```
여기서 `rax`만 보고 "문자열 포인터니까 널 종료까지 읽으면 되겠지"라고 하면 `bad_key`까지 붙여서 읽는 실수를 하게 된다. `ebx`의 값 10이 실제 경계를 알려준다.

## 관련 글
- REV-0094 — strings로 빠르게 단서 찾기
- REV-1091 — Go 바이너리에서 goroutine/런타임 함수 걸러내기
- REV-1092 — Go 바이너리 디컴파일 시 흔한 어려움과 대응(IDA/Ghidra)
- REV-1088 — Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)
- REV-1089 — Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함) (예정)

## 출처/검증
- Go 문자열의 `StringHeader{Data uintptr, Len int}` 구조와 널 미종료 특성: Go 표준 라이브러리 `unsafe`/`reflect` 패키지 공식 문서, PNF Software "Analyzing Golang Executables"(JEB 블로그) 분석 기준.
- 짧은 문자열 리터럴 비교 시 `StringHeader` 없이 `CMP` immediate로 직접 비교되는 패턴: OSIRIS Lab(NYU Tandon) "Reverse Engineering Go, Part I" 분석 기준.
- Go 1.17+ 런타임 타입 이름의 1바이트 길이 접두사 인코딩: 커뮤니티 Go 리버싱 노트(Azhlm, "Reverse Engineering Go Binaries: A Comprehensive Guide to Metadata Analysis") 기준 (2026-09-10 검증).
