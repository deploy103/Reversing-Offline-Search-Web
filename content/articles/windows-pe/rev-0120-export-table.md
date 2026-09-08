---
id: REV-0120
title: "Export Table과 DLL 함수"
slug: "rev-0120-export-table"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["Export Table", "IMAGE_EXPORT_DIRECTORY", "AddressOfFunctions", "AddressOfNames", "AddressOfNameOrdinals", "ordinal export", "DLL exports"]
aliases: ["익스포트 테이블이란", "dll이 제공하는 함수 확인", "AddressOfNames란", "서수 익스포트란", "DllMain 찾는법"]
symptom_keywords: ["dll이 어떤 함수를 제공하는지 확인하고 싶음", "AddressOfNames AddressOfFunctions 차이를 모름", "서수로만 익스포트된 함수 이름을 못찾음", "rundll32로 실행할 함수를 찾고 싶음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Export Table은 DLL(또는 드물게 EXE)이 "다른 프로그램에게 제공하는 함수 목록"을 담은 구조로, `OptionalHeader.DataDirectory[0]`이 가리키는 단 하나의 `IMAGE_EXPORT_DIRECTORY`와 그 안의 세 병렬 배열(`AddressOfFunctions`, `AddressOfNames`, `AddressOfNameOrdinals`)을 읽으면 `GetProcAddress`가 내부적으로 어떻게 함수를 찾아내는지, 그리고 이름 없이 서수만으로 익스포트된 함수를 어떻게 다뤄야 하는지까지 이해할 수 있다.

## 언제 검색해야 하나
- DLL 하나를 분석하면서 "이 DLL이 외부에 어떤 함수를 제공하는지" 전체 목록을 뽑고 싶을 때
- `rundll32.exe 어떤.dll,함수이름` 형태로 DLL의 특정 함수를 직접 실행해보고 싶은데 함수 이름을 몰라서 Export Table을 확인해야 할 때
- Import Table(REV-0119)의 `Hint` 필드가 대상 DLL의 어떤 정보를 가리키는지 이해하려면 Export Table의 이름 순서 개념이 먼저 필요할 때
- `AddressOfFunctions`, `AddressOfNames`, `AddressOfNameOrdinals` 세 배열이 왜 따로따로 있는지, 어떻게 서로 연결되는지 헷갈릴 때
- Export by ordinal(이름 없이 숫자로만 제공되는 함수)을 만났을 때 어떻게 다뤄야 할지 궁금할 때

## 핵심 개념

### Export Table이 하는 일
Windows API를 어떻게 호출할 수 있는지 생각해보면, 프로그램은 `kernel32.dll`에 있는 `CreateFileW`라는 함수의 **이름**만 알고 있고, 실제로 그 함수가 메모리 몇 번지에 있는지는 DLL이 로드될 때까지 알 수 없다. 이 간극을 메우는 함수가 `GetProcAddress(모듈핸들, "함수이름")`이고, 이 함수가 내부적으로 참조하는 데이터가 바로 대상 DLL의 **Export Table**이다. Export Table은 "이 DLL 안에서 이 이름의 함수는 이 RVA에 있다"는 매핑표를 제공한다.

### IMAGE_EXPORT_DIRECTORY 구조체
Import Table과 달리 Export Table은 DLL 하나에 이 구조체가 **딱 하나만** 존재한다(`OptionalHeader.DataDirectory[0]`이 가리키는 위치에 바로 이 구조체 하나가 있다).

```c
typedef struct _IMAGE_EXPORT_DIRECTORY {
    DWORD Characteristics;
    DWORD TimeDateStamp;
    WORD  MajorVersion;
    WORD  MinorVersion;
    DWORD Name;                 // DLL 자신의 이름 문자열 RVA (예: "MYLIB.dll")
    DWORD Base;                 // ★ 서수(ordinal)의 시작 기준값 (보통 1)
    DWORD NumberOfFunctions;    // ★ AddressOfFunctions 배열의 원소 개수
    DWORD NumberOfNames;        // ★ AddressOfNames 배열의 원소 개수 (이름 있는 함수 수)
    DWORD AddressOfFunctions;   // ★ 함수 주소(RVA) 배열의 RVA
    DWORD AddressOfNames;       // ★ 함수 이름 문자열 RVA 배열의 RVA
    DWORD AddressOfNameOrdinals;// ★ 이름→서수 인덱스 매핑 배열의 RVA
} IMAGE_EXPORT_DIRECTORY;
```

`NumberOfFunctions`와 `NumberOfNames`가 다를 수 있다는 점이 핵심이다 — **모든 함수가 이름을 갖는 건 아니다.** 이름 없이 서수로만 제공되는(export by ordinal) 함수가 있으면 `NumberOfFunctions > NumberOfNames`가 된다.

### 세 배열이 서로 연결되는 방식
```text
AddressOfNames[i]         ──► 함수 이름 문자열 (예: "MyExportedFunc")
AddressOfNameOrdinals[i]  ──► i번째 이름에 대응하는 "배열 인덱스" (서수 자체가 아니라 인덱스!)
AddressOfFunctions[j]     ──► 실제 함수 코드의 RVA
```
이름으로 함수를 찾는 절차는 항상 다음 순서를 따른다.

1. `AddressOfNames` 배열을 순회하며(이 배열은 문자열 사전순으로 정렬되어 있어서 이진 탐색이 가능하다) 원하는 이름과 일치하는 인덱스 `i`를 찾는다.
2. `AddressOfNameOrdinals[i]`를 읽어서 인덱스 `j`를 얻는다. (참고: 이 배열이 담고 있는 건 "서수 그 자체"가 아니라 `AddressOfFunctions` 배열에 대한 **0부터 시작하는 인덱스**다. 실제 서수 값을 원한다면 여기에 `Base`를 더해야 한다.)
3. `AddressOfFunctions[j]`를 읽으면 그 함수의 실제 RVA가 나온다.

이 세 단계를 그대로 코드로 구현한 것이 바로 `GetProcAddress(hModule, "함수이름")`의 내부 동작이다.

### 서수(Ordinal)로만 익스포트된 함수
`AddressOfNames`/`AddressOfNameOrdinals` 배열에 등록되지 않고 `AddressOfFunctions` 배열에만 존재하는 함수는 **이름이 없다.** 이런 함수는 `GetProcAddress(hModule, MAKEINTRESOURCE(서수))`처럼 문자열이 아니라 정수 서수로만 호출할 수 있다. 실제 서수 값은 `Base + (AddressOfFunctions 배열에서의 인덱스)`로 계산된다. 오래된 DLL이나 C++ 클래스 기반 라이브러리, 혹은 의도적으로 이름을 숨기려는 경우 이런 익스포트가 자주 보인다. 예를 들어 잘 알려진 예로 `ws2_32.dll`의 일부 초기 버전 함수들이 서수로만 제공된 사례가 있다.

### Forwarder(전달자) Export
Export Table에는 한 가지 특수 케이스가 더 있다. `AddressOfFunctions[j]`가 가리키는 RVA가 **자기 자신의 Export Table 범위(`DataDirectory[0].VirtualAddress` ~ `+ Size`) 안에 들어 있으면**, 그 위치는 실제 함수 코드가 아니라 `"다른DLL.함수이름"` 형태의 문자열이다. 이는 "이 함수는 사실 다른 DLL의 함수를 그대로 전달(forward)한다"는 뜻이다. 예를 들어 `kernel32.dll`의 일부 함수가 실제로는 `KernelBase.dll`의 함수를 그대로 전달하는 식으로 최신 Windows에서 흔히 나타난다. 이 경우 최종 실행 코드를 찾으려면 forwarder 문자열이 가리키는 진짜 DLL/함수까지 한 번 더 따라가야 한다.

### DllMain은 Export Table에 없다
많은 사람이 헷갈리는 부분인데, DLL의 초기화 함수인 `DllMain`은 **Export Table에 등록되지 않는 특수한 진입점**이다. `DllMain`의 주소는 Export Table이 아니라 `OptionalHeader.AddressOfEntryPoint`(REV-0116, REV-0121 참고)에 저장되며, 로더가 DLL을 매핑할 때 자동으로 호출한다. Export Table은 어디까지나 "다른 모듈이 이름/서수로 명시적으로 찾아 쓸 수 있는 함수" 목록이고, `DllMain`은 로더가 알아서 부르는 별도 메커니즘이다.

## 화면/코드에서 보이는 징후
- PE-bear 좌측 트리의 `Export Directory`를 클릭하면 함수 이름/서수/RVA 표가 보임
- IDA의 Exports 창(`View → Open subviews → Exports`)에 함수 이름과 서수(`Ordinal`) 컬럼이 함께 나열됨
- 일반 EXE 파일을 열었을 때 `DataDirectory[0].VirtualAddress == 0`이라 Export Directory 자체가 비어 있음 — 대부분의 EXE는 다른 프로그램에 함수를 제공하지 않기 때문에 정상
- Exports 창에서 함수 이름 대신 `Ordinal12`처럼 숫자만 보이는 항목들이 섞여 있음

## 가장 먼저 할 것
분석 대상이 EXE가 아니라 DLL이라면 먼저 Export 목록부터 훑어서 이 DLL의 "공개 API 표면"을 파악한다. 함수 이름이 `Install`, `Uninstall`, `ServiceMain`처럼 특정 목적을 암시하면 이 DLL이 서비스용인지, 플러그인용인지 짐작할 수 있다. 이름 없는 서수 익스포트가 많다면 C++ 내부 구현 세부사항을 감춘 라이브러리이거나, 리버스 엔지니어링을 어렵게 하려는 의도가 섞여 있을 수 있다는 점도 함께 염두에 둔다.

## 단계별 절차

**1) DataDirectory[0]에서 Export Table 위치 확인**
REV-0116/REV-0118에서 배운 대로 `OptionalHeader.DataDirectory[0].VirtualAddress`(RVA)를 파일 오프셋으로 변환한다. 값이 `0`이면 이 파일은 Export Table이 없다(대부분의 EXE).

