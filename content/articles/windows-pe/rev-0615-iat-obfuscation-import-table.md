---
id: REV-0615
title: "Import Table이 이상하게 재구성되어(IAT 난독화) 분석이 막힐 때"
slug: "rev-0615-iat-obfuscation-import-table"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg, Scylla, "Detect It Easy"]
keywords: ["IAT 난독화", "Import Address Table", "Scylla", "ImpREC", "GetProcAddress", "API 해시", "IAT AutoSearch"]
aliases: ["임포트 재구성", "IAT 리빌드", "API 해시 난독화", "Import Table 복구"]
symptom_keywords: ["Imports 탭에 함수가 거의 없다", "임포트가 이상한 주소를 가리킨다", "IDA가 API 이름을 못 찾는다", "패커가 임포트를 지운 것 같다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
Import 테이블이 텅 비어 있거나(패커/프로텍터가 원본 임포트를 지워버림), 항목은 있는데 실제로는 진짜 API가 아니라 패커 자체 코드나 트램폴린 스텁을 가리키고 있다면(IAT 후킹/스텁형 난독화), IDA에서 정적으로는 해결이 안 되므로 x64dbg에서 프로그램을 실제 진입점(OEP)까지 실행시킨 뒤 **Scylla**로 메모리에서 임포트를 다시 스캔·재구성(Import Table Reconstruction)하는 것이 표준적인 해결책이다.

## 언제 검색해야 하나
- IDA로 열었을 때 Imports 탭에 API가 거의 없거나(`kernel32.dll`의 `LoadLibraryA`/`GetProcAddress` 한두 개 정도만) 원래 있어야 할 API들이 안 보일 때
- Detect It Easy로 열면 패커/프로텍터(UPX, VMProtect, Themida 등) 시그니처가 뜨고, 그 뒤로 진짜 임포트가 숨겨져 있을 것으로 의심될 때
- x64dbg에서 IAT 영역을 확인했더니 각 슬롯이 가리키는 주소가 `kernel32.dll`/`user32.dll` 같은 정상 모듈 범위가 아니라, 패커 자신의 코드 섹션 안쪽 주소를 가리키고 있을 때

## 핵심 개념
정상적인 PE 파일의 Import Address Table(IAT)은 로더가 프로그램 실행 전에 미리 채워 넣는 함수 포인터 배열이다. 코드에서 `call [IAT_슬롯]` 형태로 호출하면, 그 슬롯에는 이미 `kernel32.dll!CreateFileW` 같은 실제 API의 최종 주소가 들어있어서 바로 그 API로 점프한다. IDA는 Import 디렉터리(`IMAGE_DIRECTORY_ENTRY_IMPORT`)의 이름 정보를 이용해 이 슬롯들에 자동으로 `CreateFileW` 같은 이름을 붙여주기 때문에, 정상적인 파일이라면 Imports 탭만 봐도 이 프로그램이 어떤 API를 쓰는지 한눈에 보인다.

패커/프로텍터는 정적 분석을 어렵게 만들기 위해 이 구조를 여러 방식으로 망가뜨린다.

- **임포트 자체를 지워버리기**: 원본 Import 디렉터리를 통째로 비우고, 실행 시점에 언패킹 스텁이 직접 `LoadLibraryA`/`GetProcAddress`를 호출해 필요한 API 주소를 알아낸 뒤 자체적으로 만든 IAT에 채워 넣는다. 이 경우 정적 Import 테이블에는 `LoadLibraryA`, `GetProcAddress` 정도의 최소한의 함수만 보인다.
- **API 이름을 해시로 대체**: 문자열 `"CreateFileW"`를 그대로 두지 않고 이 이름의 해시값(CRC32 등)만 코드에 심어두고, 런타임에 각 DLL의 export 이름을 하나씩 해시해서 값이 일치하는 함수를 찾는 방식. 이렇게 하면 문자열 검색으로도 API 이름을 알 수 없다.
- **IAT 슬롯이 실제 API가 아니라 자체 스텁을 가리키게 하기**: IAT 항목은 존재하지만, 그 값이 진짜 `kernel32.dll` 안이 아니라 패커가 삽입한 작은 트램폴린 코드(몇 바이트짜리 `jmp`)를 가리키고, 그 트램폴린이 실제 API로 다시 점프하는 간접 구조. 이는 API 후킹이나 추가 안티디버깅 체크를 끼워 넣기 위한 목적으로도 쓰인다.

이런 상태에서는 IDA가 각 호출을 `CreateFileW`처럼 사람이 읽을 수 있는 이름으로 보여주지 못하고, `call dword_403010` 같은 의미 없는 주소로만 보여준다. 해결의 핵심은, "패커가 다 풀어놓아서 진짜 IAT가 메모리에 완성되는 시점"까지 프로그램을 실제로 실행시킨 뒤, 그 순간의 메모리 상태를 스캔해서 IAT를 재구성하는 것이다.

## 화면/코드에서 보이는 징후
- IDA Imports 탭에 함수가 극히 적음(정상적인 GUI/콘솔 프로그램인데 10개 미만)
- Detect It Easy로 열면 상단에 UPX, ASPack, VMProtect, Themida, .NET Reactor 등 패커/프로텍터 이름이 표시됨
- x64dbg에서 실행 중 IAT로 추정되는 메모리 영역의 값들을 따라가 보면, 정상 DLL 모듈 범위 밖의 주소(패커 자신의 섹션)를 가리킴
- `.text` 섹션 외에 `UPX0`, `UPX1`처럼 표준과 다른 이름의 섹션이 있거나, 섹션 엔트로피가 7.5~8.0에 가깝게 매우 높음(압축/암호화 흔적)

## 가장 먼저 할 것
1. Detect It Easy로 파일을 열어 어떤 패커/프로텍터가 쓰였는지부터 식별한다. 알려진 패커라면 전용 언패킹 스크립트나 플러그인이 이미 존재할 수 있다.
2. x64dbg로 파일을 로드하고, 패커의 언패킹 루틴이 끝나고 원본 코드로 넘어가는 지점(Original Entry Point, OEP)을 찾는다. 흔한 방법은 스택에 있는 값들을 감시하다가 `PUSHAD` 이후 `POPAD`가 나오는 지점, 혹은 메모리 접근 브레이크포인트(패킹된 원본 섹션에 쓰기가 끝나고 실행이 그쪽으로 넘어가는 순간)를 활용하는 것이다.
3. OEP에 도달한 시점(진짜 코드가 막 실행되려는 순간)에서 x64dbg에 내장된 **Scylla** 플러그인을 열어 임포트 재구성을 시작한다.

## 단계별 절차
**1) OEP 도달**
- 패커 종류에 따라 다르지만, 흔히 쓰이는 방법은 마지막 큰 점프(언패킹 스텁에서 원본 코드로 넘어가는 `JMP`)를 찾아 그 직후에 브레이크포인트를 거는 것이다. ESP를 이용한 방법(`Track EIP into new stack frame`으로 최초 `PUSHAD` 직후 스택 주소에 하드웨어 브레이크포인트를 걸어, 이후 그 값을 `POP`하는 지점, 즉 `POPAD` 직후를 찾는 방식)도 널리 쓰인다.

