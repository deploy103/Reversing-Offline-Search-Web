---
id: REV-0567
title: "Reflective DLL Loading 개념 소개"
slug: "rev-0567-reflective-dll-loading"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["Reflective DLL Injection", "ReflectiveLoader", "manual mapping", "수동 매핑", "메모리 로딩 DLL", "재배치", "IMAGE_BASE_RELOCATION"]
aliases: ["리플렉티브 DLL 로딩", "메모리에서 직접 로드되는 DLL", "디스크에 없는 DLL", "수동 PE 매핑"]
symptom_keywords: ["디스크에 파일이 없는데 DLL이 로드된 흔적이 있다", "LoadLibrary 없이 DLL이 메모리에 나타남", "모듈 목록에 없는데 실행 중인 코드가 있다", "ReflectiveLoader라는 함수 이름을 봤다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Reflective DLL Loading(리플렉티브 DLL 로딩)은 Windows의 정상적인 `LoadLibrary` 로더를 거치지 않고, DLL 자신이 가진 로더 코드가 스스로를 메모리에 매핑·재배치·초기화하는 기법으로, 디스크에 파일을 남기지 않고 모듈 목록(PEB의 `Ldr` 리스트)에도 등록되지 않기 때문에 일반적인 "Imports/Exports를 보고 로드된 DLL을 확인"하는 정적 분석 습관만으로는 탐지가 안 되는 대표적인 은폐 로딩 기법이다.

## 언제 검색해야 하나
- 메모리 덤프나 프로세스에서 PE 헤더(`MZ`)로 시작하는 데이터 블록이 발견됐는데, 해당 경로의 파일이 디스크에 없거나 `Process Hacker`/`Process Explorer`의 모듈 목록에도 없을 때
- 코드에서 `ReflectiveLoader`라는 함수 이름이나 그와 비슷한 자체 PE 파서/재배치 루프를 봤을 때
- CTF 라이트업에서 "Reflective DLL Injection"이라는 용어를 보고 원리가 궁금할 때
- 인젝션된 DLL을 분석해야 하는데 `LoadLibrary` 호출 흔적 없이 코드가 실행되고 있는 것을 발견했을 때

## 핵심 개념
정상적인 DLL 로딩은 `LoadLibrary`가 다음을 순서대로 수행한다: 디스크에서 파일을 읽고, PE 헤더를 파싱해 필요한 메모리를 예약(`VirtualAlloc`)한 뒤 섹션들을 복사하고, Import Table을 순회하며 의존 DLL들을 로드하고 함수 주소를 채우고(REV-0119 참고), Base Relocation(재배치) 정보로 주소를 수정하고, PEB의 모듈 리스트에 등록한 뒤 `DllMain`을 호출한다.

Reflective DLL Loading은 이 과정을 **DLL 자기 자신이 직접 구현**한다. 대표적으로 Stephen Fewer가 만든 오픈소스 `ReflectiveDLLInjection` 프로젝트가 이 기법의 원형으로 널리 쓰인다. 동작 순서는 대략 다음과 같다.

1. 공격자(또는 인젝터 프로세스)가 원본 DLL 파일 전체(디스크 이미지 그대로, 즉 파싱 안 된 raw 바이트)를 대상 프로세스 메모리에 `VirtualAllocEx` + `WriteProcessMemory`로 그냥 복사해 넣는다. 이 시점엔 아직 정상적인 PE 이미지 형태가 아니다.
2. DLL 내부에 미리 포함되어 있는 특수 함수 `ReflectiveLoader`(Export되어 있거나 오프셋으로 직접 찾음)를 새 스레드(`CreateRemoteThread`)나 문맥 조작(`SetThreadContext`)으로 실행시킨다.
3. `ReflectiveLoader`는 스스로 자신의 현재 메모리 위치를 찾아내고(콜스택이나 SEH 트릭으로 자기 자신의 베이스 주소를 알아냄), PE 헤더를 직접 파싱해 섹션 정렬에 맞춰 새 메모리 영역에 이미지를 올바르게 펼쳐 복사한다.
4. Import Table을 직접 순회하며 `LoadLibrary`/`GetProcAddress`를 호출해(또는 이마저도 API Hashing으로 이름 없이) 의존성을 해결한다.
5. `IMAGE_DIRECTORY_ENTRY_BASERELOC`(재배치 디렉터리)을 직접 파싱해 로드된 주소와 원래 선호 베이스 주소(`ImageBase`)의 차이만큼 절대 주소를 가진 명령어들을 패치한다.
6. 마지막으로 자신의 `DllMain`을 직접 호출한다.

이 모든 과정이 Windows 로더를 거치지 않기 때문에 다음과 같은 특징이 생긴다: 디스크에 DLL 파일이 남지 않을 수 있음(파일리스), PEB의 `InLoadOrderModuleList` 등 모듈 리스트에 등록되지 않아 `Process Explorer`의 DLL 목록이나 `lsass`류 도구로 열거가 안 됨, Import Table을 보고 "이 DLL이 어떤 API를 쓰는지" 파악하는 정적 분석이 어려움(대개 API Hashing과 함께 사용됨, REV-0569 참고).

## 화면/코드에서 보이는 징후
- 코드에 자체적으로 `IMAGE_DOS_HEADER.e_lfanew`를 읽고 `IMAGE_NT_HEADERS`를 파싱하는 루프, 섹션 헤더를 순회하며 `memcpy`하는 코드가 보임 — 직접 만든 PE 로더
- `IMAGE_BASE_RELOCATION` 구조체를 순회하며 `IMAGE_REL_BASED_HIGHLOW`/`IMAGE_REL_BASED_DIR64` 타입 재배치 항목을 처리하는 루프
- 함수 이름에 `ReflectiveLoader`, `LoadRemoteLibraryR` 등이 붙어 있거나(Stephen Fewer 원본 프로젝트 관례), Export Table에 이런 이름의 함수가 하나만 존재
- 메모리 덤프 도구(예: x64dbg의 메모리 맵, Process Hacker의 Memory 탭)에서 `MZ` 시그니처로 시작하지만 파일 매핑(Mapped File) 정보가 없는 `Private` 타입 메모리 영역이 발견됨

## 가장 먼저 할 것
1. 의심되는 메모리 영역을 x64dbg의 메모리 맵(`Memory Map`, `Alt+M`)에서 찾아 `MZ`로 시작하는지, `Type` 컬럼이 `Priv`(Private, 즉 파일 매핑이 아닌 순수 할당된 메모리)인지 확인한다. 정상 DLL은 `Map`으로 표시되지만 리플렉티브 로딩된 DLL은 `Priv`로 나타난다.
2. 해당 영역을 덤프(우클릭 → `Follow in Dump` 후 선택 영역을 파일로 저장)해서 PE-bear나 IDA로 별도 분석 가능한 파일로 만든다.

## 단계별 절차
**1) 인젝터(로더) 측 코드 분석**
- 인젝터 프로세스(또는 인젝션을 수행하는 셸코드/EXE)에서 `VirtualAllocEx`, `WriteProcessMemory`, `CreateRemoteThread`(또는 `NtCreateThreadEx`, `RtlCreateUserThread`) 호출 순서를 찾는다.
- `WriteProcessMemory`로 써넣는 데이터의 크기와 시작 부분을 확인해 `MZ`/`PE` 시그니처가 있는지 본다 — DLL 원본 이미지를 그대로 복사하는 패턴이면 리플렉티브 로딩 후보다.