**2) IMAGE_EXPORT_DIRECTORY 읽기**
`Base`, `NumberOfFunctions`, `NumberOfNames`, `AddressOfFunctions`, `AddressOfNames`, `AddressOfNameOrdinals` 여섯 필드를 확보한다.

**3) 이름 목록 전체 나열하기**
`AddressOfNames` 배열(`NumberOfNames`개, 각 4바이트 RVA)을 순회하며 각 RVA가 가리키는 문자열을 읽는다.

**4) 특정 이름의 실제 함수 주소 찾기**
`i`번째 이름을 찾았다면 `AddressOfNameOrdinals[i]`(2바이트 값)를 읽어 인덱스 `j`를 얻고, `AddressOfFunctions[j]`(4바이트 RVA)를 읽는다.

**5) Forwarder 여부 확인**
`AddressOfFunctions[j]`가 Export Table 자신의 RVA 범위(`DataDirectory[0].VirtualAddress` ~ `+Size`) 안에 있으면 그 위치의 문자열을 읽어 `"DLL이름.함수이름"` 형태인지 확인한다.

**6) IDA/PE-bear로 자동 확인**
```text
IDA: View → Open subviews → Exports
PE-bear: 좌측 트리 → Export Directory
```

## 명령어/단축키
```text
IDA: Exports 창에서 함수 더블클릭 → 그 함수 코드로 바로 이동
PE-bear: 좌측 트리 → Export Directory (이름/서수/RVA 표 확인)
rundll32: rundll32.exe 대상.dll,함수이름 인자   # Export된 함수를 직접 실행해볼 때
```

