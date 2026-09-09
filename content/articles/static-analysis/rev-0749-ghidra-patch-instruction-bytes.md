---
id: REV-0749
title: "Ghidra Patch Instruction으로 바이트 수정하기"
slug: "rev-0749-ghidra-patch-instruction-bytes"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra]
keywords: ["Ghidra Patch Instruction", "Ghidra Patch Data", "Ghidra 바이트 패치", "Ghidra Export Program", "Ghidra 명령어 수정"]
aliases: ["Ghidra 명령어 수정", "Ghidra 바이트 수정", "Ghidra 패치 후 저장"]
symptom_keywords: ["Ghidra에서 명령어를 직접 고치는 법", "Ghidra Patch Instruction 어디있나", "Ghidra 수정한 걸 실제 파일로 저장하는 법", "Ghidra JNZ를 JMP로 바꾸는 법"]
source_ids: ["SRC-GHIDRA-DOCS"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Ghidra의 Patch Instruction/Patch Data는 Listing에서 선택한 명령어나 데이터를 직접 다른 값으로 바꿔치기하는 기능으로, x64dbg의 패치(REV-0184)와 같은 목적을 오프라인 정적 분석 환경에서 수행하며 실제 실행 파일로 만들려면 반드시 File → Export Program까지 거쳐야 한다.

## 언제 검색해야 하나
- x64dbg 등에서 하던 것처럼 특정 분기를 강제로 우회한 실행 파일을 Ghidra에서 만들어보고 싶을 때
- Listing에서 명령어를 고치고 싶은데 메뉴에서 못 찾을 때
- 패치를 했는데 실제 실행 파일에는 반영이 안 되는 것 같을 때
- 조건 분기를 무력화해서 정적 분석 결과를 검증해보고 싶을 때

## 핵심 개념

### Patch Instruction이 하는 일
Patch Instruction은 Listing에서 선택한 명령어를 다른 명령어로 직접 바꿔치기하는 기능이다. 예를 들어 `JNZ`를 `JMP`나 `NOP`로 바꿔 특정 조건 분기를 강제로 우회시키는 식의, x64dbg의 어셈블/패치(REV-0184)와 같은 목적을 Ghidra 안에서 수행한다.

### 여는 법과 사용법
Listing에서 바꾸고 싶은 명령어 위에 커서를 놓고 우클릭 → Patch Instruction을 선택하면 그 줄이 바로 편집 가능한 텍스트 필드로 바뀌어, 새 어셈블리 니모닉을 타이핑할 수 있다. 예를 들어 `JNZ LAB_00401050`이라고 써 있는 줄을 `JMP LAB_00401050`으로 고쳐 쓰고 Enter를 누르면 그 자리의 실제 바이트가 어셈블되어 반영된다. 데이터(예: 문자열, 상수)를 바꾸고 싶으면 Patch Data를 사용한다.

### 실제로 무엇이 바뀌는가
Patch Instruction/Patch Data는 Ghidra 프로젝트 내부에 저장된 프로그램 이미지(바이트 배열)를 수정한다. 이 시점에서는 디스크의 원본 실행 파일이 바뀌는 게 아니라, Ghidra가 관리하는 분석용 사본이 바뀌는 것이다. 실제 실행 가능한 파일로 만들고 싶다면 File → Export Program을 실행해서 원본과 같은 포맷(Original File 형식 등)으로 내보내야, 패치된 바이트가 반영된 새 실행 파일이 디스크에 생긴다.

### Assembler 검증
Patch Instruction 입력창은 실시간으로 문법을 검증하며, 새 명령어의 바이트 길이가 원래 명령어와 다를 경우(예: 2바이트 명령을 5바이트 명령으로 바꾸려는 경우) 뒤에 오는 바이트를 덮어써서 이후 명령어 정렬이 깨질 수 있다는 점을 주의해야 한다. Ghidra는 가능하면 같은 길이의 인코딩을 우선 시도하지만 항상 보장되지는 않는다.

### CTF에서의 활용 예
- 라이선스 체크/시리얼 체크 분기(`JNZ`/`JZ`)를 `JMP`나 `NOP`로 바꿔 무조건 통과하도록 만들어 정적으로 결과를 확인
- 디버거 탐지 분기를 무력화해서 정적 분석 결과를 검증
- 다만 이렇게 패치한 결과는 어디까지나 "이 분기를 없애면 어떻게 되는지" 확인하는 보조 수단이며, 실제 플래그를 얻으려면 원래 로직(키/알고리즘)을 이해하는 것이 더 중요한 경우가 많다.

## 화면/코드에서 보이는 징후
x64dbg 등에서 하던 것처럼 특정 분기를 강제로 우회한 실행 파일을 만들어보고 싶을 때, Listing에서 명령어를 고치고 싶은데 메뉴에서 못 찾을 때.

## 가장 먼저 할 것
바꾸고 싶은 명령어 위에서 먼저 우클릭 메뉴에 Patch Instruction이 보이는지 확인하고(보이지 않으면 해당 위치가 아직 코드로 정의되지 않았을 수 있으니 `D`로 먼저 Disassemble), 패치 전 원본 프로그램을 반드시 별도로 백업해 둔다.

## 단계별 절차
1. 패치 대상 명령어 확인, 필요하면 `D`로 코드 정의
2. 명령어 위 우클릭 → Patch Instruction
3. 새 니모닉 입력 후 Enter(예: `JNZ` → `JMP`, 또는 특정 위치를 `NOP`로)
4. Listing에서 바뀐 바이트가 올바르게 반영됐는지 확인(주변 명령어 정렬이 깨지지 않았는지)
5. File → Export Program으로 실제 실행 파일로 내보내기(형식 선택 시 원본과 같은 포맷 선택)
6. 내보낸 파일을 별도로 실행/디버깅해서 의도한 대로 동작하는지 검증

## 명령어/단축키
- 우클릭 → Patch Instruction
- 우클릭 → Patch Data
- `D`: Disassemble(코드로 정의)
- File → Export Program

## 출력 해석
패치 직후 Listing에서 해당 줄의 바이트 열(주소 옆 hex)이 바뀐 것을 볼 수 있다. Export Program 후 생성된 파일을 `file`/`objdump`로 열어 원래 포맷(PE/ELF)이 그대로 유지됐는지, 패치한 바이트가 정확한 오프셋에 반영됐는지 재확인하는 것이 안전하다.

## 흔한 실수
- Patch Instruction만 하고 Export Program을 하지 않아 "패치했는데 실행 파일은 그대로다"라고 착각하는 것.
- 명령어 길이가 달라지는 패치를 하면서 뒤 바이트가 밀리는 것을 확인하지 않는 것.
- 원본 파일을 백업하지 않고 패치를 실험하다가 되돌리기 어려워지는 것.
- PIE/ASLR 등으로 재배치가 필요한 바이너리에서 패치 후 재배치 정보가 깨지는 경우를 확인하지 않는 것.

## 막혔을 때 다음 체크
- 디버거에서 같은 목적의 패치를 하고 싶으면 → REV-0184 x64dbg CTF용 간단 패치와 저장
- 구조체 필드처럼 데이터를 바꾸고 싶은데 명령어가 아니라면 → REV-0742 Ghidra Data Type Manager로 구조체 임포트/정의하기
- 패치 전 이 분기가 정확히 어떤 조건인지 P-code 레벨까지 확인하고 싶으면 → REV-0745 Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)

## 미니 예제
```text
패치 전:
00401050  JNZ  LAB_00401060

명령어 위 우클릭 -> Patch Instruction -> "JMP LAB_00401060" 입력 -> Enter

패치 후:
00401050  JMP  LAB_00401060

File -> Export Program -> Original File 형식 선택 -> chall_patched.exe 생성
chall_patched.exe 실행 시 항상 LAB_00401060 경로로 진입(조건 무시됨) 확인
```

## 관련 글
- REV-0184 — x64dbg CTF용 간단 패치와 저장
- REV-0742 — Ghidra Data Type Manager로 구조체 임포트/정의하기
- REV-0745 — Ghidra P-code 개념 소개(왜 중간 표현이 필요한가)
- REV-0161 — Ghidra Rename과 Data Type 수정

## 출처/검증
Ghidra 공식 Help 문서(Patch Instruction, Patch Data, Export Program) 기준. 실제 실행 화면을 캡처해 재검증하지는 않았으며, 공식 문서와 널리 통용되는 메뉴 경로를 기준으로 작성했다(2026-09-09).
