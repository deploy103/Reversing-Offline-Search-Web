---
id: REV-0554
title: "Bound Import와 Import 최적화 이해하기"
slug: "rev-0554-bound-import"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear"]
keywords: ["IMAGE_BOUND_IMPORT_DESCRIPTOR", "IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT", "IMAGE_BOUND_FORWARDER_REF", "TimeDateStamp", "바인딩 임포트", "ASLR과 바인딩"]
aliases: ["바운드 임포트란", "임포트 바인딩 최적화", "TimeDateStamp 불일치", "레거시 로드 최적화"]
symptom_keywords: ["IAT에 이미 그럴듯한 주소가 채워져 있음", "Bound Import 디렉터리가 뭔지 모름", "정적 분석 중 IAT 값을 실제 주소로 착각함", "옛날 시스템 파일에서만 보이는 임포트 디렉터리가 있음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Bound Import는 링커가 "이 DLL은 특정 시점(특정 `TimeDateStamp`)에 특정 주소로 로드될 것"이라고 가정하고 IAT에 실제 함수 주소를 미리 계산해 박아 넣어두는 레거시 로드 시간 최적화 기법으로, 로더는 실제로 로드된 DLL의 타임스탬프가 바인딩 당시와 정확히 일치할 때만 이 미리 계산된 값을 그대로 신뢰해 `GetProcAddress` 조회를 생략하며, 하나라도 다르면 조용히 무시하고 일반적인 방식으로 다시 해석하기 때문에 정적 분석 중 IAT 값을 실제 로드 주소로 오인하지 않도록 주의해야 한다.

## 언제 검색해야 하나
- 정적으로 IAT를 열어봤는데 아직 로드되지도 않았을 파일에 이미 그럴듯한 절대 주소들이 채워져 있어서 당황할 때
- PE-bear나 CFF Explorer의 Directory 목록에서 `Bound Import`(인덱스 11) 항목을 발견했는데 무슨 의미인지 모를 때
- 오래된 시스템 DLL이나 특정 레거시 빌드 옵션(`/BIND`)으로 빌드된 파일을 분석할 때
- ASLR과 Bound Import가 왜 서로 충돌하는 개념인지 이해하고 싶을 때
- IAT의 초기값을 "이미 로드된 실제 주소"로 착각해서 잘못된 결론을 내릴 뻔했을 때

## 핵심 개념

### 왜 바인딩이 필요했는가
프로세스가 시작할 때 로더는 각 임포트 DLL을 로드한 뒤, Import Name Table에 나열된 함수 이름 하나하나에 대해 해당 DLL의 Export Table을 뒤져 `GetProcAddress`에 해당하는 조회를 수행하고, 그 결과 주소로 IAT를 채운다. 이 조회 과정은 임포트 함수가 많을수록, 그리고 여러 프로세스가 같은 DLL을 반복해서 로드할수록 누적 비용이 커진다. `/BIND` 링커 옵션(또는 `BIND.exe` 후처리 도구)을 쓰면, 빌드 시점에 미리 "이 DLL이 어떤 버전(타임스탬프)이고 어떤 주소에 로드될 예정인지"를 가정한 뒤 그 함수들의 실제 주소를 계산해서 IAT에 미리 써넣을 수 있다. 만약 실제 로드 시점에 그 가정이 정확히 들어맞으면, 로더는 조회 과정을 통째로 생략하고 그냥 이 값을 그대로 쓸 수 있어 시작 시간이 빨라진다.

### IMAGE_BOUND_IMPORT_DESCRIPTOR 구조
`OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_BOUND_IMPORT]`(인덱스 11)가 이 정보의 시작을 가리킨다.
```c
typedef struct _IMAGE_BOUND_IMPORT_DESCRIPTOR {
    DWORD TimeDateStamp;             // 바인딩 당시 대상 DLL의 타임스탬프
    WORD  OffsetModuleName;          // DLL 이름 문자열까지의 오프셋(디스크립터 배열 시작 기준)
    WORD  NumberOfModuleForwarderRefs; // 뒤따르는 IMAGE_BOUND_FORWARDER_REF 개수
    // NumberOfModuleForwarderRefs개의 IMAGE_BOUND_FORWARDER_REF가 이어짐
} IMAGE_BOUND_IMPORT_DESCRIPTOR;

typedef struct _IMAGE_BOUND_FORWARDER_REF {
    DWORD TimeDateStamp;    // 전달(forward)되는 대상 DLL의 타임스탬프
    WORD  OffsetModuleName;
    WORD  Reserved;
} IMAGE_BOUND_FORWARDER_REF;
```
`IMAGE_BOUND_FORWARDER_REF`는 어떤 임포트 함수가 실제로는 다른 DLL로 전달(export forwarding, REV-0556 참고)되는 경우, 그 최종 대상 DLL까지도 함께 바인딩했다는 것을 기록한다.

### 로더가 바인딩을 신뢰하는 조건
로더는 프로세스 시작 시 실제로 로드한 각 DLL의 PE 헤더 `FileHeader.TimeDateStamp`를 확인해, `IMAGE_BOUND_IMPORT_DESCRIPTOR.TimeDateStamp`와 정확히 일치하는지 비교한다. 일치하면 IAT에 미리 채워진 값을 그대로 신뢰하고 별도 조회를 생략한다. 하나라도 다르면(예: 해당 DLL이 패치/업데이트되어 다시 빌드된 경우) 바인딩된 값 전체를 버리고, 일반적인 Import Name Table 기반 `GetProcAddress` 조회로 되돌아간다. 즉 바인딩은 어디까지나 "맞으면 좋고 틀리면 그냥 무시되는" 최적화용 힌트일 뿐, 실패해도 프로그램 동작 자체에는 영향이 없다.

### BIND.exe와 링커 옵션
바인딩은 링크 시점에 `/BIND` 옵션으로 곧바로 만들어지거나, 이미 빌드된 실행 파일에 대해 별도의 후처리 도구(`BIND.exe`, 구 Platform SDK/DDK에 포함)를 실행해서 사후에 추가할 수도 있다. `BIND.exe`는 지정된 검색 경로에서 실제 대상 DLL들을 찾아 그 시점의 익스포트 주소와 타임스탬프를 읽어 IAT와 Bound Import Descriptor를 채워 넣는 방식으로 동작한다. 따라서 같은 소스 코드로 빌드된 두 바이너리라도, 바인딩 후처리를 거쳤는지 여부에 따라 Bound Import Directory 유무가 갈릴 수 있다 — 이는 컴파일러 자체의 차이가 아니라 빌드 파이프라인 뒷단의 선택적 단계라는 점을 기억해두면 바이너리를 비교할 때 오해를 줄일 수 있다.

### ASLR 시대에 바인딩의 위치
바인딩은 본질적으로 "DLL이 항상 같은 주소에 로드된다"는 가정에 의존하는데, 이는 ASLR(주소 공간 배치 난수화)의 전제와 정면으로 충돌한다. ASLR이 적용된 최신 시스템 DLL은 매번 다른 주소에 로드되므로 바인딩된 주소가 거의 항상 무효화되고, 결국 대부분의 최신 빌드에서는 Bound Import를 적극적으로 활용하지 않는다. 그래서 이 디렉터리는 오래된 레거시 바이너리, 특정 임베디드/구형 시스템 컴포넌트, 또는 명시적으로 고정 베이스 로딩을 쓰는 특수한 빌드에서 주로 관찰된다.

## 화면/코드에서 보이는 징후
- PE-bear/CFF Explorer의 Directory 목록에 `Bound Import`가 유효한 RVA/Size로 존재
- 정적 분석 중 IAT를 헥스로 열었더니 프로세스를 실행하지 않았는데도 이미 그럴듯한 절대 주소값들이 채워져 있음(단, 이는 "채워질 예정 주소를 미리 계산해둔 것"이지 현재 프로세스에서 실제로 유효한 주소라는 보장은 없음)
- 오래된 Windows 시스템 DLL(특히 초기 버전대)에서 이 디렉터리가 자주 관찰됨
- `IMAGE_BOUND_IMPORT_DESCRIPTOR.TimeDateStamp`가 실제 대상 DLL의 헤더 타임스탬프와 다르면(패치된 시스템 등) 이 정보는 로드 시 그냥 무시됨

## 가장 먼저 할 것
IAT에 이미 값이 채워진 것처럼 보이는 파일을 만나면, 먼저 Bound Import Directory(인덱스 11)가 존재하는지 확인한다. 존재한다면 그 값을 "지금 이 프로세스에서 실제로 유효한 주소"로 신뢰하지 말고, 반드시 실제 로드된 DLL의 타임스탬프와 대조하거나, 디버거로 실행 중 프로세스에서 다시 확인해야 한다.

## 단계별 절차
**1) Bound Import Directory 존재 확인**
`OptionalHeader.DataDirectory[11].VirtualAddress`/`.Size`가 `0`이 아닌지 확인한다.