## 출력 해석
- Exports 창에 함수 이름이 알파벳 순으로 깔끔하게 정렬되어 보이면 정상적인 `AddressOfNames` 기반 목록(이 배열 자체가 사전순 정렬되어 있기 때문)
- 서수만 있고 이름이 없는 항목이 많으면(`NumberOfFunctions`가 `NumberOfNames`보다 훨씬 크면) 이 DLL이 이름 없는 내부 함수를 다수 노출하고 있다는 뜻
- 특정 익스포트 함수의 RVA로 이동했는데 코드가 아니라 문자열처럼 보이면 forwarder export — 그 문자열이 가리키는 실제 DLL/함수를 다시 찾아야 함
- `DataDirectory[0].VirtualAddress == 0`이면 이 파일에는 애초에 Export Table이 없는 것 — DLL인데 이 값이 0이면 이례적이므로 다른 로딩 메커니즘(리소스 기반 등)을 의심할 수 있음

## 흔한 실수
- `AddressOfNameOrdinals[i]`의 값을 곧바로 서수라고 착각하는 것 — 이 값은 `AddressOfFunctions` 배열의 인덱스이며, 실제 서수를 원하면 `Base`를 더해야 한다.
- `NumberOfFunctions`와 `NumberOfNames`가 항상 같다고 가정하는 것 — 서수로만 익스포트된 함수가 있으면 다르다.
- Forwarder export를 실제 함수 코드로 착각하고 그 RVA에서 디스어셈블을 시도하는 것 — RVA가 Export Table 자신의 범위 안에 있으면 반드시 문자열인지부터 확인해야 한다.
- `DllMain`을 Export Table에서 찾으려고 하는 것 — `DllMain`은 Export Table이 아니라 `AddressOfEntryPoint`로 지정된다.
- `AddressOfNames` 배열이 정렬되어 있다는 걸 몰라서 이진 탐색을 못 쓰고 매번 선형 탐색으로 이름을 찾는 것(직접 파서를 짤 때 성능 이슈로 이어질 수 있음).