**2) Scylla로 IAT AutoSearch**
- OEP에서 실행을 멈춘 채로 x64dbg 상단 메뉴에서 Scylla 플러그인을 연다.
- `IAT Info` 항목에 OEP 주소를 입력하고 `IAT AutoSearch`를 누르면, Scylla가 현재 프로세스 메모리를 스캔해 IAT로 추정되는 영역을 자동으로 찾아준다.
- 이어서 `Get Imports`를 누르면 해당 영역의 각 슬롯 값이 실제로 어느 DLL의 어느 함수 주소인지 역으로 매칭해 이름을 복원한다. Scylla는 직접 스캔 방식(`LEA`, `MOV`, `PUSH`, `CALL`, `JMP` 명령의 오퍼랜드까지 추적)도 지원해 스텁을 거치는 간접 참조도 상당수 잡아낼 수 있다.

**3) 덤프 및 Fix Dump**
- Scylla의 `Dump` 기능으로 현재 메모리 상태(이미 언패킹된 코드)를 파일로 저장한다.
- 그 다음 `Fix Dump`를 눌러, 방금 복원한 임포트 정보를 바탕으로 덤프한 파일의 Import 디렉터리를 새로 만들어준다(내부적으로 `.SCY`라는 새 섹션을 추가해 새 IAT/IDT를 심는다). 이렇게 나온 파일은 독립적으로 실행 가능한 언패킹된 PE 파일이 된다.

**4) IDA에서 재분석**
- Fix Dump로 만들어진 파일을 IDA로 다시 열면, 이번에는 Imports 탭에 정상적인 API 이름들이 채워져 있어 정적 분석이 훨씬 수월해진다.

