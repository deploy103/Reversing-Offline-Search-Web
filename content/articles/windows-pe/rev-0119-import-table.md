---
id: REV-0119
title: "Import Table에서 중요한 API 찾기"
slug: "rev-0119-import-table"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["Import Table", "IMAGE_IMPORT_DESCRIPTOR", "IAT", "INT", "Import Address Table", "Import Name Table", "IMAGE_THUNK_DATA", "IMAGE_IMPORT_BY_NAME", "GetProcAddress"]
aliases: ["임포트 테이블이란", "iat란", "import name table이란", "썽크 구조", "어떤 dll을 쓰는지 확인"]
symptom_keywords: ["프로그램이 어떤 API를 쓰는지 확인하고 싶음", "IAT와 INT 차이를 모름", "썽크가 뭔지 모름", "CreateFile 같은 함수를 어디서 찾는지 모름", "call 명령이 [rip+오프셋]으로 가는 이유를 모름"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Import Table은 "이 프로그램이 어떤 DLL의 어떤 함수를 가져다 쓰는지" 목록을 담은 구조로, `OptionalHeader.DataDirectory[1]`이 가리키는 `IMAGE_IMPORT_DESCRIPTOR` 배열과 그 안의 INT(Import Name Table)/IAT(Import Address Table) 두 쌍둥이 썽크(thunk) 배열을 읽을 줄 알면, 코드를 한 줄도 안 읽고 "이 파일이 파일을 쓰는지, 네트워크를 쓰는지, 레지스트리를 건드리는지" 같은 행위를 헤더만 보고 짐작할 수 있다.

## 언제 검색해야 하나
- 새로운 샘플을 받았을 때 코드 분석 전에 "이 프로그램이 뭘 할 수 있는지" 빠르게 훑어보고 싶을 때(예: `WinExec`, `CreateProcessA`가 보이면 다른 프로세스를 실행할 수 있다는 뜻)
- IDA에서 `call cs:GetProcAddress` 처럼 함수 이름이 이미 붙어서 보이는데, 이게 어디서 온 정보인지 궁금할 때
- `call qword ptr [rip+0x2E45]`처럼 오프셋 기반 간접 호출이 왜 이렇게 컴파일되는지 궁금할 때
- IAT(Import Address Table)와 INT(Import Name Table)의 차이, 그리고 왜 이 둘이 로딩 후 결국 같은 값을 갖게 되는지 궁금할 때
- API 후킹이나 IAT 패치 같은 동적 분석 기법을 배우기 전에 정적 구조부터 이해하고 싶을 때

## 핵심 개념

### Import Table이 필요한 이유
PE 파일은 `printf`, `CreateFileW`, `VirtualAlloc` 같은 함수를 스스로 갖고 있지 않다. 이런 함수는 `msvcrt.dll`, `kernel32.dll` 같은 별도 DLL 안에 들어 있고, 프로그램이 실행될 때 Windows 로더가 필요한 DLL들을 프로세스 주소 공간에 매핑한 뒤, 그 안의 함수들이 **실제로 메모리 어느 주소에 위치하는지** 알아내서 우리 실행 파일이 호출할 수 있도록 연결해줘야 한다. 이 "무엇을, 어디서 가져올지"의 목록이 Import Table이고, "로더가 실제 주소를 채워 넣을 자리"가 IAT(Import Address Table)다.

### 큰 그림: Descriptor → INT/IAT → IMAGE_IMPORT_BY_NAME
```text
OptionalHeader.DataDirectory[1] (RVA, Size)
        │
        ▼
IMAGE_IMPORT_DESCRIPTOR[]  ── DLL 하나당 항목 하나 (배열 끝은 전부 0인 항목으로 표시)
   ├─ kernel32.dll  → OriginalFirstThunk(INT) ─┐   FirstThunk(IAT) ─┐
   ├─ user32.dll    → ...                       │                    │
   └─ (모두 0, 배열 끝)                          ▼                    ▼
                                     IMAGE_THUNK_DATA[]        IMAGE_THUNK_DATA[]
                                     (함수 이름/서수 목록,      (로딩 후 실제 함수
                                      로딩 전후 값 동일)         주소로 덮어써짐)
                                            │
                                            ▼
                                   IMAGE_IMPORT_BY_NAME
                                   { Hint; Name[] }  예: "CreateFileW"
```

### IMAGE_IMPORT_DESCRIPTOR 구조체
```c
typedef struct _IMAGE_IMPORT_DESCRIPTOR {
    union {
        DWORD Characteristics;
        DWORD OriginalFirstThunk;  // ★ INT(Import Name Table)의 RVA
    };
    DWORD TimeDateStamp;           // 바인딩된 경우의 타임스탬프 (보통 0)
    DWORD ForwarderChain;
    DWORD Name;                    // ★ DLL 이름 문자열의 RVA (예: "KERNEL32.dll")
    DWORD FirstThunk;               // ★ IAT(Import Address Table)의 RVA
} IMAGE_IMPORT_DESCRIPTOR;          // 20바이트, DLL 하나당 하나
```

`DataDirectory[1].VirtualAddress`가 가리키는 위치부터 이 구조체가 DLL 개수만큼 연속으로 나열되고, **모든 필드가 0인 항목**이 나오면 배열이 끝났다는 뜻이다(별도의 개수 필드가 없다).

### INT(Import Name Table)와 IAT(Import Address Table): 왜 두 개가 필요한가
`OriginalFirstThunk`와 `FirstThunk`는 각각 다른 배열을 가리키지만, **로딩 전에는 완전히 동일한 내용**을 담고 있다. 두 배열 모두 `IMAGE_THUNK_DATA`(포인터 크기와 같은, 64비트라면 8바이트) 원소들의 배열이며, 각 원소는 함수를 이름으로 가져올지(`IMAGE_IMPORT_BY_NAME` 구조체의 RVA) 서수(ordinal)로 가져올지를 인코딩한다.

- **`OriginalFirstThunk`가 가리키는 배열 = INT** — "무슨 함수를 가져올지"의 원본 목록. 로더가 로딩 후에도 값을 바꾸지 않는다. 즉 파일을 정적으로 분석할 때 함수 이름을 알아내려면 이 배열을 읽으면 된다.
- **`FirstThunk`가 가리키는 배열 = IAT** — 로딩 전에는 INT와 같은 내용(함수 이름을 가리키는 RVA)이지만, **로더가 실제로 각 함수를 로드해서 그 주소를 알아낸 뒤, 이 배열의 각 원소를 "실제 함수의 절대 주소"로 덮어쓴다.** 그래서 프로그램이 실제로 실행될 때 코드에서 `call [FirstThunk가 가리키는 위치]`처럼 IAT를 통해 간접 호출하면, 그 자리에는 이미 실제 함수 주소가 채워져 있어서 바로 그 함수로 점프하게 된다.

즉 INT는 "정적 분석용 이름표", IAT는 "실행 시점에 실제 주소가 채워지는 슬롯"이다. 컴파일러가 만드는 함수 호출 코드는 항상 IAT(`FirstThunk`) 쪽을 참조하도록 되어 있다 — INT는 로더가 어떤 함수를 찾아야 하는지 알려주는 용도로만 쓰이고, 로딩이 끝나면 그 역할이 끝난다.

### 32비트 vs 64비트 IMAGE_THUNK_DATA
```c
// 64비트 (IMAGE_THUNK_DATA64), 원소 크기 8바이트
typedef union _IMAGE_THUNK_DATA64 {
    ULONGLONG ForwarderString;
    ULONGLONG Function;          // IAT에서: 로딩 후 실제 함수 주소
    ULONGLONG Ordinal;           // 최상위 비트(0x8000000000000000) 켜지면 서수 임포트
    ULONGLONG AddressOfData;     // INT에서: IMAGE_IMPORT_BY_NAME의 RVA
} IMAGE_THUNK_DATA64;
```
최상위 비트(`IMAGE_ORDINAL_FLAG64` = `0x8000000000000000`, 32비트는 `IMAGE_ORDINAL_FLAG32` = `0x80000000`)가 켜져 있으면 이 함수는 이름이 아니라 **서수(ordinal, 숫자)**로 임포트된다는 뜻이고, 나머지 하위 비트가 곧 그 서수 값이다. 이 경우 `IMAGE_IMPORT_BY_NAME`을 거치지 않고 바로 서수로 `GetProcAddress`가 호출된 것과 같은 효과를 낸다. 이름이 아니라 서수로만 임포트되는 함수는 정적 분석 도구가 이름을 자동으로 붙여주지 못하는 경우가 있어(대상 DLL의 export ordinal 매핑표가 따로 필요) 분석이 조금 더 까다롭다.

### IMAGE_IMPORT_BY_NAME
서수가 아니라 이름으로 임포트하는 경우, 썽크 값은 이 구조체의 RVA를 가리킨다.
```c
typedef struct _IMAGE_IMPORT_BY_NAME {
    WORD Hint;       // 대상 DLL의 Export Table 내 예상 인덱스(힌트, 없어도 이름으로 재검색 가능)
    BYTE Name[1];    // 널 종료 함수 이름 문자열, 예: "CreateFileW\0"
} IMAGE_IMPORT_BY_NAME;
```
`Hint`는 대상 DLL의 Export Table(REV-0120)에서 이 함수가 몇 번째쯤 있을 것 같다는 힌트일 뿐이고, 로더는 이 힌트가 틀려도 `Name`으로 다시 찾아서 정확한 주소를 알아낸다.

### 코드에서 실제로 보이는 모습
64비트 코드에서 임포트 함수를 호출하는 전형적인 패턴은 다음과 같다.
```asm
call qword ptr [rip+0x2E45]   ; IAT 슬롯을 RIP 상대 주소로 간접 호출
```
IDA는 이 IAT 슬롯이 어떤 임포트 항목을 가리키는지 미리 파싱해뒀기 때문에, 실제로는 다음처럼 사람이 읽기 좋은 형태로 보여준다.
```asm
call cs:CreateFileW
```
겉보기에는 직접 호출처럼 보이지만, 내부적으로는 여전히 IAT를 거치는 간접 호출이다. 이 점을 알아야 "이 CALL이 왜 xref가 `.idata`나 `.rdata` 섹션의 특정 슬롯을 가리키는지" 이해할 수 있다.

## 화면/코드에서 보이는 징후
- PE-bear 좌측 트리의 `Import Directory`를 클릭하면 DLL 이름별로 그룹화된 함수 목록이 보임
- IDA의 Imports 창(`View → Open subviews → Imports`)에 DLL 이름과 함수 이름이 한 줄씩 나열됨
- 디스어셈블리에서 `call cs:함수이름` 또는 `call qword ptr [rip+오프셋]` 형태로 함수 호출이 나타남
- 문자열 뷰나 `.rdata` 섹션 안에서 `KERNEL32.dll`, `CreateFileW`, `VirtualAlloc` 같은 문자열이 보임

## 가장 먼저 할 것
IDA의 Imports 창(또는 PE-bear의 Import Directory)을 열어서 통째로 한 번 훑어본다. `CreateProcess`, `WinExec`, `ShellExecute` 계열이 보이면 다른 프로그램을 실행할 수 있다는 뜻이고, `InternetOpen`, `WinHttp`, `send`/`recv`, `WSAStartup` 계열이 보이면 네트워크 통신을 한다는 뜻이며, `RegOpenKey`, `RegSetValue` 계열이 보이면 레지스트리를 건드린다는 뜻이다. `VirtualAlloc` + `WriteProcessMemory` + `CreateRemoteThread` 조합처럼 특정 함수들이 함께 보이면 프로세스 인젝션 같은 특정 기법의 정황일 수 있다. 이렇게 Import Table만 훑어도 코드를 읽기 전에 "이 프로그램이 대략 뭘 하는지"에 대한 가설을 세울 수 있다.

## 단계별 절차

**1) DataDirectory[1]에서 Import Table 위치 확인**
REV-0116/REV-0118에서 배운 대로 `OptionalHeader.DataDirectory[1].VirtualAddress`(RVA)를 파일 오프셋으로 변환한다.