## 막혔을 때 다음 체크
- `DataDirectory[0]`이 정의된 헤더 구조가 헷갈리면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- RVA를 파일 오프셋으로 바꾸는 계산이 필요하면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- 반대로 이 파일이 가져다 쓰는 함수(Import) 쪽 구조가 궁금하면 → [REV-0119 Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- `DllMain`이 아니라 EXE의 진입점/`WinMain`을 찾고 싶으면 → [REV-0121 Entry Point와 WinMain 찾기](./rev-0121-entry-point-winmain.md)

## 미니 예제
어떤 DLL의 `IMAGE_EXPORT_DIRECTORY`를 읽었더니 다음과 같았다고 하자.

```text
Base = 1
NumberOfFunctions = 5
NumberOfNames = 3

AddressOfNames         → ["Add", "Multiply", "Subtract"]  (사전순 정렬)
AddressOfNameOrdinals  → [0, 2, 1]     (즉 "Add"→index0, "Multiply"→index2, "Subtract"→index1)
AddressOfFunctions     → [0x1200(Add), 0x1350(Subtract), 0x1420(Multiply), 0x1500(?), 0x15A0(?)]
```

`"Multiply"`의 실제 주소를 찾는 과정: `AddressOfNames`에서 `"Multiply"`의 인덱스는 `1` → `AddressOfNameOrdinals[1] = 2` → `AddressOfFunctions[2] = 0x1420`. 따라서 `Multiply` 함수의 RVA는 `0x1420`이다. 인덱스 `3`, `4`에 해당하는 함수 두 개는 `AddressOfNames`에 등록되어 있지 않으므로 이름이 없고, 서수로만(`Base + 3 = 4`, `Base + 4 = 5`) 접근 가능한 함수다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0121 — Entry Point와 WinMain 찾기
- REV-0114 — PE 파일 구조 한 번에 보기

## 출처/검증
- `IMAGE_EXPORT_DIRECTORY` 구조체 정의 및 `AddressOfFunctions`/`AddressOfNames`/`AddressOfNameOrdinals` 관계, forwarder export 판정 방식: Microsoft Learn "PE Format" 공식 문서, "The .edata Section" 절 기준 (2026-09-08 검증).
- `GetProcAddress`의 이름 기반 탐색 동작 방식: Microsoft Learn Win32 API `GetProcAddress` 문서 및 PE Format 문서 공통 설명 기준.
- 서수 전용 익스포트, forwarder export 실제 사례: 다수 공개 Windows 내부구조/리버싱 참고자료의 일반화된 설명.
