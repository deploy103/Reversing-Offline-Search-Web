---
id: REV-0945
title: "언패킹 후 IAT를 복구하는 개념(Import Reconstruction)"
slug: "rev-0945-iat-reconstruction-concept"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["IAT 복구", "Import Reconstruction", "Scylla", "ImpREC", "IAT Autosearch", "Fix Dump", "import table 재구성"]
aliases: ["scylla 사용법", "iat 복구 어떻게 해", "import reconstruction 개념", "덤프한 파일 실행 안됨 iat"]
symptom_keywords: ["덤프한 파일이 실행이 안됨", "IDA에 열었더니 import가 하나도 없음", "scylla get imports invalid", "fix dump 후에도 크래시"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
REV-0227/REV-0944로 OEP를 찾아 메모리를 덤프해도, 덤프된 파일의 IAT(Import Address Table)는 함수 주소만 채워져 있고 "어느 DLL의 어느 함수인지"를 가리키는 정상 구조가 없는 상태이므로, Scylla 같은 도구로 IAT 위치를 찾고(IAT Autosearch) 각 주소를 함수 이름으로 되돌린 뒤(Get Imports) 파일에 새로 써넣는(Fix Dump) 3단계 과정을 거쳐야 실행 가능한 파일이 된다.

## 언제 검색해야 하나
- OEP를 찾아 메모리 덤프까지는 했는데 그 파일을 실행하면 바로 크래시가 날 때
- IDA/Ghidra로 덤프 파일을 열었더니 Imports 창이 텅 비어 있거나 함수 이름이 하나도 안 붙어 있을 때
- "IAT 복구", "Import Reconstruction"이라는 용어를 봤는데 정확히 뭘 복구하는 것인지 개념이 헷갈릴 때
- Scylla를 처음 써보는데 `IAT Autosearch`, `Get Imports`, `Fix Dump` 버튼이 각각 뭘 하는지 모를 때

## 핵심 개념

### 정상 실행 파일의 IAT는 무엇을 담고 있나
정상적으로 컴파일된 PE 파일은 Import Directory에 "이 프로그램이 `kernel32.dll`의 `CreateFileA`를 쓴다"는 식의 정보가 (DLL 이름, 함수 이름 또는 ordinal) 쌍으로 저장되어 있다. 로더(`ntdll.dll`)는 프로그램 시작 전에 이 목록을 읽어, 각 DLL을 메모리에 매핑하고 실제 함수 주소를 계산해서 IAT라는 메모리 영역(주소 배열)에 채워 넣는다. 실행 중인 프로그램의 코드는 `call [IAT_slot]` 형태로 이 배열을 통해 간접 호출을 한다.

### 패킹된 프로그램은 왜 이 정보를 감추는가
많은 패커/프로텍터는 압축을 풀거나 보호를 적용하는 과정에서, 원본 Import Directory를 사용하지 않고 스텁 코드가 직접 `LoadLibraryA`와 `GetProcAddress`를 호출해서 필요한 함수 주소를 알아낸 뒤 자기만의 IAT 영역에 채워 넣는다(REV-0229). 이렇게 하면 디스크 파일만 봐서는 "이 프로그램이 무슨 API를 쓰는지" 알기 어려워진다.

### 덤프 시점의 상태
OEP에서 메모리를 덤프하면, 그 시점에는 이미 스텁이 IAT 슬롯에 실제 함수 주소(예: `kernel32.dll`의 `CreateFileA`가 매핑된 실제 가상 주소)를 다 채워놓은 상태다. 문제는 그 주소가 **숫자로만** 존재하고, PE 헤더의 Import Directory에는 "이 슬롯이 어느 DLL의 어느 함수인지"를 알려주는 원래 정보가 없다(패커가 원본 Import Directory 자체를 지우거나 변형했기 때문). 그래서:

- 그 값 자체는 유효한 함수 포인터이므로 프로그램은 원래 환경에서 계속 실행될 수는 있다.
- 하지만 파일을 디스크에 다시 쓰고 다른 컴퓨터에서 실행하면, 그 주소는 그 컴퓨터에서는 의미 없는 값이 된다(DLL이 매번 같은 주소에 로드된다는 보장이 없다). 로더가 IAT를 다시 채워주려 해도 참조할 Import Directory 정보가 없으므로 크래시가 난다.

### Import Reconstruction의 3단계
1. **IAT 위치 찾기(IAT Autosearch)**: 메모리 안에서 "연속으로 유효한 함수 주소들이 배열처럼 나열된 영역"을 찾는다. Scylla는 덤프한 프로세스의 메모리를 스캔해서 이런 패턴을 자동으로 찾아준다.
2. **각 주소를 이름으로 되돌리기(Get Imports)**: 찾아낸 각 주소가 실제로 어느 DLL의 어느 함수(export)에 해당하는지 시스템에 로드된 DLL들의 export 테이블과 대조해서 알아낸다.
3. **파일에 다시 써넣기(Fix Dump)**: 알아낸 DLL/함수 이름 목록으로 정상적인 Import Directory 구조를 새로 만들어 덤프 파일에 추가하고, 코드가 참조하는 IAT 슬롯 주소도 이 새 구조를 가리키도록 재배치한다.

이 세 단계를 거치면 덤프 파일은 이제 "다른 컴퓨터에서 실행해도 로더가 정상적으로 Import를 다시 채워줄 수 있는" 일반 PE 파일이 된다.

## 화면/코드에서 보이는 징후
- 덤프 파일을 IDA에 열면 Imports 창이 비어 있거나 극소수(`LoadLibraryA`, `GetProcAddress`만)만 보임
- 덤프 파일 실행 시 `Access violation` 또는 즉시 종료
- Scylla의 `IAT Autosearch` 실행 시 "IAT found at ..." 메시지와 함께 시작 주소/크기가 표시됨
- `Get Imports` 실행 후 각 항목이 `kernel32.dll!CreateFileA`처럼 이름으로 채워지거나, 일부가 `??? (invalid)`로 표시됨

## 가장 먼저 할 것
덤프 파일을 실행하기 전에 먼저 IDA/Ghidra의 Imports 창부터 확인해서 정말 비어있는지 확인한다. 비어있다면 Scylla를 실행해 현재 실행 중인(아직 종료하지 않은) 프로세스를 대상으로 IAT Autosearch부터 시작한다 — 프로세스가 이미 종료된 뒤에는 이 방법을 쓸 수 없으므로, 덤프와 IAT 복구는 같은 디버깅 세션 안에서 연속으로 진행해야 한다.

## 단계별 절차
1. OEP에서 프로세스를 정지시킨 상태 유지(REV-0944)
2. x64dbg에서 `Plugins → Scylla` 실행
3. Scylla 창에서 `IAT Autosearch` 클릭, 찾은 IAT 시작 주소/크기 확인
4. `Get Imports` 클릭, 각 항목이 이름으로 채워지는지 확인
5. `invalid`로 표시되는 항목이 있으면 우클릭 → `Cut Thunk` 등으로 제외하거나, 크기를 수동 조정해 재시도
6. `Fix Dump` 클릭, 아까 덤프해둔 파일(또는 Scylla의 `Dump` 기능으로 새로 뜬 파일)을 선택해 Import Directory를 새로 써넣음
7. 결과 파일을 IDA/Ghidra로 다시 열어 Imports 창 확인
8. 가능하면 실제로 실행해 원본과 같은 동작을 하는지 검증

## 명령어/단축키
- x64dbg: `Plugins → Scylla`
- Scylla: `IAT Autosearch`, `Get Imports`, `Fix Dump` 버튼(창 내 순서대로 배치됨)
- Scylla `Dump` 버튼: OEP 프로세스의 메모리를 파일로 저장(REV-0944에서 만든 덤프와 별개로 여기서 새로 뜰 수도 있음)

## 출력 해석
- `Get Imports` 결과에서 대부분 이름이 붙고 소수만 `invalid`라면, invalid 항목은 실제로 사용되지 않는 여분 슬롯이거나 IAT 크기를 잘못 잡은 경우다 — 크기를 줄여 재시도한다.
- 거의 전부 `invalid`라면 IAT Autosearch가 엉뚱한 영역을 찾은 것이다 — OEP를 잘못 잡았거나(너무 이른 시점), 수동으로 IAT 시작 주소를 지정해 다시 시도해야 한다.
- `Fix Dump` 완료 메시지 후 결과 파일 크기가 원본 덤프보다 약간 커지는 것은 정상이다(새 Import Directory 섹션이 추가되기 때문).

## 흔한 실수
- 프로세스를 먼저 종료하고 나서 Scylla를 실행하려는 것 — IAT Autosearch는 살아있는 프로세스의 메모리를 스캔하는 기능이므로 반드시 OEP에서 멈춘 상태를 유지해야 한다.
- `invalid` 항목이 하나라도 있으면 전체가 실패했다고 단정하는 것 — 소수의 invalid는 Cut Thunk로 제외하고 진행해도 되는 경우가 많다.
- Fix Dump에 원본 압축 파일을 잘못 지정해서 아무 변화 없는 것처럼 보이는 것 — 반드시 OEP 시점에 덤프한 파일을 지정해야 한다.
- IAT 복구 없이 그냥 덤프 파일을 실행해보고 "언패킹 실패"로 결론짓는 것 — IAT가 깨진 상태에서의 크래시는 정상적인 중간 단계다.

## 막혔을 때 다음 체크
- Scylla 같은 GUI 도구가 없거나 자동 탐지가 계속 실패한다면 → REV-0946 도구 없이 수동으로 Import 복구하는 개념
- OEP 자체가 의심스럽다면 → REV-0944 OEP 수동 추적 절차 심화로 돌아가 재확인
- .NET 바이너리라서 애초에 이 native IAT 개념이 안 맞는 것 같다면 → REV-0951 패킹된 .NET 바이너리 기초
- Import가 아예 재구성이 안 될 만큼 프로텍터가 강력하다면 → REV-0942 상용 프로텍터를 만났을 때 현실적인 대응

## 미니 예제
```text
Scylla 창:
  IAT Autosearch  -> "IAT found at 0x00403000, size 0x120"
  Get Imports     -> kernel32.dll!CreateFileA
                     kernel32.dll!ReadFile
                     kernel32.dll!WriteFile
                     user32.dll!MessageBoxA
                     ??? (invalid)          <- 1개는 실제 미사용 슬롯으로 판단, Cut Thunk
  Fix Dump        -> dumped_00400000.exe 선택 -> "Success!"
```
`Fix Dump` 성공 후 결과 파일(`dumped_00400000_SCY.exe` 형태로 저장됨)을 IDA에 열면 Imports 창에 `CreateFileA`, `ReadFile`, `WriteFile`, `MessageBoxA`가 정상적으로 나타난다.

## 관련 글
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0944 — 패킹된 바이너리에서 OEP를 수동으로 추적하는 절차 심화
- REV-0946 — 도구 없이 수동으로 Import 복구하는 개념
- REV-0229 — Import가 거의 없는 PE를 봤을 때

## 출처/검증
- Scylla의 IAT Autosearch/Get Imports/Fix Dump 동작 방식은 Scylla 공식 저장소(github.com/NtQuery/Scylla) 문서 및 x64dbg 공식 문서(help.x64dbg.com)의 플러그인 설명을 기준으로 정리했다(2026-09-09 검증).
- IAT/Import Directory의 로더 동작 원리는 Microsoft PE Format 공식 문서(Portable Executable Format)를 기준으로 확인했다.