**2) 대상 프로세스 메모리에서 ReflectiveLoader 찾기**
- 대상 프로세스에 x64dbg를 붙이고(`Attach`), `CreateRemoteThread`의 시작 주소로 지정된 오프셋으로 이동한다.
- 그 함수(`ReflectiveLoader`)를 스텝(`F7`)으로 따라가면서, 자기 위치를 찾는 코드(콜 후 스택에서 리턴 주소를 읽는 방식이 흔함) → PE 헤더 파싱 → 섹션 복사 → 재배치 처리 → Import 해결 → `DllMain` 호출 순서를 확인한다.

**3) 최종 매핑된 이미지 덤프 및 재구성**
- `DllMain` 호출 직전/직후 시점에 실행을 멈추고, 이미지가 매핑된 최종 메모리 주소를 메모리 맵에서 찾는다.
- 해당 영역을 통째로 덤프한 뒤, 섹션 헤더의 `VirtualAddress`/`PointerToRawData`가 실행 시 매핑 상태와 다를 수 있으므로 PE-bear의 "Dump Process/Rebuild PE" 유사 기능이나 수동으로 헤더를 조정해 정적 분석 가능한 파일로 재구성한다(이 과정은 REV-0568 프로세스 할로잉의 덤프/재구성 절차와 유사하다).

## 명령어/단축키
- x64dbg: `Alt+M`(메모리 맵), 우클릭 `Follow in Dump`, 우클릭 선택 영역 `Binary → Save To a File`(덤프)
- x64dbg: `Attach`(다른 프로세스에 붙기), `F7`/`F8`(스텝), `Ctrl+G`(주소 이동)
- IDA: 덤프한 파일을 새로 열어 `Alt+T`로 `IMAGE_DOS_HEADER`/`IMAGE_NT_HEADERS` 구조체 수동 적용

## 출력 해석
- 메모리 맵에서 `Type = Priv`이면서 시작 4바이트가 `4D 5A`(`MZ`)이면 파일에서 매핑된 것이 아니라 코드가 직접 써넣은 이미지라는 뜻이다.
- 재배치 처리 루프가 보인다는 것은 이 DLL이 선호 베이스 주소가 아닌 곳에 로드될 수 있음을 스스로 대비하고 있다는 의미이며, 통상적인 ASLR 대응과 별개로 "자기 자신을 수동으로 재배치하는 능력"이 있다는 신호다.