**2) IMAGE_IMPORT_DESCRIPTOR 배열을 하나씩 읽기**
그 오프셋부터 20바이트씩 구조체를 읽으며, 모든 필드가 0인 항목을 만날 때까지 반복한다. 각 항목의 `Name`(RVA)을 오프셋으로 변환해서 DLL 이름 문자열을 읽는다.

**3) 각 Descriptor의 OriginalFirstThunk(INT)를 따라가서 함수 이름 나열**
`OriginalFirstThunk`가 가리키는 위치부터 `IMAGE_THUNK_DATA` 배열(원소 값이 0이면 끝)을 읽고, 각 원소가 서수 플래그가 꺼져 있으면 그 값(RVA)을 다시 오프셋으로 변환해 `IMAGE_IMPORT_BY_NAME.Name`을 읽는다.

**4) IDA/PE-bear로 같은 내용을 자동으로 확인**
```text
IDA: View → Open subviews → Imports (단축키 대응 메뉴)
PE-bear: 좌측 트리 → Import Directory
```

**5) x64dbg로 실행 중 IAT 슬롯 실제 값 확인**
```text
x64dbg: Memory Map에서 .rdata(또는 .idata) 섹션 찾기 → 해당 IAT 주소로 이동
덤프 창에서 IAT 슬롯 값이 정적 분석 때 봤던 RVA가 아니라 실제 함수의 절대 주소로 바뀌어 있는지 확인
```

