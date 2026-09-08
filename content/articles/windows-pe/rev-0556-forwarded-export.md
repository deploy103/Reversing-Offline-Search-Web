---
id: REV-0556
title: "Forwarded Export 이해하기"
slug: "rev-0556-forwarded-export"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["Forwarded Export", "IMAGE_EXPORT_DIRECTORY", "AddressOfFunctions", "Export Forwarder", "API Set", "api-ms-win-core"]
aliases: ["포워드 익스포트", "익스포트 포워더란", "함수가 다른 dll로 위임됨", "api-ms-win 이란"]
symptom_keywords: ["Export 함수 주소가 다른 DLL 이름 문자열처럼 보임", "IDA에서 export 주소가 코드가 아니라 문자열을 가리킴", "api-ms-win-core dll이 실제로 뭘 하는지 모름", "kernel32 함수가 실제로 다른 dll에 있다고 나옴"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Forwarded Export(포워드 익스포트)는 DLL이 "이 함수는 내가 직접 구현하지 않고, 다른 DLL의 함수를 그대로 쓴다"고 위임하는 메커니즘으로, `IMAGE_EXPORT_DIRECTORY`의 `AddressOfFunctions` 배열 원소가 코드 주소가 아니라 `"대상DLL.함수이름"` 형태의 **문자열**을 가리킬 때가 바로 이 경우이며, Windows 10/11의 `api-ms-win-core-*.dll` 계열(API Set)이 대표적인 실사용 예다.

## 언제 검색해야 하나
- IDA의 Exports 창에서 함수 주소를 더블클릭했는데 코드가 아니라 `NTDLL.RtlAllocateHeap` 같은 문자열이 나올 때
- `api-ms-win-core-file-l1-1-0.dll`, `api-ms-win-core-memory-l1-1-0.dll` 같은 낯선 이름의 DLL을 Import Table이나 Dependency 뷰에서 봤을 때, 이 DLL이 실제로 뭘 하는지 궁금할 때
- Export Table을 파싱하는 스크립트를 짜다가 `AddressOfFunctions[i]`가 Export 디렉터리 자기 자신의 RVA 범위 안에 들어와서 이상하다고 느낄 때
- 악성코드가 정상 API 이름을 그대로 노출하면서도 실제 구현은 다른 모듈에 있어서 분석 도구가 혼동하는 경우를 이해하고 싶을 때

## 핵심 개념

### Export Table에서 함수 주소가 저장되는 방식
REV-0120에서 다룬 것처럼, `IMAGE_EXPORT_DIRECTORY.AddressOfFunctions`는 RVA들의 배열이고, 각 RVA는 보통 함수 코드가 시작하는 위치를 가리킨다. 그런데 이 값이 **Export 디렉터리 자체의 시작 RVA와 끝 RVA(= `DataDirectory[0].VirtualAddress` ~ `+ Size`) 사이에 들어오는 경우**가 있다. 이때 로더는 이 RVA를 코드 주소가 아니라 **문자열의 RVA**로 취급한다. 그 문자열의 형식은 항상 다음과 같다.

```text
"대상DLL이름.함수이름"        예: "NTDLL.RtlAllocateHeap"
"대상DLL이름.#서수"           예: "NTDLL.#123"  (서수로 포워딩하는 경우)
```

즉 이 DLL을 로드해서 `GetProcAddress`로 이 함수를 찾으면, 로더는 자기 코드를 실행하는 대신 문자열에 적힌 `NTDLL.dll`을 (아직 로드 안 됐으면) 로드하고 그 안의 `RtlAllocateHeap`을 다시 찾아서 그 주소를 최종적으로 돌려준다. 함수를 호출하는 쪽에서는 이 과정을 전혀 알 필요가 없다 — `GetProcAddress`가 알아서 체인을 따라간다.

### 왜 이런 기능이 존재하는가
- **코드 중복 제거**: 여러 DLL이 사실상 같은 구현을 공유해야 할 때, 실제 코드는 한 곳에만 두고 나머지는 이름만 노출한다.
- **API Set(최소 우회 계층)**: Windows 8 이후 `api-ms-win-core-*.dll`, `api-ms-win-crt-*.dll` 같은 아주 작은 "가상 DLL"들이 대량으로 존재하는데, 이들은 함수를 단 하나도 직접 구현하지 않고 **전부** `kernelbase.dll`, `ucrtbase.dll` 등으로 포워딩만 한다. 이렇게 하면 마이크로소프트는 내부 구현을 자유롭게 옮기면서도(예: kernel32 → kernelbase 이전) 겉보기 API 표면은 그대로 유지할 수 있다.
- **레거시 호환성**: 과거 버전에서 특정 DLL에 있던 함수가 새 버전에서 다른 DLL로 옮겨졌을 때, 예전 이름의 export를 남겨두고 새 위치로 포워딩해서 하위 호환성을 유지한다.

### 판별 조건 요약
```c
DWORD funcRVA = AddressOfFunctions[i];
DWORD expDirStart = DataDirectory[0].VirtualAddress;
DWORD expDirEnd   = expDirStart + DataDirectory[0].Size;

if (funcRVA >= expDirStart && funcRVA < expDirEnd) {
    // 코드 주소가 아니라 "DLL.함수이름" 형태의 널 종료 문자열 RVA
    // 포워드 익스포트!
} else {
    // 평범한 함수 코드 RVA
}
```
이 조건이 리버서가 직접 Export Table을 파싱하는 도구를 만들 때 가장 자주 놓치는 부분이다 — 단순히 "RVA를 코드로 디스어셈블해봤더니 이상하다"로 끝나지 않고, 반드시 이 범위 체크를 먼저 해야 한다.

## 화면/코드에서 보이는 징후
- IDA Exports 창에서 함수를 더블클릭했는데 디스어셈블리 창이 아니라 `.rdata`나 `.edata` 섹션의 문자열 위치로 이동함
- IDA가 자동으로 해당 export 이름 옆에 `(forwarded to NTDLL.RtlAllocateHeap)` 같은 주석을 붙여주는 경우가 있음
- PE-bear의 Export Directory 뷰에서 함수 항목의 "Address" 컬럼에 코드 오프셋 대신 `모듈명.함수명` 텍스트가 표시됨
- `dumpbin /exports` 결과에서 함수 이름 옆에 실제 RVA 대신 `(forwarded to kernelbase.CreateFileW)` 같은 문구가 붙어 나옴

## 가장 먼저 할 것
낯선 이름의 함수 export를 열었는데 코드로 안 가고 문자열이 보이면, 당황하지 말고 그 문자열을 그대로 읽는다. `"KERNELBASE.CreateFileW"`처럼 보인다면 이 DLL은 그 함수를 직접 구현하지 않고 `kernelbase.dll`의 `CreateFileW`를 그대로 재노출하는 것뿐이다. 진짜 분석 대상은 포워딩 문자열이 가리키는 DLL(`kernelbase.dll`)을 별도로 로드해서 그 안의 실제 구현을 봐야 한다. `api-ms-win-*` 계열 DLL을 만났을 때는 애초에 그 DLL 자체를 분석할 필요가 거의 없다 — 항상 실제 구현은 `kernelbase.dll`, `ucrtbase.dll`, `ntdll.dll` 중 하나에 있다고 가정하고 그쪽을 바로 열면 된다.

## 단계별 절차

**1) Export Table 위치 확인**
REV-0120에서 배운 대로 `DataDirectory[0]`(RVA, Size)로 `IMAGE_EXPORT_DIRECTORY`를 찾는다.

