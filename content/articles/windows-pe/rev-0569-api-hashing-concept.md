---
id: REV-0569
title: "Import 함수를 런타임에 해시로 찾는 API Hashing 개념"
slug: "rev-0569-api-hashing-concept"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["API Hashing", "ROR13", "djb2", "동적 API 해결", "Import Table 회피", "해시 기반 GetProcAddress"]
aliases: ["API 해싱", "함수 이름 대신 해시값", "Import Table이 텅 빈 이유", "동적 API 로딩 은폐"]
symptom_keywords: ["Import Table을 봤는데 API가 거의 없다", "임포트가 kernel32밖에 없다", "상수 값과 비교한 뒤 함수를 호출한다", "ror 명령어와 add를 반복하는 루프가 있다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
API Hashing(API 해싱)은 악성코드나 패커가 Import Table에 `CreateFileA`, `VirtualAlloc` 같은 함수 이름 문자열을 그대로 남기지 않고, 대신 각 함수 이름을 특정 해시 알고리즘(흔히 ROR13 계열)으로 변환한 숫자 상수만 코드에 박아 두었다가, 실행 시점에 익스포트 테이블을 직접 순회하며 이름을 해시해 비교함으로써 API를 찾아 호출하는 기법으로, Import Table만 보고 "이 프로그램이 무슨 일을 하는지" 짐작하려는 정적 분석을 무력화시킨다.

## 언제 검색해야 하나
- IDA Imports 탭(`Shift+F11`)을 열었는데 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress` 딱 두세 개만 있고 나머지 API가 안 보일 때
- 코드에서 어떤 32비트 상수(예: `0x876F8B31`)와 계산된 값을 `cmp`로 비교한 뒤 그 결과로 함수 포인터를 호출하는 패턴을 봤을 때
- 함수 이름 대신 숫자 상수만 잔뜩 하드코딩되어 있어서 이 프로그램이 정확히 어떤 API를 쓰는지 짐작이 안 될 때
- 디스어셈블리에서 `ror`(또는 `rol`), `add`, `cmp` 명령어가 문자열 순회로 보이는 루프 안에서 반복되는 것을 봤을 때

## 핵심 개념
정상적인 프로그램은 컴파일 시점에 어떤 API를 쓸지 정해지고, 이는 PE의 Import Table(REV-0119 참고)에 함수 이름 문자열로 기록된다. 분석가는 이 목록만 봐도 "네트워크 API가 있으니 통신을 한다", "레지스트리 API가 있으니 값을 읽거나 쓴다"는 식으로 대략적인 기능을 짐작할 수 있다. API Hashing은 바로 이 지름길을 차단하기 위한 기법이다.

동작 원리는 다음과 같다.

1. **오프라인에서 해시 상수 미리 계산**: 공격자는 자신이 쓸 API 이름들(`"VirtualAlloc"`, `"WriteProcessMemory"` 등)을 특정 해시 함수에 넣어 32비트(또는 64비트) 정수 값을 미리 계산해 코드에 상수로 박아둔다. 흔히 쓰이는 해시는 각 문자를 ASCII 코드로 더하면서 누적 해시값을 13비트만큼 오른쪽으로 순환 회전(ROR13, Rotate Right 13)시키는 방식으로, Metasploit 셸코드에서 유명해진 알고리즘이다. 그 외에도 djb2(`hash = hash*33 + c`), FNV-1a, CRC32 등 다양한 변형이 쓰인다.
2. **실행 시점에 모듈 베이스 확보**: 프로그램은 Import Table에 의존하지 않고, PEB(Process Environment Block)의 `Ldr` 리스트를 직접 순회하거나(`fs:[0x30]`/`gs:[0x60]`으로 PEB 접근, REV-0132 참고), `kernel32.dll`처럼 이미 로드되어 있는 것이 확실한 모듈의 베이스 주소를 알아낸다.
3. **익스포트 테이블 직접 순회**: 해당 모듈의 `IMAGE_EXPORT_DIRECTORY`(REV-0120 참고)에서 `AddressOfNames` 배열을 순회하며, 각 이름 문자열을 똑같은 해시 알고리즘으로 계산한다.
4. **해시값 비교**: 계산된 해시값을 코드에 미리 박아둔 상수와 비교(`cmp`)해서 일치하면, 그 이름에 대응하는 `AddressOfFunctions` 배열의 함수 주소를 가져와 사용한다. 이 과정 전체가 사실상 직접 구현한 `GetProcAddress`다.
5. 이렇게 얻은 함수 포인터로 `LoadLibrary`, `VirtualAlloc` 등을 호출해 필요한 다른 DLL과 API도 같은 방식으로 계속 확장해 나간다.

이 기법의 효과는 두 가지다. 첫째, Import Table에 실제로 쓰는 API 이름이 전혀 남지 않으므로 정적 분석/시그니처 기반 탐지가 훨씬 어려워진다. 둘째, 문자열로 `"VirtualAlloc"` 같은 텍스트가 바이너리에 남지 않으므로 `strings` 명령이나 문자열 뷰(REV-0128 참고)로 기능을 유추하기도 어려워진다. Reflective DLL Loading(REV-0567)이나 셸코드에서 특히 자주 함께 쓰이는데, 이런 코드는 애초에 정상 로더를 거치지 않으므로 Import Table 자체가 없거나 극도로 빈약하기 때문이다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭에 `LoadLibraryA`/`LoadLibraryW`, `GetProcAddress`, 혹은 그마저도 없이 `kernel32.dll` 베이스 주소만 얻는 코드만 있고 나머지가 텅 빔
- 디스어셈블리에 `ror edx, 0Dh`(13비트 회전) 또는 `rol`, 그 직후 `add`가 반복되는 루프 — 문자열의 각 바이트를 순회하며 해시를 누적하는 전형적인 패턴
- `cmp eax, 0A1B2C3D4h` 같은 매직 넘버 비교가 여러 개 이어지고, 각 비교의 `jz`/`je` 분기마다 서로 다른 함수 호출로 이어짐
- 함수에 이름이 없고 `sub_XXXXXX`로만 표시되는데, 그 안에서 PEB(`fs:[0x30]` 또는 `gs:[0x60]`) 접근 코드가 보임

## 가장 먼저 할 것
1. `ror`/`rol` + `add`가 루프 안에서 반복되는 코드를 찾아 그 루프가 입력받는 문자열(함수 이름 후보)이 어디서 오는지 xref로 추적한다. 대개 `IMAGE_EXPORT_DIRECTORY.AddressOfNames` 배열을 가리키는 포인터 연산이 근처에 있다.
2. 비교 대상이 되는 매직 넘버 상수들을 목록으로 뽑아 둔다. 이후 알려진 API 이름들을 같은 알고리즘으로 해시해서 이 상수들과 매칭시키는 것이 다음 단계다.

## 단계별 절차
**1) 해시 알고리즘 특정**
- 회전 비트 수(예: 13), 초기값(흔히 0), 각 반복에서 대소문자를 구분하는지(대문자로 변환 후 계산하는 경우가 많음), 널 종료 방식인지 등을 디스어셈블리에서 정확히 재현할 수 있도록 의사코드로 옮겨 적는다.

**2) 알려진 API 이름을 같은 알고리즘으로 미리 해시**
- Python 등으로 `kernel32.dll`, `ntdll.dll`, `advapi32.dll`, `ws2_32.dll` 등 흔히 쓰이는 DLL의 Export 함수 이름 목록을 가져와 동일한 해시 함수로 전부 계산한 룩업 테이블을 만든다. (오프라인 스크립트 작성은 이 글의 범위를 넘지만, IDAPython으로 대상 DLL의 export를 순회하며 계산하는 방식이 실전에서 흔히 쓰인다.)

**3) 상수-함수명 매칭 및 주석/이름 붙이기**
- 코드에서 발견한 매직 넘버 상수를 1)에서 만든 룩업 테이블과 대조해 실제 함수 이름을 알아낸다.
- IDA에서 해당 상수가 나오는 위치에 `;` 주석으로 실제 함수 이름을 달아두거나, 해시 계산 함수 자체의 리턴값을 기준으로 `Rename`(`N`)해서 이후 분석이 쉬워지도록 만든다.

**4) 동적 분석으로 교차 검증**
- x64dbg로 실제 실행하면서 해시 비교 직후 호출되는 함수의 진짜 주소가 어떤 DLL의 어떤 export인지 확인한다(`Ctrl+G`로 주소 이동 후 모듈/함수 이름이 표시되는지 확인). 정적으로 추정한 이름과 일치하는지 검증한다.

## 명령어/단축키
- IDA: `Shift+F11`(Imports), `X`(교차 참조), `N`(이름 변경/Rename), `;`(주석 추가)
- x64dbg: `Ctrl+G`(주소 이동, 심볼 있으면 함수명 자동 표시), `F7`/`F8`(스텝하며 호출된 실제 함수 확인)

## 출력 해석
- 해시 비교 직후 분기(`je`)를 따라가면 함수 포인터를 레지스터나 지역 변수에 저장하는 코드로 이어지는데, 이 값이 최종적으로 `call` 명령의 대상이 되면 그것이 진짜 API 호출이다.
- 룩업 테이블 대조 결과 여러 개의 상수가 같은 DLL의 함수들과 일치한다면, 그 DLL의 이름(예: `ws2_32.dll` = 네트워크 관련 함수들과 일치)만으로도 프로그램의 대략적인 목적(네트워크 통신, 프로세스 조작 등)을 짐작할 수 있다.

## 흔한 실수
- Import Table이 비어있다고 해서 "이 프로그램은 아무 API도 안 쓴다"고 결론짓는 것. 실제로는 해싱으로 숨겨져 있을 뿐 훨씬 많은 API를 쓰는 경우가 대부분이다.
- 회전 비트 수나 대소문자 처리 방식을 정확히 재현하지 않고 대충 비슷한 해시로 매칭을 시도해 엉뚱한 함수 이름으로 결론 내리는 것. 반드시 디스어셈블리의 정확한 연산 순서를 그대로 재현해야 한다.
- 해시 알고리즘이 프로그램마다 다를 수 있다는 것을 잊고, 예전에 본 ROR13 상수 목록을 다른 샘플에 그대로 재사용하는 것.
- 동적 검증 없이 해시 매칭 결과만 믿는 것. 해시 충돌(다른 이름인데 같은 해시값)이 이론상 가능하므로 실제 호출된 함수를 x64dbg로 한 번은 확인하는 습관이 필요하다.

## 막혔을 때 다음 체크
- 이 함수들이 IDA/Ghidra에서 그래프로 잘 안 보이거나 자동 분석이 안 될 때 → REV-0570(API Hashing 상수를 IDA/Ghidra에서 찾는 법)을 참고한다.
- 이 기법이 Reflective DLL Loading이나 셸코드와 함께 나온다면 → REV-0567(Reflective DLL Loading 개념 소개)을 함께 본다.
- PEB를 직접 읽는 코드 자체가 낯설다면 → REV-0132(PEB BeingDebugged 검사 이해)에서 PEB 구조 접근 방식을 먼저 익힌다.

## 미니 예제
```c
// 전형적인 ROR13 기반 해시 (개념 요약, 대소문자는 대문자로 정규화한다고 가정)
DWORD HashApiName(const char* name) {
    DWORD hash = 0;
    while (*name) {
        hash = ((hash >> 13) | (hash << (32 - 13))); // ROR 13
        hash += (BYTE)*name;
        name++;
    }
    return hash;
}

// 사용 예: 이름 없이 해시값만으로 함수 찾기
FARPROC pVirtualAlloc = ResolveByHash(hKernel32, 0x91AFCA54); // 0x91AFCA54 == HashApiName("VirtualAlloc")
```
`ResolveByHash`는 `hKernel32`가 가리키는 모듈의 `IMAGE_EXPORT_DIRECTORY`를 직접 파싱해 `AddressOfNames` 배열의 각 이름에 `HashApiName`을 적용하고, 그 결과가 `0x91AFCA54`와 일치하는 항목을 찾아 대응하는 함수 주소를 리턴한다. 소스 코드 어디에도 `"VirtualAlloc"`이라는 문자열이 등장하지 않으므로, 컴파일된 바이너리의 Import Table과 문자열 목록 어디를 봐도 이 함수를 쓴다는 흔적이 남지 않는다.

## 관련 글
- REV-0570 — API Hashing 상수를 IDA/Ghidra에서 찾는 법
- REV-0567 — Reflective DLL Loading 개념 소개
- REV-0568 — 프로세스 할로잉(Process Hollowing) 개념 소개
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0120 — Export Table과 DLL 함수
- REV-0132 — PEB BeingDebugged 검사 이해

## 출처/검증
- ROR13 기반 API 해싱은 Metasploit 프레임워크의 셸코드 로더에서 널리 사용되어 유명해진 방식으로, 다수의 공개 셸코드/악성코드 분석 레퍼런스에서 표준적으로 다루는 기법이다.
- `IMAGE_EXPORT_DIRECTORY`의 `AddressOfNames`/`AddressOfFunctions`/`AddressOfNameOrdinals` 필드 구조는 Microsoft PE/COFF 형식 공식 문서 기준이다.
- PEB의 `Ldr`/모듈 리스트를 통한 모듈 베이스 확보 방식은 다수의 Windows 내부 구조 레퍼런스 및 공개 셸코드 예제에서 일관되게 확인되는 패턴이다(2026-09-08 기준 서술).