## 명령어/단축키
```text
IDA: Imports 창에서 함수 더블클릭 → 그 함수를 참조하는 코드로 xref 이동
PE-bear: 좌측 트리 → Import Directory (DLL/함수 목록을 표로 표시)
x64dbg: Alt+M(Memory Map) → .rdata 영역에서 IAT 슬롯 실시간 값 확인
```

## 출력 해석
- Imports 창에 함수 이름이 정상적으로 나열되면 이름 기반 임포트 — 대부분의 경우
- 함수 이름 대신 `Ordinal#123`처럼 숫자만 보이면 서수 기반 임포트 — 대상 DLL의 export ordinal 표를 별도로 참고해야 실제 함수 이름을 알 수 있다(흔히 `ws2_32.dll`의 일부 함수 등에서 보임)
- Import Table 자체가 텅 비어 있거나(`DataDirectory[1].Size == 0`) 아주 적은 수의 함수(예: `LoadLibraryA`, `GetProcAddress`만)만 있으면, 나머지 함수들을 런타임에 `GetProcAddress`로 동적으로 찾아 쓰는 패턴(패커/난독화에서 흔함)을 의심할 수 있다
- IAT 슬롯을 x64dbg로 실행 중에 확인했을 때 정적 분석 때와 다른(훨씬 큰, 로드된 DLL 범위 안의) 주소가 들어 있으면 정상적으로 바인딩된 것