**2) 디스크립터 배열 순회**
`IMAGE_BOUND_IMPORT_DESCRIPTOR` 배열을 순회하며 각 항목의 `OffsetModuleName`으로 대상 DLL 이름을, `TimeDateStamp`로 바인딩 시점의 대상 DLL 버전을 확인한다.

**3) Forwarder 참조 확인**
`NumberOfModuleForwarderRefs`가 0보다 크면, 뒤따르는 `IMAGE_BOUND_FORWARDER_REF`들을 읽어 실제로 전달되는 최종 DLL까지 파악한다.

**4) 실제 로드 환경과 대조**
분석 대상 DLL의 실제 파일(또는 실행 중 로드된 모듈)의 `FileHeader.TimeDateStamp`를 확인해 바인딩 당시 값과 일치하는지 비교한다. 불일치하면 이 바인딩은 현재 환경에서 무효라는 뜻이다.

## 명령어/단축키
```text
PE-bear: Directories 탭 → Bound Import 항목의 RVA/Size 확인, 파싱된 디스크립터 목록 보기
IDA: 헤더 뷰(Alt+7 계열 서브뷰)에서 Data Directory 배열 확인
CFF Explorer(대안 도구): Directories 탭에서 Bound Import 구조 파싱 결과 확인
```

## 출력 해석
- `TimeDateStamp`가 대상 DLL의 실제 헤더 값과 일치하면 이론상 로더가 조회를 생략하고 바인딩된 IAT 값을 그대로 사용 — 하지만 ASLR 등으로 실제 로드 주소가 바인딩 가정과 다르면 이 최적화는 애초에 무의미
- `NumberOfModuleForwarderRefs`가 0보다 큰데 실제로는 해당 함수들이 포워딩되지 않는 최신 DLL을 쓰고 있다면, 이 파일이 상당히 오래된 시점에 빌드되었음을 짐작할 수 있음(빌드 시대 추정 단서)
- Bound Import가 있으면서 동시에 `.reloc`이 스트립되어 있고(REV-0547) `DllCharacteristics`에 `DYNAMIC_BASE`가 꺼져 있다면, 이 파일은 고정 베이스 로딩을 전제로 설계된 특수한(혹은 오래된) 빌드일 가능성이 큼

