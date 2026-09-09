---
id: REV-0939
title: "ASPack 패커 기초 알아보기"
slug: "rev-0939-aspack-packer-basics"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, DIE, PE-bear]
keywords: ["ASPack", "ASPack 언패킹", "ASPack 시그니처", "ASPack stub", "aspack 패커란", "ASPack 압축 실행파일"]
aliases: ["aspack이 뭐임", "ASPack 패킹 확인법", "aspack 언패킹 방법", "ASPack stub 코드"]
symptom_keywords: ["DIE에서 ASPack이라고 뜸", "섹션 이름이 이상한데 UPX는 아님", "PUSHAD로 시작하는 entry point", "aspack 패킹된 exe 분석"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
ASPack은 UPX처럼 EXE/DLL을 압축하는 오래된 상용 실행 압축기로, entry point가 `PUSHAD`로 시작하는 짧은 복원 스텁을 갖고 있으며 UPX와 달리 공식 `-d` 옵션이 없으므로 REV-0227에서 배운 수동 언패킹(OEP 찾기 + 덤프)으로 접근해야 한다.

## 언제 검색해야 하나
- Detect It Easy(DIE)로 스캔했더니 packer 항목에 `ASPack`이라는 이름이 나올 때
- 파일 크기가 작고 섹션이 2~3개뿐인데 UPX 특유의 `UPX0`/`UPX1` 섹션 이름이 아닐 때
- x64dbg로 entry point를 열었더니 `PUSHAD` 한 줄 뒤로 알 수 없는 루프가 이어질 때
- "ASPack 언패킹" 같은 검색어로 자동화 도구를 찾다가 실패해서 개념부터 이해하고 싶을 때

## 핵심 개념
ASPack은 1990년대 후반부터 배포된 상용 Windows 실행 파일 압축기다. UPX와 목적은 같다 — 실행 파일 크기를 줄이는 것 — 하지만 두 가지 실무적인 차이가 있다.

1. **공식 언패킹 도구가 없다.** UPX는 압축과 해제가 같은 도구(`upx -d`)로 되지만, ASPack은 압축 전용 상용 도구이고 벤더가 "언패킹" 기능을 공개 배포하지 않는다. 따라서 REV-0226처럼 한 줄 명령으로 되돌릴 수 없다.
2. **스텁 구조가 UPX보다 약간 더 복잡하다.** 여러 개의 재배치(relocation) 처리, 자체 API 해석 루틴이 들어가 있어 단순 압축 해제 루프보다 코드 길이가 길다.

그럼에도 ASPack은 "상용 실행 압축기" 중에서는 가장 단순한 축에 속한다. VMProtect나 Themida처럼 코드 가상화나 강력한 안티 디버깅을 넣지 않고, 목적이 순수하게 파일 크기 축소이기 때문에 안티 디버깅 트릭이 거의 없거나 매우 약하다. 그래서 x64dbg로 붙여서 관찰하는 것 자체는 어렵지 않다.

### entry point 스텁의 전형적인 모양
ASPack 스텁은 보통 다음 순서를 따른다.

1. `PUSHAD` — 모든 범용 레지스터를 스택에 저장(복원 후 원본 레지스터 상태를 되살리기 위함)
2. 압축된 `.text`/`.data` 내용을 원래 위치(원본 섹션이 있던 가상 주소)에 풀어놓는 루프
3. 원본 프로그램이 쓰는 API 주소를 IAT에 채워 넣는 루틴(`GetProcAddress` 계열 호출 반복)
4. `POPAD` — 저장해둔 레지스터를 복원
5. `JMP OEP` — 압축 풀린 원본 코드로 점프

이 흐름은 REV-0227에서 다룬 일반적인 패커 스텁 구조와 사실상 동일하다. 차이는 세부 명령 배치와 시그니처뿐이다.

### 왜 지금도 ASPack을 CTF에서 만나는가
오래된 패커라서 오히려 "패킹이 뭔지 처음 보여주기용" 문제나, 레거시 샘플을 재활용한 문제에서 자주 나온다. 또한 시그니처가 잘 알려져 있어 DIE/PEiD 계열 도구가 거의 100% 정확히 식별해주므로, "패킹 식별 연습" 난이도의 문제로도 적합하다.

## 화면/코드에서 보이는 징후
- DIE의 상단 패널에 `PE64/PE32` 아래 `Packer: ASPack(...)` 문자열이 명시적으로 표시됨
- PE-bear로 섹션을 보면 이름이 `.aspack`, `.adata` 같은 ASPack 특유의 이름으로 되어 있는 경우가 많음(다만 컴파일 시점 설정에 따라 이름을 바꿀 수도 있어 100% 신뢰하면 안 됨)
- x64dbg에서 entry point 첫 명령이 `pushad`이고, 그 뒤로 짧은 루프와 다수의 `mov`, `rep movsb` 유사 패턴이 반복됨
- Imports 창(IDA/x64dbg)에 정상 프로그램이라면 있어야 할 API가 몇 개 없고 `LoadLibraryA`, `GetProcAddress` 정도만 보임(REV-0229와 동일한 신호)

## 가장 먼저 할 것
DIE로 스캔해서 `ASPack` 시그니처와 버전을 확인한다. 그 다음 원본 파일을 반드시 백업한 뒤, x64dbg로 열어 entry point가 `pushad`로 시작하는지 직접 눈으로 확인한다. 이 확인이 끝나면 "이건 UPX처럼 자동으로는 안 풀리는 패커"라는 전제 하에 REV-0944(OEP 수동 추적 절차 심화)로 넘어간다.

## 단계별 절차
1. `die packed.exe` 또는 DIE GUI로 패커 식별, 버전까지 확인
2. 원본 백업(`copy packed.exe packed.exe.bak`)
3. x64dbg로 로드, entry point에서 `pushad` 확인
4. `popad` 다음에 오는 `jmp` 명령을 찾아 그 목적지 주소를 OEP 후보로 표시(REV-0944 절차 활용)
5. OEP 후보에서 실행을 멈추고 코드가 정상적인 컴파일러 프롤로그처럼 보이는지 확인
6. Scylla로 덤프 및 IAT 복구(REV-0945/REV-0946)
7. 복구된 파일을 IDA/Ghidra로 재분석

## 명령어/단축키
- x64dbg: `F9`(Run), `F8`(Step Over), `F7`(Step Into) — pushad/popad 사이를 오갈 때 F8을 많이 쓴다
- x64dbg 커맨드바: `bp <addr>`로 popad 이후 jmp 주소에 브레이크포인트
- DIE: `File → Open`으로 로드 후 상단 패커 표시줄 확인
- Scylla: `Plugins → Scylla` (REV-0945 참고)

## 출력 해석
- DIE가 `ASPack v2.12 -> Alexey Solodovnikov`처럼 버전과 제작자까지 표시하면 시그니처 매칭이 확실하다는 뜻이다.
- entry point가 `pushad`가 아니라 다른 형태라면 ASPack이 아니거나, 다른 패커가 위에 한 번 더 덮여 있는 이중 패킹일 수 있다(REV-0224 체크리스트로 재확인).
- popad 이후 jmp 대상 주소가 원본 이미지 베이스 근처의 낮은 주소(예: `.text` 시작 부분)라면 OEP일 확률이 높다.

## 흔한 실수
- ASPack도 UPX처럼 전용 `-d` 명령이 있을 것이라 기대하고 인터넷에서 "aspack -d" 같은 명령을 찾아 헤매는 것. ASPack은 그런 공식 해제 도구를 제공하지 않는다.
- pushad/popad 쌍이 하나뿐이라고 가정하는 것. 일부 ASPack 버전이나 변형은 중첩된 스텁을 갖고 있어 popad가 여러 번 나올 수 있다.
- 섹션 이름만 보고 ASPack이라 단정하는 것. 섹션 이름은 리소스 편집기 등으로 쉽게 바뀔 수 있으므로 DIE 시그니처와 entry point 코드 패턴을 함께 확인해야 한다.

## 막혔을 때 다음 체크
- OEP를 못 찾겠다면 → REV-0944 OEP 수동 추적 절차 심화
- 덤프 후 실행이 안 된다면 → REV-0945 언패킹 후 IAT를 복구하는 개념(Import Reconstruction)
- Scylla 같은 도구가 없다면 → REV-0946 도구 없이 수동으로 Import 복구하는 개념
- 사실 ASPack이 아니라 더 강력한 프로텍터였다면 → REV-0942 상용 프로텍터(VMProtect/Themida)를 만났을 때 현실적인 대응

## 미니 예제
```text
entry point:
  pushad
  mov esi, <compressed_data>
  mov edi, <original_va>
decompress_loop:
  ; 압축 해제 루프 반복
  loop decompress_loop
  ; IAT 채우기
  call resolve_imports
  popad
  jmp 0x00401000     ; <- OEP 후보
```
`jmp 0x00401000`에 브레이크포인트를 걸고 F9로 실행하면, 그 주소에서 멈춘 순간 메모리에는 이미 압축이 풀린 원본 코드가 올라와 있다.

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0225 — UPX인지 확인하는 법
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0940 — PECompact 패커 기초 알아보기
- REV-0944 — 패킹된 바이너리에서 OEP를 수동으로 추적하는 절차 심화
- REV-0945 — 언패킹 후 IAT를 복구하는 개념(Import Reconstruction)

## 출처/검증
- ASPack의 entry point 스텁 구조(pushad/popad, 압축 해제 루프, IAT 자체 해석)는 다수의 공개 리버싱 교육 자료와 언패킹 튜토리얼에서 공통적으로 설명하는 패턴을 기준으로 정리했다.
- Detect It Easy의 패커 시그니처 표시 방식은 DIE 공식 저장소(github.com/horsicq/Detect-It-Easy) 문서를 참고했다(2026-09-09 검증).
- 실제 버전별 스텁 코드는 ASPack 버전에 따라 세부 명령이 달라질 수 있으므로, 특정 샘플 분석 시 직접 디버거로 재확인이 필요하다.