## 명령어/단축키
- x64dbg: 하드웨어 브레이크포인트로 OEP 추적, `Ctrl+F9`(함수 반환까지 실행), Scylla 플러그인 메뉴 진입
- Scylla: `IAT AutoSearch` → `Get Imports` → `Dump` → `Fix Dump` 순서
- Detect It Easy: 파일 열면 자동으로 패커/컴파일러 시그니처 표시

## 출력 해석
- Scylla의 `Get Imports` 결과 목록에서 함수 이름 옆에 `Valid:Yes`로 표시되면 정상적으로 매칭된 것이고, `Valid:No`(빨간색)로 표시되면 해당 슬롯이 알려진 API 주소와 일치하지 않아 수동으로 확인이 필요하다는 뜻이다.
- 일부 항목이 계속 `Invalid`로 남는다면 그 슬롯이 실제로는 API가 아니라 패커 내부 데이터이거나, 흔치 않은 API(다른 모듈에서 동일 주소를 export하는 경우 등)일 수 있다.

## 흔한 실수
- OEP를 정확히 찾지 못한 채(언패킹이 아직 덜 끝난 시점) Scylla로 IAT를 스캔해서, 불완전하거나 잘못된 임포트 목록을 얻는 것. 반드시 원본 코드가 실행되기 직전 시점을 정확히 잡아야 한다.
- `Fix Dump`까지 마친 파일을 원본과 동일하다고 착각하는 것. 일부 특수한 보호 기법(코드 자체 수정, 안티덤프)이 있는 경우 단순 덤프로는 완전히 복원되지 않을 수 있다.
- IAT 난독화와 API 해시 난독화를 혼동하는 것. Scylla는 IAT 슬롯 매칭에는 강하지만, 코드 안에 심어진 API 이름 해시값 자체를 해독해주지는 않으므로, 해시 기반 동적 API 로딩까지 쓰인 경우에는 코드 레벨 분석이 추가로 필요하다.

## 막혔을 때 다음 체크
- Import Table의 기본 구조 자체를 다시 확인하고 싶다면 → REV-0119(Import Table에서 중요한 API 찾기)를 확인한다.
- `GetProcAddress`/`LoadLibrary`를 이용한 동적 API 로딩 패턴이 헷갈린다면 → REV-0129(GetProcAddress LoadLibrary)를 확인한다.
- 패커/프로텍터 여부를 먼저 식별하고 싶다면 → REV-0126(DIE 기초)를 확인한다.

## 미니 예제
`packed.exe`를 IDA로 열었더니 Imports 탭에 `kernel32.dll`의 `LoadLibraryA`, `GetProcAddress` 두 개만 보였다. Detect It Easy로 확인해보니 UPX로 패킹되어 있었다. x64dbg로 로드해 `ESP` 기반 방법으로 `PUSHAD` 직후 스택 주소에 하드웨어 브레이크포인트를 걸고 실행하니, 언패킹이 끝나는 지점에서 `POPAD` 직후 멈췄고 바로 다음에 원본 OEP로 향하는 큰 `JMP` 명령이 보였다. 이 `JMP`를 실행해 OEP에 도달한 뒤 Scylla를 열어 `IAT AutoSearch` → `Get Imports`를 실행하니, `CreateFileW`, `ReadFile`, `RegOpenKeyExW` 등 원래 프로그램이 쓰던 40여 개의 API가 모두 정상 이름으로 복원되었다. `Dump` 후 `Fix Dump`로 저장한 파일을 다시 IDA로 열자 이제 Imports 탭이 완전하게 채워져 있었다.

## 관련 글
- REV-0119 — Import Table에서 중요한 API 찾기
- REV-0129 — GetProcAddress LoadLibrary 동적 API 해석
- REV-0126 — Detect It Easy로 컴파일러 패커 확인

## 출처/검증
- Scylla가 실행 중인 프로세스 메모리에서 IAT를 스캔(`IAT AutoSearch`)하고 각 슬롯을 실제 API 주소와 매칭(`Get Imports`)한 뒤 `Fix Dump`로 새 Import 디렉터리를 심어주는 동작 방식은 Scylla 공식 저장소(NtQuery/Scylla, x64dbg/Scylla) 및 관련 언패킹 튜토리얼 자료 기준이다.
- 패커가 원본 Import 테이블을 비우고 런타임에 `LoadLibraryA`/`GetProcAddress`로 API를 직접 찾아 IAT를 채우거나, API 이름을 해시로 대체하는 기법은 다수의 패킹/언패킹 관련 리버스 엔지니어링 자료 및 악성코드 분석 라이트업에서 공통적으로 확인되는 패턴이다(2026-09-08 기준 서술).
