---
id: REV-0946
title: "도구 없이 수동으로 Import 복구하는 개념"
slug: "rev-0946-manual-import-reconstruction-no-tools"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg]
keywords: ["수동 IAT 복구", "Scylla 없이 import 복구", "GetProcAddress 주소로 함수 찾기", "export 테이블 대조", "IAT 손수 재구성"]
aliases: ["scylla 없을때 iat 복구", "수작업 import reconstruction", "export table 대조법", "함수 주소로 이름 찾기"]
symptom_keywords: ["scylla가 실행이 안됨", "get imports가 계속 invalid만 나옴", "iat autosearch가 이상한 영역을 찾음", "직접 iat 만들어야함"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Scylla 같은 자동화 도구가 없거나 자동 탐지가 특이한 스텁 구조 때문에 실패할 때는, IAT 슬롯에 들어있는 각 주소를 손으로 하나씩 DLL의 export 주소 목록과 대조해서 함수 이름을 알아내고, 그 결과를 참고용 매핑표로 남겨 코드 분석에 활용하는 수작업 절차로 대체할 수 있다.

## 언제 검색해야 하나
- REV-0945에서 Scylla를 시도했는데 IAT Autosearch가 계속 엉뚱한 영역을 찾거나 실패할 때
- 분석 환경에 Scylla/ImpREC 같은 GUI 도구를 설치할 수 없는 제약이 있을 때(오프라인 대회 환경 등)
- IAT 복구의 원리 자체를 이해하고 싶어서 자동 도구 뒤에서 실제로 무슨 계산이 일어나는지 알고 싶을 때
- 완전한 실행 파일 재구성까지는 필요 없고, 그냥 "이 함수 포인터가 어떤 API인지"만 알면 되는 상황일 때

## 핵심 개념

### 자동 도구가 하는 일을 손으로 그대로 재현하기
Scylla의 `Get Imports`가 내부적으로 하는 일은 사실 단순하다. IAT 슬롯에 들어있는 각 값(가상 주소)에 대해:

1. 그 주소가 어느 DLL이 매핑된 범위 안에 속하는지 확인한다(예: `kernel32.dll`이 `0x76F00000~0x76FE0000`에 매핑되어 있다면, 그 범위 안의 주소는 kernel32의 export일 가능성이 높다).
2. 해당 DLL의 export 테이블(EAT, Export Address Table)을 순회하면서 같은 주소를 가진 export 항목을 찾는다.
3. 일치하는 export의 이름을 가져와 그 IAT 슬롯의 이름으로 붙인다.

이 과정은 x64dbg의 기본 기능만으로도 手動 재현이 가능하다.

### 필요한 정보
- **IAT로 추정되는 메모리 영역**: REV-0944에서 확인한 IAT 후보 주소 범위. 특징은 연속으로 유효한 코드/함수 주소가 배열처럼 나열되어 있다는 점이다(각 슬롯이 4바이트(x86) 또는 8바이트(x64) 간격으로 유효한 포인터를 담고 있음).
- **각 로드된 DLL의 메모리 매핑 범위**: x64dbg의 Memory Map 탭(`Alt+M`)에서 `kernel32.dll`, `user32.dll`, `ntdll.dll` 등이 어느 주소 범위에 매핑되어 있는지 확인한다.
- **각 DLL의 export 목록**: x64dbg의 Symbols 탭(`Alt+S`)에서 특정 모듈을 선택하면 그 모듈이 내보내는(export) 함수 이름과 주소 목록을 볼 수 있다.

### 수작업 절차
1. Dump 창에서 IAT 후보 영역을 연다.
2. 슬롯을 하나씩(4/8바이트 단위) 읽어 주소 값을 기록한다.
3. 그 주소가 Memory Map에서 어느 모듈 범위에 속하는지 확인한다.
4. Symbols 탭에서 해당 모듈을 열고, 같은 주소를 가진 export 이름을 찾아 슬롯 옆에 라벨을 붙인다(x64dbg는 이미 알려진 주소라면 Dump 창에 자동으로 `<kernel32.CreateFileA>` 같은 코멘트를 붙여주기도 한다).
5. 슬롯 전체를 이렇게 매핑해서 표로 정리한다(주소 → DLL.함수명).
6. 이 매핑표를 참고하며 코드 분석(IDA/Ghidra에서 `call [IAT_slot]`을 만날 때마다 표를 대조해 실제 함수를 파악)에 활용한다.

### 완전한 파일 재구성이 필요한가?
CTF/실무 대부분의 목표는 "코드가 어떤 API를 쓰는지 아는 것"이지, "완벽하게 실행 가능한 새 PE 파일을 만드는 것" 자체가 아니다. 매핑표만 만들어도 IDA에서 각 `call` 지점에 수동으로 이름을 붙여(`N` 키로 rename, 또는 코멘트 추가) 분석을 계속 진행할 수 있다. 완전한 파일 재구성(Import Directory를 실제로 새로 써서 다른 컴퓨터에서도 실행 가능하게 만드는 것)이 꼭 필요한 경우에만 REV-0945의 Fix Dump 수준 작업이 필요하다.

## 화면/코드에서 보이는 징후
- x64dbg Dump 창에서 IAT 후보 영역의 각 슬롯 오른쪽에 이미 `<kernel32.CreateFileA>`처럼 자동 코멘트가 붙어 있는 경우가 많음(x64dbg가 내부적으로 심볼을 미리 로드해두기 때문)
- Memory Map 탭에서 여러 DLL이 각기 다른 주소 범위에 매핑되어 있는 것을 확인 가능
- Symbols 탭에서 모듈 선택 시 수백~수천 개의 export 이름과 주소 나열

## 가장 먼저 할 것
x64dbg Dump 창에서 IAT 후보 영역을 먼저 살펴본다. 의외로 x64dbg가 이미 각 슬롯 옆에 함수 이름 코멘트를 자동으로 붙여준 상태일 수 있다 — 이 경우 별도 도구 없이 눈으로 보는 것만으로 매핑표가 거의 완성된다.

## 단계별 절차
1. `Alt+M`으로 Memory Map 열어 로드된 DLL과 주소 범위 확인
2. IAT 후보 영역을 Dump 창에서 열기(`Ctrl+G`로 주소 이동)
3. 슬롯별 값과 x64dbg 자동 코멘트 확인
4. 코멘트가 없는 슬롯은 값을 복사해 Memory Map에서 속한 모듈 확인
5. `Alt+S`(Symbols)에서 해당 모듈 선택, 같은 주소의 export 검색(Symbols 창 필터에 주소나 함수명 일부 입력)
6. 매핑 결과를 텍스트로 정리(주소, 모듈, 함수명)
7. IDA/Ghidra에서 해당 `call [addr]` 지점마다 이름 라벨 부여

## 명령어/단축키
- x64dbg: `Alt+M`(Memory Map), `Alt+S`(Symbols), `Ctrl+G`(Dump로 주소 이동)
- Dump 창 우클릭 → `Follow in Disassembler`로 해당 주소의 코드 확인
- Symbols 탭 검색창에 주소 입력 시 근접 export 자동 필터링

## 출력 해석
- Dump 창의 자동 코멘트가 `<kernel32.CreateFileA>`처럼 나오면 이미 이름이 확정된 것이다.
- 코멘트가 없고 주소만 있는 슬롯은 아직 로드되지 않은 DLL의 함수이거나, IAT 영역이 아닌 다른 데이터일 수 있다 — Memory Map으로 재확인이 필요하다.
- 어떤 슬롯 값이 로드된 어떤 DLL 범위에도 속하지 않는다면, 그 슬롯은 IAT가 아니라 다른 종류의 포인터 테이블(예: vtable, 내부 함수 테이블)일 가능성이 있다.

## 흔한 실수
- IAT 후보 영역을 잘못 잡아서 (예: 실제로는 전역 변수 배열인 것을 IAT로 착각) export와 대조해도 하나도 안 맞는데 계속 그 영역만 붙잡고 있는 것.
- x64dbg가 이미 자동으로 코멘트를 붙여준 것을 못 보고 하나하나 수작업으로 다시 확인하며 시간을 낭비하는 것.
- 매핑표를 텍스트로 남기지 않고 머릿속으로만 기억하려다 나중에 다시 헷갈리는 것 — 반드시 표로 기록해둔다.
- 완전한 실행 파일 재구성이 필요하지도 않은데 무리하게 Import Directory를 손으로 다시 쓰려고 시도하는 것 — 코드 분석만이 목표라면 매핑표로 충분하다.

## 막혔을 때 다음 체크
- 매핑표 작성 후에도 실행 가능한 파일까지 만들어야 한다면 → REV-0945 IAT 복구 개념(Scylla의 Fix Dump 활용)으로 다시 시도
- IAT 후보 영역 자체가 확실하지 않다면 → REV-0944 OEP 수동 추적 절차 심화에서 IAT 위치 추정 방법 재확인
- 애초에 이 바이너리가 특이하게 IAT를 아예 안 쓰는 구조(직접 함수 포인터를 계산해서 호출)라면 → REV-0943 커스텀 패커 알아보는 단서 참고

## 미니 예제
```text
Memory Map:
  kernel32.dll   0x76F00000 - 0x76FE0000
  user32.dll     0x77100000 - 0x771A0000

IAT 후보 영역(0x00403000):
  0x00403000: 0x76F12345   -> Memory Map: kernel32.dll 범위
                             -> Symbols(kernel32.dll) 대조 -> CreateFileA
  0x00403004: 0x76F23456   -> kernel32.dll 범위 -> ReadFile
  0x00403008: 0x77123456   -> user32.dll 범위 -> MessageBoxA
```
이렇게 만든 매핑표를 IDA에 옮겨, 해당 오프셋을 참조하는 `call dword ptr [0x00403000]` 같은 명령마다 `CreateFileA` 이름을 코멘트로 달아주면 코드 분석이 크게 쉬워진다.

## 관련 글
- REV-0945 — 언패킹 후 IAT를 복구하는 개념(Import Reconstruction)
- REV-0944 — 패킹된 바이너리에서 OEP를 수동으로 추적하는 절차 심화
- REV-0229 — Import가 거의 없는 PE를 봤을 때
- REV-0943 — 커스텀 패커(자체 제작 패커) 알아보는 단서

## 출처/검증
- IAT 슬롯 주소와 DLL export 테이블을 대조하는 원리는 Microsoft PE Format 공식 문서(Import/Export Directory 구조)를 기준으로 정리했다.
- x64dbg의 Memory Map/Symbols 탭 동작과 자동 심볼 코멘트 기능은 x64dbg 공식 문서(help.x64dbg.com)를 기준으로 확인했다(2026-09-09 검증).