**2) AddressOfFunctions 배열을 순회하며 범위 체크**
각 원소가 Export 디렉터리 자기 자신의 RVA 범위(`VirtualAddress` ~ `VirtualAddress+Size`) 안에 있는지 확인한다. 안에 있으면 포워더, 밖에 있으면 진짜 코드다.

**3) 포워더 문자열 읽기**
범위 안에 있다면 그 RVA를 파일 오프셋으로 바꿔서 널 종료 문자열을 읽는다. `.`을 기준으로 앞부분이 대상 DLL 이름, 뒷부분이 함수 이름(또는 `#숫자` 형태의 서수)이다.

**4) 대상 DLL을 별도로 로드해서 실제 구현 확인**
IDA에서 `File → Load file → PE`로 대상 DLL(예: `C:\Windows\System32\kernelbase.dll`)을 별도로 열거나, 이미 실행 중인 프로세스라면 x64dbg의 Memory Map에서 해당 DLL이 로드돼 있는지 확인하고 그 안의 함수로 이동한다.

**5) IDA 자동 처리 신뢰하기**
대부분의 경우 IDA는 포워드 익스포트를 자동으로 인식해서 이름 옆에 주석을 붙여준다. Exports 창에서 이름/주소 컬럼을 눈으로 훑기만 해도 어떤 함수가 포워딩인지 바로 알 수 있다.

