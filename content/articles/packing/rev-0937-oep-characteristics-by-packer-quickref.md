---
id: REV-0937
title: "패커별 OEP 특징 빠른 참조"
slug: "rev-0937-oep-characteristics-by-packer-quickref"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, IDA]
keywords: ["OEP 특징", "OEP 찾는 법", "popad jmp oep", "ESP 트릭", "패커별 OEP", "Original Entry Point 패턴"]
aliases: ["oep 어디서 찾나", "패커마다 oep 다른가", "popad 다음 jmp가 oep", "esp 트릭이 뭔가"]
symptom_keywords: ["oep를 못 찾겠음", "popad 다음에 jmp가 보임", "esp 트릭이 뭔지 모름", "패커마다 oep 위치가 다른가"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
UPX/ASPack 계열은 `PUSHAD`로 시작해 `POPAD` 직후의 단 하나의 `JMP`가 OEP로 이어지는 패턴이 매우 규칙적이라 ESP 트릭으로 쉽게 찾을 수 있지만, 상용 프로텍터(VMProtect/Themida)는 이런 단일 지점 자체가 없거나 위장되어 있으므로 이 표로 "내가 다루는 패커가 어느 유형인지"부터 구분해야 한다.

## 언제 검색해야 하나
- REV-0227에서 OEP 개념은 이해했는데, 실제로 어디서부터 찾기 시작해야 할지(브레이크포인트를 어디 걸지) 감이 안 잡힐 때
- x64dbg 화면에서 `PUSHAD`/`POPAD` 같은 명령을 보고 이게 OEP 탐색과 관련 있는지 궁금할 때
- "ESP 트릭"이라는 용어를 들었는데 정확히 뭘 하는 기법인지 모를 때
- 패커 종류에 따라 OEP를 찾는 난이도가 왜 이렇게 다른지 궁금할 때

## 핵심 개념
대부분의 단순 압축형 패커(UPX, ASPack, FSG 등)는 실행 시작 시 레지스터를 모두 스택에 저장(`PUSHAD`)하고, 압축 해제가 끝나면 저장했던 레지스터를 모두 복원(`POPAD`)한 뒤, 바로 다음에 오는 단 하나의 점프 명령으로 OEP로 넘어가는 구조를 공유한다. 이 구조가 워낙 규칙적이어서 "ESP 트릭"이라는 유명한 탐색 기법이 성립한다.

**ESP 트릭 원리**: `PUSHAD`가 실행되면 8개 레지스터가 스택에 순서대로 쌓이면서 ESP(스택 포인터)가 특정 값만큼 감소한다. 이 순간 디버거에서 ESP 레지스터 값에 하드웨어 메모리 접근(읽기/쓰기) 브레이크포인트를 걸어두면, 압축 해제 루프가 아무리 복잡해도 결국 `POPAD`가 그 스택 값을 다시 읽어가는 순간 브레이크포인트가 걸린다. `POPAD` 직후에는 거의 항상 원본 코드로 가는 `JMP` 한 줄만 남아 있으므로, 그 지점에서 한 번 더 `Step Into`(F7)만 하면 바로 OEP다.

상용 프로텍터는 이 구조 자체를 쓰지 않거나, 여러 번 중첩된 가짜 `PUSHAD`/`POPAD`를 배치해 ESP 트릭을 무력화하므로 표를 미리 알아두면 헛수고를 줄일 수 있다.

## 화면/코드에서 보이는 징후
| 패커 유형 | Entry point 코드 패턴 | OEP 도달 난이도 | 유효한 탐색 기법 |
|---|---|---|---|
| UPX | `PUSHAD` → 단순 압축 해제 루프 → `POPAD` → 단일 `JMP` | 쉬움 | ESP 트릭이 거의 항상 성공 |
| ASPack | `PUSHAD` 유사 구조, 루프가 UPX보다 약간 더 복잡 | 쉬움~보통 | ESP 트릭 대부분 성공 |
| FSG / MEW | 레지스터 저장 방식이 `PUSHAD`가 아닌 개별 `PUSH`일 수 있음 | 보통 | ESP 트릭 변형 필요, 수동 확인 병행 |
| Themida/WinLicense | 단일 OEP 지점이 명확하지 않음, 다중 안티디버깅 우선 통과 필요 | 매우 어려움 | ESP 트릭 무효, REV-0935 참고 |
| VMProtect | 원본 명령어가 가상 바이트코드로 대체되어 "OEP"라는 개념 자체가 흐려짐 | 매우 어려움~사실상 불가능 | ESP 트릭 무효, 부분 디버깅 전용 기법 필요 |

## 가장 먼저 할 것
x64dbg로 파일을 열고 entry point에서 멈춘 직후, 첫 명령이 `PUSHAD`인지부터 확인한다. `PUSHAD`가 보이면 ESP 트릭을 적용할 수 있는 유형(UPX/ASPack 계열)일 가능성이 높다.

## 단계별 절차
**1) entry point 확인**: x64dbg로 프로그램을 로드하면 자동으로 entry point에서 멈춘다. 첫 줄이 `PUSHAD`인지 본다.
**2) ESP 값 기록**: `PUSHAD` 실행 직후(F8로 한 줄 실행) 레지스터 창에서 ESP 값을 확인한다.
**3) 하드웨어 브레이크포인트 설정**: 덤프 창에서 해당 ESP 주소로 이동(`Ctrl+G`에 `ESP` 입력) 후 우클릭 → `Breakpoint → Hardware, Access → Dword`로 설정한다.
**4) 실행(F9)**: 압축 해제 루프를 건너뛰고 `POPAD`가 그 스택 값을 읽는 순간 자동으로 멈춘다.
**5) 다음 줄 확인**: 멈춘 지점 근처에 `POPAD` 다음 `JMP` 한 줄이 보이면, 그 `JMP`를 `Step Into`(F7)해서 도착하는 지점이 OEP다.
**6) OEP 확인**: 도착 지점 코드가 `PUSH EBP`/`MOV EBP, ESP` 같은 정상 함수 프롤로그로 보이면 OEP를 맞게 찾은 것이다(REV-0227 참고).
**7) 패턴이 안 맞으면**: `PUSHAD`가 안 보이거나 여러 번 반복되면 표에서 Themida/VMProtect 계열인지 재확인하고, REV-0935로 이동해 접근 방식을 재검토한다.

