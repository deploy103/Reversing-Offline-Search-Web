---
id: REV-0955
title: "언패킹한 덤프가 크래시가 날 때"
slug: "rev-0955-unpacked-dump-crashes"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, "Detect It Easy", "PE-bear"]
keywords: ["메모리 덤프 크래시", "process dump crash", "덤프한 exe 실행 안됨", "언패킹 덤프 오류", "IAT 미복구"]
aliases: ["덤프 실행하면 크래시", "process dump가 안 열림", "scylla dump crash"]
symptom_keywords: ["Scylla로 덤프했는데 실행이 안됨", "덤프 파일이 접근 위반으로 죽음", "덤프한 exe를 IDA로 열면 함수가 이상함", "메모리에서 뜬 파일이 원본과 다르게 동작"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
OEP에서 프로세스 메모리를 파일로 떠냈는데(dump) 그 파일이 실행 즉시 접근 위반(Access Violation)으로 죽는다면, 거의 항상 **IAT(Import Address Table)가 아직 정상 구조로 복구되지 않았거나, 덤프 시점의 섹션 크기 정보(SizeOfRawData/VirtualSize)가 잘못 저장되었기 때문**이다.

## 언제 검색해야 하나
- x64dbg + Scylla로 OEP에서 "Dump" 버튼을 눌러 파일을 저장했는데, 그 파일을 실행하면 창이 뜨자마자 사라지거나 "프로그램이 작동을 멈췄습니다" 오류가 뜰 때
- 덤프한 파일을 IDA/Ghidra로 열었을 때 함수 호출 부분이 전부 이상한 주소를 가리키거나, `call`이 존재하지 않는 메모리 영역을 가리킬 때
- 덤프 직후 x64dbg 안에서 실행을 계속(F9)했을 때는 정상 동작하는데, 별도로 저장한 덤프 파일만 따로 실행하면 죽을 때
- OEP를 제대로 찾은 것 같은데도 덤프 결과가 매번 크래시로 이어질 때

## 핵심 개념
메모리 덤프가 크래시로 이어지는 원인은 크게 세 갈래로 나뉜다.

### 1) IAT가 원본 구조로 복구되지 않음
실행 중인 프로세스의 메모리에서는 각 API 함수의 **실제 주소**가 이미 채워져 있다. 하지만 이 주소들이 "어느 DLL의 어느 함수인지"를 나타내는 정상적인 Import Table 구조(Import Directory, Import Address Table, 이름 문자열)는 패커가 자체 방식으로 관리했을 뿐 표준 PE 포맷으로 존재하지 않는 경우가 많다. 이 상태로 파일을 그대로 저장하면, 실행할 때 Windows 로더가 표준 Import Table을 찾다가 없거나 깨진 구조를 만나 로딩 자체에 실패하거나, 함수 호출 시점에 잘못된 주소를 호출해서 접근 위반이 난다.

### 2) 섹션의 RawSize/VirtualSize 불일치
디스크 파일과 메모리 이미지는 섹션 정렬 방식이 다르다(디스크는 `FileAlignment`, 메모리는 `SectionAlignment` 기준). 메모리를 그대로 파일로 떠내면서 이 정렬 차이를 제대로 변환하지 않으면, 저장된 파일의 섹션 크기/오프셋이 실제 내용과 어긋나 로더가 코드를 엉뚱한 위치에서 읽게 된다.

### 3) OEP 자체가 틀렸거나 너무 이름
언패킹 스텁이 완전히 끝나기 전, 즉 아직 압축 해제나 IAT 채우기가 덜 끝난 시점에서 덤프를 뜨면, 저장된 메모리 이미지 자체에 미완성 데이터가 섞여 있다. 이 경우 IAT를 아무리 다시 복구해도 코드 영역 자체가 불완전하기 때문에 크래시가 사라지지 않는다.

## 화면/코드에서 보이는 징후
- 덤프 파일 실행 시 Windows가 "액세스 위반(0xC0000005)" 또는 "잘못된 이미지(0xC000012F, INVALID_IMAGE_FORMAT)" 오류를 낸다.
- IDA로 덤프를 열었을 때 Imports 탭이 텅 비어 있거나, 함수 이름 대신 `sub_` 접두사만 가득하다.
- x64dbg에서 덤프 파일을 다시 열어 실행하면, `call [address]` 형태의 간접 호출 지점에서 예외가 발생한다.
- PE-bear로 덤프 파일의 섹션 테이블을 보면 `VirtualSize`와 `SizeOfRawData` 값이 원본 대비 극단적으로 차이 나거나 0으로 표시된다.

## 가장 먼저 할 것
크래시가 난 지점을 x64dbg로 다시 열어 정확히 어떤 명령에서 죽는지부터 확인한다. `call [rax]` 같은 간접 호출에서 죽는지, 아니면 프로그램 시작 직후(로더 단계)에서 죽는지에 따라 원인이 IAT 문제인지 섹션 정렬 문제인지 갈린다.

## 단계별 절차
1. 덤프 파일을 x64dbg로 다시 열고 실행(F9)해서 정확히 어느 명령/주소에서 예외가 발생하는지 기록한다.
2. 그 명령이 `call`, `jmp` 등 함수 호출/간접 점프이고 대상 주소가 이상한 값(0, 매우 작은 값, 매핑되지 않은 영역)이면 IAT 문제를 의심한다 — Scylla를 다시 열어 `IAT Autosearch` → `Get Imports`로 항목들이 정상적으로(`valid`) 인식되는지 확인한다.
3. `Get Imports` 결과에 물음표(`?`)나 "invalid"로 표시되는 함수가 있다면, OEP 시점이 아직 IAT를 다 채우기 전이었을 가능성이 크다 — OEP 후보를 조금 더 뒤로(스텁의 `jmp OEP` 이후 몇 개 명령 더 지나서) 옮겨 다시 덤프한다.
4. IAT는 정상인데 프로그램 시작 자체가 로더 단계에서 실패한다면, PE-bear로 섹션 테이블의 `VirtualSize`/`SizeOfRawData`/`PointerToRawData` 값을 원본(패킹된 파일)과 비교해서 명백히 어긋난 섹션이 있는지 확인한다.
5. Scylla의 "Fix Dump" 기능을 다시 실행해 IAT를 최신 상태로 재작성한 뒤, 저장된 결과 파일로 다시 테스트한다.
6. 그래도 크래시가 반복되면, 덤프 자체를 신뢰하지 말고 그냥 x64dbg 안에서 계속 동적으로 관찰하며 필요한 정보만 얻는 방식(REV-0241)으로 전환하는 것도 실용적인 선택이다.

## 명령어/단축키
- x64dbg: `Plugins → Scylla` 로 플러그인 실행, `IAT Autosearch` → `Get Imports` → `Fix Dump`
- x64dbg 예외 확인: 실행 중 죽으면 상태 표시줄에 예외 코드(`Access violation`)와 주소가 표시됨, `Ctrl+G`로 해당 주소로 이동
- PE-bear: 파일 열기 후 좌측 트리 `Section Headers`에서 각 섹션의 `RawSize`/`VirtualSize` 확인

## 출력 해석
- Scylla `Get Imports`에서 항목 대부분이 정상 함수 이름으로 표시되면 IAT는 문제가 아니다. `?` 표시가 많다면 그 자체가 OEP가 이르거나 IAT 위치 지정이 틀렸다는 신호다.
- x64dbg에서 죽는 위치가 `.text` 섹션 밖(예: 매핑되지 않은 주소)이라면 섹션 크기/정렬 문제일 가능성이 크다.
- PE-bear에서 `VirtualSize`가 `SizeOfRawData`보다 훨씬 크게 나오는 것 자체는 정상(메모리에서 더 크게 확장되는 섹션들이 흔함)이지만, `PointerToRawData`가 파일 전체 크기를 넘어서는 값이라면 명백한 오류다.

## 흔한 실수
- 크래시가 나면 바로 "언패킹이 잘못됐다"고 단정하고 처음부터 OEP를 다시 찾는 것 — 실제로는 IAT 복구만 다시 하면 해결되는 경우가 훨씬 많다.
- Scylla의 `Get Imports` 결과를 확인하지 않고 바로 `Fix Dump`부터 누르는 것 — invalid 항목이 있는 채로 고정해봐야 크래시는 그대로다.
- 덤프 파일을 IDA로 열어보지 않고 실행만 반복하는 것 — IDA로 열면 Imports 탭이 비었는지, 함수가 제대로 인식되는지 훨씬 빠르게 확인할 수 있다.
- 여러 번 덤프를 시도하면서 매번 파일명을 덮어써서, 이전 시도와 무엇이 달라졌는지 비교할 수 없게 만드는 것.

## 막혔을 때 다음 체크
- IAT를 아무리 복구해도 여전히 텅 비어 보인다면 → REV-0958(Import Table이 언패킹 후에도 비어있을 때)을 참고한다.
- 덤프 자체는 만들어졌는데 안티덤프 루틴이 의심된다면 → REV-0962(안티덤프 때문에 덤프한 파일이 손상되어 있을 때)를 참고한다.
- OEP 자체를 다시 찾아야 한다면 → REV-0956(OEP를 찾았는데 실행이 이상하게 될 때)을 참고한다.

## 미니 예제
```text
1) x64dbg + Scylla로 OEP(0x00401230)에서 Dump 실행 → dumped.exe 저장
2) dumped.exe 실행 → 즉시 "Access violation" 창 뜸
3) x64dbg로 dumped.exe를 다시 열어 F9 실행 → 0x00401258의 call [0x00402010]에서 예외
4) Scylla의 IAT Autosearch → Get Imports 확인
   -> kernel32.dll!GetProcAddress   valid
   -> kernel32.dll!LoadLibraryA     valid
   -> user32.dll!MessageBoxA        ??? (invalid)
5) MessageBoxA가 invalid로 나온 것을 보고, OEP를 스텁 종료 직후가 아니라
   몇 개 명령 더 지난 지점(IAT 채우기가 완전히 끝난 시점)으로 다시 잡음
6) 재덤프 후 Get Imports 재확인 → 전부 valid
7) Fix Dump 실행 → dumped_fixed.exe 실행 시 정상 동작 확인
```

## 관련 글
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0956 — OEP를 찾았는데 실행이 이상하게 될 때
- REV-0958 — Import Table이 언패킹 후에도 비어있을 때
- REV-0962 — 안티덤프 때문에 덤프한 파일이 손상되어 있을 때

## 출처/검증
- Scylla의 IAT Autosearch/Get Imports/Fix Dump 동작과 IAT 복구 필요성: Scylla 공식 저장소(github.com/NtQuery/Scylla) 문서 기준(2026-09-09 검증).
- PE 파일의 디스크/메모리 섹션 정렬 차이(FileAlignment vs SectionAlignment)와 이로 인한 덤프 오류 가능성: Microsoft PE/COFF 명세 문서 기준.