## 흔한 실수
- IAT에 미리 채워진 값을 "이 프로세스가 지금 이 주소에 함수가 있다"는 확정된 사실로 오해하는 것 — 이는 어디까지나 바인딩 당시 가정이며, 타임스탬프가 안 맞으면 실제 로드 시 완전히 무시된다.
- Bound Import를 Delay-Load Import(REV-0553)와 혼동하는 것 — 둘은 목적과 동작 시점이 정반대다. Delay-Load는 "로딩을 늦추는" 것이고 Bound Import는 "로딩을 더 빠르게 하기 위해 미리 계산해두는" 것이다.
- 최신 빌드에서 Bound Import가 안 보인다고 해서 이 최적화 개념 자체가 폐기됐다고 생각하는 것 — ASLR과의 충돌 때문에 활용도가 크게 줄었을 뿐, 메커니즘 자체는 여전히 로더에 남아있다.
- `OffsetModuleName`이 디스크립터 배열 시작을 기준으로 한 오프셋이라는 걸 놓치고, 파일 전체 기준 오프셋이나 RVA로 착각해서 잘못된 위치의 문자열을 읽는 것.

## 막혔을 때 다음 체크
- 일반 Import Table 구조와 IAT/INT 개념이 헷갈리면 → [Import Table에서 중요한 API 찾기](./rev-0119-import-table.md)
- 이 최적화가 왜 ASLR과 충돌하는지 재배치 관점에서 더 보고 싶으면 → [.reloc 섹션과 재배치 정보 읽는 법](./rev-0547-reloc-base-relocation.md)
- 로딩을 늦추는 반대 개념(Delay-Load)과 비교하고 싶으면 → [Delay-Load Import 이해하기](./rev-0553-delay-load-import.md)
- 오디널로만 임포트되어 이름이 안 보이는 경우까지 함께 확인하고 싶으면 → [Ordinal Import(이름 없는 Import) 분석법](./rev-0555-ordinal-import.md)

## 미니 예제
오래된 32비트 시스템 유틸리티 하나를 PE-bear로 열었더니 Directories 탭에 `Bound Import`가 유효한 값으로 존재했다. 파싱해보니 `kernel32.dll`에 대한 `IMAGE_BOUND_IMPORT_DESCRIPTOR.TimeDateStamp`가 `0x3B7D8420`으로 기록되어 있었다. 분석 환경의 실제 `kernel32.dll` 헤더 타임스탬프를 확인하니 이후 여러 번의 Windows 업데이트로 값이 완전히 달라져 있었다. 즉 이 바인딩 정보는 이 파일이 빌드되던 당시의 `kernel32.dll` 버전을 가정한 것일 뿐이며, 현재 환경에서 실행하면 로더는 이 값을 무시하고 정상적인 Import Name Table 기반 조회를 다시 수행한다. IAT에 남아있는 옛날 주소값은 오직 "이 파일이 빌드된 시점의 흔적"으로만 유용하고, 실제 실행 시 유효한 주소가 아니다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0553 — Delay-Load Import 이해하기
- REV-0555 — Ordinal Import(이름 없는 Import) 분석법
- REV-0547 — .reloc 섹션과 재배치 정보 읽는 법

## 출처/검증
- `IMAGE_BOUND_IMPORT_DESCRIPTOR`, `IMAGE_BOUND_FORWARDER_REF` 구조체와 Bound Import Directory(인덱스 11) 정의: Microsoft Learn "PE Format" 공식 문서 기준 (2026-09-08 검증).
- 바인딩된 임포트를 로더가 타임스탬프로 검증하고 무효 시 폴백하는 동작: Microsoft PE/COFF 형식 공식 문서 및 다수 리버싱 참고자료 공통 설명 기준.
- ASLR 도입 이후 Bound Import 활용도 감소 배경: Microsoft Learn ASLR 관련 공식 문서의 일반적 설명 기준.