## 흔한 실수
- Import Table이 비어있거나 이상하다고 해서 "이 DLL은 아무 API도 안 쓴다"고 판단하는 것. 실제로는 API Hashing이나 자체 `GetProcAddress` 구현으로 이름 문자열을 감춘 경우가 많다(REV-0569 참고).
- 디스크에 파일이 없다는 이유만으로 분석을 포기하는 것. 메모리 덤프로 얼마든지 재구성해 분석할 수 있다.
- 프로세스 모듈 목록(`Process Explorer`, `!lmi` 등)만 보고 "이 프로세스는 추가로 로드된 DLL이 없다"고 결론짓는 것. 리플렉티브 로딩은 정확히 이 목록을 우회하기 위한 기법이다.
- 재배치 처리 루프와 일반적인 압축 해제(UPX 등) 루프를 혼동하는 것. 재배치 루프는 `IMAGE_REL_BASED_*` 타입 값과 델타(현재 로드 주소 - `ImageBase`)를 더하는 패턴이 특징이다.

## 막혔을 때 다음 체크
- 인젝션 자체의 흐름(할로잉 방식인지, 단순 DLL 인젝션인지)이 헷갈리면 → REV-0568(프로세스 할로잉 개념 소개)을 함께 읽는다.
- 함수 이름이 전혀 안 보이고 해시 값 비교만 보인다면 → REV-0569(API Hashing 개념)와 REV-0570(API Hashing 상수를 IDA/Ghidra에서 찾는 법)을 참고한다.
- DLL의 정상적인 로딩 순서 자체가 헷갈리면 → REV-0119(Import Table에서 중요한 API 찾기)와 REV-0129(GetProcAddress LoadLibrary 동적 API 해석)를 먼저 복습한다.

## 미니 예제
아래는 널리 알려진 Reflective DLL Injection 구조를 단순화한 의사코드다.

```c
// 인젝터 측
LPVOID remoteMem = VirtualAllocEx(hProcess, NULL, dllSize, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
WriteProcessMemory(hProcess, remoteMem, rawDllBytes, dllSize, NULL);
DWORD loaderOffset = FindReflectiveLoaderOffset(rawDllBytes); // Export 테이블에서 오프셋 계산
CreateRemoteThread(hProcess, NULL, 0,
    (LPTHREAD_START_ROUTINE)((BYTE*)remoteMem + loaderOffset),
    remoteMem, 0, NULL);
```

```c
// DLL 내부 ReflectiveLoader (개념 요약)
void* ReflectiveLoader(void* rawImageBase) {
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)rawImageBase;
    IMAGE_NT_HEADERS* nt  = (IMAGE_NT_HEADERS*)((BYTE*)rawImageBase + dos->e_lfanew);
    void* newBase = VirtualAlloc(NULL, nt->OptionalHeader.SizeOfImage, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    // 섹션별 복사
    for (섹션 개수만큼)
        memcpy((BYTE*)newBase + section->VirtualAddress,
               (BYTE*)rawImageBase + section->PointerToRawData,
               section->SizeOfRawData);
    ProcessRelocations(newBase, nt);   // 재배치 직접 처리
    ResolveImports(newBase, nt);       // Import 직접 처리
    DllMain(newBase, DLL_PROCESS_ATTACH, NULL);
    return newBase;
}
```
인젝터는 `remoteMem`에 raw DLL 바이트를 그대로 써넣기만 하고, 실제 "제대로 된 PE 이미지로 펼치는 일"은 대상 프로세스 안에서 `ReflectiveLoader` 스스로가 수행한다. 이 때문에 `LoadLibrary`를 부르는 코드가 인젝터/대상 프로세스 어디에도 없는데도 DLL이 완전히 동작하게 된다.

## 관련 글
- REV-0568 — 프로세스 할로잉(Process Hollowing) 개념 소개
- REV-0569 — Import 함수를 런타임에 해시로 찾는 API Hashing 개념
- REV-0570 — API Hashing 상수를 IDA/Ghidra에서 찾는 법
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석

## 출처/검증
- Reflective DLL Injection 기법은 Stephen Fewer가 공개한 `ReflectiveDLLInjection` 오픈소스 프로젝트(GitHub, stephenfewer/ReflectiveDLLInjection)가 사실상의 원형/표준 참고 구현이다.
- PE 이미지 매핑, 재배치(`IMAGE_BASE_RELOCATION`), Import 해결 절차의 세부 필드는 Microsoft PE/COFF 형식 공식 문서 기준이다.
- 메모리 영역의 `Private`/`Mapped` 구분과 리플렉티브 로딩 탐지 휴리스틱은 다수의 공개 악성코드 분석 레퍼런스에서 공통적으로 사용하는 방법이다(2026-09-08 기준 서술).
