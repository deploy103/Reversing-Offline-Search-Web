---
id: REV-0958
title: "Import Table이 언패킹 후에도 비어있을 때"
slug: "rev-0958-import-table-empty-after-unpacking"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, "PE-bear", "Detect It Easy"]
keywords: ["IAT 복구 실패", "import table 비어있음", "Scylla Get Imports 실패", "IAT rebuild", "import address table 재구성"]
aliases: ["언패킹 후 import 없음", "IDA imports 탭이 비어있음", "scylla iat autosearch 안됨"]
symptom_keywords: ["IDA로 열었는데 Imports 탭이 비어있음", "Scylla IAT Autosearch가 아무것도 못 찾음", "함수 이름이 하나도 안보이고 sub_만 있음", "언패킹 후에도 API 호출을 알아볼 수 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
언패킹/덤프까지 마쳤는데도 IDA의 Imports 탭이 텅 비어 있거나 Scylla의 `IAT Autosearch`가 아무것도 찾지 못한다면, 대부분 **IAT 위치를 잘못 지정했거나, 패커가 표준 IAT 구조 대신 자체 방식(API 이름 해시, 자체 스텁 호출)으로 함수를 호출하도록 코드를 바꿔놓았기 때문**이다.

## 언제 검색해야 하나
- 덤프한 파일을 IDA로 열었더니 함수 이름이 하나도 없고 전부 `sub_401xxx` 형태의 자동 생성 이름뿐일 때
- Scylla에서 `IAT Autosearch`를 눌렀는데 "OEP not found" 또는 아무 결과 없이 끝날 때
- `Get Imports`를 실행했는데 항목 수가 원본 프로그램이 실제로 쓸 법한 API 개수에 비해 터무니없이 적을 때(예: 2~3개뿐)
- 코드에서 `call [address]` 형태의 간접 호출이 보이는데, 그 주소가 어떤 DLL의 함수인지 IDA가 전혀 인식하지 못할 때

## 핵심 개념

### IAT Autosearch가 실패하는 이유
Scylla의 `IAT Autosearch`는 프로세스 메모리에서 "연속된 함수 포인터 배열처럼 보이는 영역"을 휴리스틱으로 찾는다. 이 방식은 다음과 같은 경우 실패한다.
- 아직 OEP에 정확히 도달하지 않아서 IAT가 채워지는 도중이다(REV-0955, REV-0956 참고).
- 패커가 IAT를 표준적인 연속 배열 형태로 만들지 않고, 함수 주소를 코드 곳곳에 흩어서(inline) 박아 넣었다.
- 패커가 API 호출을 아예 IAT 방식이 아니라 **자체 스텁을 거쳐서** 호출하도록 바꿔놓았다 — 즉 원본 코드는 `call [IAT_entry]`가 아니라 `call packer_stub_wrapper`를 호출하고, 그 wrapper 안에서 실제 API로 점프한다. 이 경우 IAT라는 개념 자체가 원본 형태로 존재하지 않는다.

### API 이름을 해시로 숨기는 경우
일부 패커/프로텍터는 API 이름 문자열을 그대로 저장하지 않고 해시값으로 변환해 저장해 둔다. 런타임에 `LoadLibraryA`로 DLL을 로드한 뒤, 그 DLL이 export하는 모든 함수 이름을 순회하며 해시를 계산해서 원하는 해시값과 일치하는 함수를 찾는다. 이 방식에서는 IAT에 해당하는 표준 구조가 아예 만들어지지 않고, 함수 주소가 계산된 즉시 레지스터나 임시 변수에만 저장되었다가 바로 호출에 쓰인다. 이런 경우 Scylla 같은 범용 IAT 복구 도구로는 애초에 복구할 대상 자체가 없다.

### IAT는 있는데 위치를 못 찾는 경우
IAT 구조 자체는 표준적으로 존재하지만, Scylla가 자동으로 스캔하는 메모리 범위 밖에 있거나(예: 힙 영역에 동적으로 할당됨), 시작 주소를 수동으로 지정해야 하는 경우도 있다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭(`View → Open subviews → Imports`, 또는 `Ctrl+F`로 찾기)이 완전히 비어 있거나 몇 개뿐이다.
- 디스어셈블리에서 `call ds:off_XXXXXX` 또는 `call [rip+0x...]` 형태의 간접 호출이 있는데, 대상 주소에 이름이 붙어 있지 않다.
- Scylla `IAT Autosearch` 결과에 "Nothing found" 또는 매우 적은 수의 항목만 나온다.
- `call`이 항상 같은 하나의 함수(예: 자체 wrapper 함수)로 먼저 가고, 그 함수 안에서 다시 여러 갈래로 분기하는 패턴이 반복된다.

## 가장 먼저 할 것
먼저 x64dbg에서 실제 API 호출이 일어나는 지점(예: `MessageBoxA`가 호출될 것으로 예상되는 곳)에 브레이크포인트를 걸어보고, 호출 직전 스택/레지스터에 찍히는 주소가 어떤 DLL 영역에 속하는지(`Memory Map`에서 해당 주소가 `user32.dll` 범위인지) 확인한다. 이것으로 "IAT가 아예 없는 방식"인지 "IAT는 있는데 못 찾는 것"인지부터 구분한다.

## 단계별 절차
1. Scylla의 `IAT Autosearch`가 실패하면, `Advanced` 옵션에서 시작 주소(IAT Start VA)와 크기를 수동으로 입력해서 재시도한다. OEP 근처 데이터 섹션(`.data`, `.rdata`)의 시작 주소부터 넓게 스캔 범위를 잡아본다.
2. x64dbg의 Memory Map에서 각 DLL이 로드된 주소 범위를 확인해두고, 디스어셈블리에서 간접 호출 대상 주소가 그 범위 안에 들어가는지 하나씩 대조한다. 들어간다면 IAT가 어딘가에 존재하긴 하는 것이므로 위치만 다시 찾으면 된다.
3. 호출 방식이 항상 하나의 공통 wrapper 함수를 거친다면, 그 wrapper 함수 내부를 분석해서 어떤 기준(인덱스, 해시값 등)으로 실제 API를 선택하는지 확인한다. 이 구조라면 Scylla 대신 수동으로 각 호출부에 실제 함수 이름을 주석으로 달아주는 작업이 필요하다.
4. API 이름 해시 방식이 의심되면, `LoadLibraryA`/`GetProcAddress`(또는 이를 대체하는 자체 함수) 호출 직후 반환값(함수 포인터)에 브레이크포인트를 걸어, 실행 중에 그 값이 어떤 함수인지 하나씩 역추적한다. 이는 자동화가 어려우므로 필요한 API만 최소한으로 확인하는 것이 현실적이다.
5. IAT를 어떤 방식으로도 표준 구조로 되살릴 수 없다면, 완전한 정적 분석용 파일을 만드는 것을 포기하고 x64dbg 안에서 직접 호출 지점마다 브레이크포인트를 걸어 동적으로 API를 식별하며 분석을 진행한다(REV-0241 방식).

## 명령어/단축키
- Scylla: `IAT Autosearch` 실패 시 `Advanced` 버튼으로 수동 범위 지정
- x64dbg Memory Map: `Alt+M`(단축키는 버전에 따라 다를 수 있음, 메뉴 `View → Memory Map`으로도 접근)
- x64dbg 간접 호출 대상 확인: 디스어셈블리에서 `call [addr]` 우클릭 → `Follow in Dump` 또는 `Follow in Disassembler`
- IDA: `Ctrl+F`(전체 검색), `Alt+T`(텍스트 검색), Imports 탭은 `View → Open subviews → Imports`

## 출력 해석
- `IAT Autosearch`가 항목 몇 백 개를 찾아냈다면 정상적인 IAT 구조가 존재한다는 뜻이다. 반대로 0개 또는 극소수라면 IAT 자체가 표준 형태로 없다는 강한 신호다.
- Memory Map에서 확인한 DLL 주소 범위와 코드의 호출 대상 주소가 일치한다면, IAT는 어딘가 존재하지만 자동 스캔 범위 밖에 있는 것뿐이다.
- 호출이 항상 같은 wrapper 함수로 모인다면, 이는 "IAT가 없는 게 아니라 간접 호출을 한 겹 더 감싼 것"이므로 wrapper 함수 하나만 분석하면 나머지 호출 전체를 이해할 수 있다.

## 흔한 실수
- IAT Autosearch가 실패하면 바로 "언패킹이 잘못됐다"고 결론짓고 OEP부터 다시 찾는 것 — IAT 문제와 OEP 문제는 별개일 수 있다.
- wrapper 함수를 통한 간접 호출 구조를 발견하고도, 그 안을 분석하지 않고 계속 IAT 복구 도구만 반복 실행하는 것.
- API 이름 해시 방식임을 확인하고도 모든 API를 완벽히 복구하려고 시간을 다 쓰는 것 — CTF 맥락에서는 실제로 로직에 필요한 몇 개 API만 확인하면 충분한 경우가 많다.
- 덤프 시점(OEP)이 잘못되어 IAT가 아직 덜 채워진 상태라는 가능성을 배제하고 시작하는 것 — 먼저 REV-0956의 OEP 재검토부터 하는 것이 순서상 맞다.

## 막혔을 때 다음 체크
- OEP 자체가 의심된다면 → REV-0956(OEP를 찾았는데 실행이 이상하게 될 때)을 먼저 확인한다.
- 덤프 파일이 이 문제 때문에 계속 크래시가 난다면 → REV-0955(언패킹한 덤프가 크래시가 날 때)를 참고한다.
- 완전한 정적 분석 파일을 포기하고 동적 분석으로 전환하는 판단 기준이 필요하다면 → REV-0241(패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환)을 참고한다.

## 미니 예제
```text
1) Scylla IAT Autosearch 실행 -> "Nothing found!"
2) x64dbg Memory Map 확인
   -> user32.dll: 0x6F800000 - 0x6F8B0000
3) 디스어셈블리에서 call [0x00403010] 발견, Follow in Dump
   -> 0x00403010의 값 = 0x6F823A50 (user32.dll 범위 안)
4) IAT는 존재하지만 Scylla가 인식하는 표준 위치에 있지 않다고 판단
5) Scylla Advanced에서 IAT Start VA를 0x00403000, Size를 0x200으로 수동 지정
6) IAT Autosearch 재시도 -> 40개 항목 발견, Get Imports 정상 동작
```

## 관련 글
- REV-0955 — 언패킹한 덤프가 크래시가 날 때
- REV-0956 — OEP를 찾았는데 실행이 이상하게 될 때
- REV-0241 — 패커와 난독화 때문에 디컴파일이 틀릴 때 정적/동적 전환

## 출처/검증
- Scylla의 IAT Autosearch 휴리스틱과 수동 범위 지정 기능: Scylla 공식 저장소(github.com/NtQuery/Scylla) 문서 기준(2026-09-09 검증).
- API 이름 해시 기반 동적 함수 resolve 기법은 다수의 공개 멀웨어/프로텍터 분석 자료에서 공통적으로 설명하는 일반적 기법을 정리한 것이며, 실제 해시 알고리즘은 패커마다 다르므로 개별 분석이 필요하다.