## 흔한 실수
- INT(`OriginalFirstThunk`)와 IAT(`FirstThunk`)를 같은 것으로 착각하는 것 — 로딩 전에는 내용이 같아 보이지만, 로딩 후 IAT만 실제 주소로 덮어써진다는 점이 핵심 차이다.
- 코드에서 `call cs:함수이름`을 직접 호출로 착각하는 것 — 실제로는 IAT 슬롯을 통한 간접 호출이며, 이 슬롯 자체를 패치하면(IAT Hooking) 호출 대상을 바꿀 수 있다.
- 서수(ordinal) 임포트를 보고 "함수 이름을 알 수 없다"고 포기하는 것 — 대상 DLL의 export ordinal 번호와 이름 매핑표(예: `ws2_32.dll`의 알려진 서수 목록)를 찾아 대조하면 이름을 복원할 수 있다.
- `IMAGE_IMPORT_DESCRIPTOR` 배열이 개수 필드 없이 "모두 0인 항목"으로 끝난다는 걸 모르고 고정된 개수만큼만 읽으려 하는 것.
- 32비트와 64비트에서 `IMAGE_THUNK_DATA`의 크기(4바이트 vs 8바이트)와 서수 플래그 비트 위치가 다르다는 걸 무시하고 같은 코드로 파싱하는 것.