## 명령어/단축키
- x64dbg: `Ctrl+G`(주소로 이동), `F8`(Step Over), `F7`(Step Into), `F9`(Run)
- 하드웨어 브레이크포인트: 덤프 창 우클릭 → `Breakpoint → Hardware, Access → Dword`
- 레지스터 창: 우측 상단에서 ESP/EIP 실시간 확인

## 출력 해석
- 하드웨어 브레이크포인트가 걸린 직후 코드가 `POPAD`라면 ESP 트릭이 정상 동작한 것이다.
- 브레이크포인트가 여러 번 반복해서 걸리고 `POPAD`가 안 보인다면, 압축 해제 루프 내부에서 스택을 임시로 더 건드리는 경우이므로 몇 번 더 `F9`를 눌러 진짜 `POPAD` 지점까지 진행해야 한다.
- OEP 도착 후 코드가 여전히 스텁처럼 짧고 반복적이라면 다단 패킹(패커 위에 패커를 또 씌운 경우)일 수 있으니 1번부터 다시 반복한다.

## 흔한 실수
- `PUSHAD`가 안 보이는 패커에도 무조건 ESP 트릭을 시도하다가 시간을 낭비하는 것 — 표로 먼저 유형을 구분해야 한다.
- 첫 번째로 걸린 하드웨어 브레이크포인트를 무조건 OEP 직전이라고 단정하는 것 — 압축 해제 루프 내부에서도 스택 접근이 여러 번 발생할 수 있다.
- Themida/VMProtect 같은 프로텍터에 UPX용 기법(ESP 트릭)을 그대로 적용하려는 것 — 애초에 성립하지 않는 구조다(REV-0935 참고).

## 막혔을 때 다음 체크
- OEP 개념 자체가 헷갈리면 → REV-0227 수동 언패킹 개념 OEP와 Dump.
- 이 파일이 UPX/ASPack 계열인지부터 확실히 하고 싶다면 → REV-0931 흔한 패커 시그니처 빠른 참조표.
- Themida/VMProtect 계열로 판단된다면 → REV-0935 VMProtect/Themida 등 상용 프로텍터 존재만 알아두는 참조표.

## 미니 예제
```asm
; UPX 계열 entry point 전형적 패턴
00401000  PUSHAD
00401001  MOV ESI, 0040A000
00401006  LEA EDI, [ESI+something]
; ... 압축 해제 루프 (수백~수천 회 반복) ...
00401234  POPAD
00401235  JMP 00401ABC        ; <- 이 JMP를 Step Into 하면 OEP(00401ABC)
```
ESP 트릭으로 `00401234`(POPAD)에서 멈춘 뒤 `F7` 한 번이면 `00401ABC`(OEP)에 도착한다.

## 관련 글
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0931 — 흔한 패커 시그니처 빠른 참조표(UPX/ASPack/PECompact 등)
- REV-0935 — VMProtect/Themida 등 상용 프로텍터 존재만 알아두는 참조표
- REV-0936 — 언패킹 체크리스트 빠른 참조

## 출처/검증
- ESP 트릭의 원리(`PUSHAD`/`POPAD` 및 하드웨어 메모리 접근 브레이크포인트 활용)는 x64dbg/OllyDbg 커뮤니티에서 UPX류 패커 OEP 탐색에 널리 쓰이는 표준 기법으로, x64dbg 공식 문서(help.x64dbg.com) 및 다수의 공개 리버싱 튜토리얼에서 공통적으로 설명하는 내용을 기준으로 정리했다(2026-09-09 검증).
- VMProtect/Themida가 이 기법에 취약하지 않은 이유(코드 가상화로 단일 OEP 개념 자체가 흐려짐)는 각 제품 공식 소개 자료 및 공개 리버싱 발표 자료의 일반적 설명을 참고했다.
- 실제 성공 여부는 패커 버전과 옵션(안티 ESP 트릭 대응이 추가된 최신 버전 등)에 따라 달라질 수 있다.