## 명령어/단축키
```text
dumpbin /exports 대상.dll        Visual Studio 개발자 명령 프롬프트에서 실행,
                                  "(forwarded to X.Y)" 문구로 포워더 여부 바로 확인 가능
IDA: Exports 창(Alt+E 대응 View → Open subviews → Exports)에서
     함수 더블클릭 → 문자열 위치로 이동하면 포워더
x64dbg: Memory Map(Alt+M)에서 대상 DLL이 로드돼 있는지 확인 후 Symbols 창에서 실제 함수 탐색
```

## 출력 해석
- Exports 창의 함수 주소 컬럼이 `.text`나 `.code` 섹션이 아니라 `.rdata`/`.edata` 섹션 범위를 가리키면 포워더일 가능성이 매우 높다
- `dumpbin /exports`에서 `ordinal hint RVA name` 형식이 아니라 `ordinal hint name (forwarded to ...)` 형식으로 나오면 확정적으로 포워더다
- `api-ms-win-core-*.dll`, `api-ms-win-crt-*.dll`, `ext-ms-win-*.dll` 이름 패턴을 보면 그 DLL의 export가 거의 100% 포워더로만 구성돼 있다고 가정해도 무방하다

## 흔한 실수
- 포워더 문자열 RVA를 코드로 착각해서 억지로 디스어셈블을 시도하는 것 — ASCII 텍스트가 나오는데 이를 이상한 명령어로 오인하는 경우가 있다.
- `api-ms-win-*` 류의 얇은 DLL을 실제 구현체로 착각하고 그 안에서 로직을 찾으려 애쓰는 것 — 실제 구현은 항상 포워딩 대상(kernelbase, ucrtbase 등)에 있다.
- 포워더 체인이 여러 단계로 이어질 수 있다는 걸 모르고 한 번만 따라가고 포기하는 것 — 드물지만 A→B→C처럼 두 단계 이상 포워딩되는 경우도 있다.
- 서수로 포워딩된 경우(`"NTDLL.#123"`)에 이름을 못 찾겠다고 포기하는 것 — 대상 DLL의 export ordinal 표에서 123번을 찾아야 한다(REV-0555 Ordinal Import 분석법과 같은 접근).

## 막혔을 때 다음 체크
- Export Table 구조 자체가 헷갈리면 → [REV-0120 Export Table과 DLL 함수](./rev-0120-export-table.md)
- 서수 기반 임포트/익스포트를 이름으로 되돌리는 방법이 필요하면 CONTENT_PLAN의 REV-0555(Ordinal Import 분석법) 항목을 참고
- RVA를 파일 오프셋으로 바꾸는 계산이 헷갈리면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- 함수 이름만으로 어떤 API 계열인지 감이 안 잡히면 → [REV-0129 GetProcAddress LoadLibrary 동적 API 해석](./rev-0129-getprocaddress-loadlibrary.md)

## 미니 예제
`api-ms-win-core-heap-l1-1-0.dll`을 IDA로 열고 Exports 창을 봤다고 하자.

```text
Exports 창:
  HeapAlloc    → 더블클릭 → 코드 창이 아니라 문자열 위치로 이동
                → 읽어보니 "KERNELBASE.HeapAlloc"

해석:
  이 DLL 안에는 HeapAlloc의 실제 구현이 없다.
  실제 힙 할당 로직을 보려면 kernelbase.dll을 열어서
  그 안의 HeapAlloc 함수를 봐야 한다.
```

`dumpbin /exports`로 같은 파일을 확인하면 다음과 비슷한 줄이 보인다.

```text
    1    0 00000000 HeapAlloc (forwarded to KERNELBASE.HeapAlloc)
```
`RVA` 컬럼이 `00000000`으로 나오거나 아예 생략되고 `(forwarded to ...)` 문구가 붙는 것이 포워더의 전형적인 출력이다.

## 관련 글
- REV-0120 — Export Table과 DLL 함수
- REV-0118 — RVA VA Raw Offset 계산
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0557 — PE 체크섬(Checksum) 검증과 리버싱 의미

## 출처/검증
- `IMAGE_EXPORT_DIRECTORY` 구조와 forwarder RVA가 Export 디렉터리 범위 안에 들어올 때 문자열로 취급되는 규칙: Microsoft Learn "PE Format" 공식 문서, "Export Address Table" 절 기준 (2026-09-08 검증).
- `api-ms-win-core-*` API Set이 kernelbase.dll 등으로 포워딩만 하는 얇은 DLL이라는 사실: Microsoft Learn "API sets" 문서 및 다수 Windows 내부구조 리버싱 자료 기준.
- `dumpbin /exports`의 `(forwarded to ...)` 출력 형식: Visual Studio `dumpbin` 도구 실사용 관찰 및 공식 문서 기준.