## 막혔을 때 다음 체크
- `DataDirectory[1]`이 정의된 헤더 구조가 헷갈리면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- RVA를 파일 오프셋으로 바꾸는 계산이 필요하면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- 반대로 이 파일이 다른 프로그램에 제공하는 함수(Export)가 궁금하면 → [REV-0120 Export Table과 DLL 함수](./rev-0120-export-table.md)
- 임포트된 함수가 실제로 호출되는 지점(진입점→main 흐름)이 궁금하면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)

## 미니 예제
`DataDirectory[1]`을 따라가서 첫 번째 `IMAGE_IMPORT_DESCRIPTOR`를 읽었더니 다음과 같았다고 하자.

```text
IMAGE_IMPORT_DESCRIPTOR[0]:
  OriginalFirstThunk = 0x2A100  (INT)
  Name               = 0x2A5C0  → "KERNEL32.dll"
  FirstThunk         = 0x2C000  (IAT)

INT(0x2A100)를 따라가서 읽은 IMAGE_THUNK_DATA 배열:
  [0] → AddressOfData = 0x2A610 → IMAGE_IMPORT_BY_NAME.Name = "CreateFileW"
  [1] → AddressOfData = 0x2A628 → IMAGE_IMPORT_BY_NAME.Name = "ReadFile"
  [2] → AddressOfData = 0x2A63C → IMAGE_IMPORT_BY_NAME.Name = "CloseHandle"
  [3] → 0 (배열 끝)
```

정적 분석 시점의 IAT(`0x2C000`이 가리키는 배열)도 이 시점에는 INT와 완전히 같은 값(같은 RVA들)을 갖고 있지만, 프로그램이 실행되어 `kernel32.dll`이 로드되고 나면 이 세 슬롯은 각각 `CreateFileW`, `ReadFile`, `CloseHandle`의 **실제 메모리 주소**로 덮어써진다. 코드에서 이 파일을 읽는 함수는 `call qword ptr [rip + (0x2C000 - 현재RIP+ImageBase 등 재계산된 오프셋)]` 형태로 컴파일되어 있고, IDA는 이걸 `call cs:CreateFileW`처럼 사람이 읽기 좋게 보여준다.

## 관련 글
- REV-0120 — Export Table과 DLL 함수
- REV-0118 — RVA VA Raw Offset 계산
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0114 — PE 파일 구조 한 번에 보기

## 출처/검증
- `IMAGE_IMPORT_DESCRIPTOR`, `IMAGE_THUNK_DATA`, `IMAGE_IMPORT_BY_NAME` 구조체 정의 및 INT/IAT 관계: Microsoft Learn "PE Format" 공식 문서, "The .idata Section" 절 기준 (2026-09-08 검증).
- 서수 임포트 플래그(`IMAGE_ORDINAL_FLAG32`/`64`) 정의: Microsoft Learn "PE Format" 문서 및 `winnt.h` 정의 기준.
- IAT를 통한 간접 호출 컴파일 패턴: 다수 리버싱 실무 참고자료 및 IDA 디스어셈블리 관찰 결과에 기반한 일반화 설명.
