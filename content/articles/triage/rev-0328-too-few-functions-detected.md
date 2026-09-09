---
id: REV-0328
title: "함수 개수가 비정상적으로 적게 잡힐 때"
slug: "rev-0328-too-few-functions-detected"
category: "triage"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["함수 개수 적음", "Functions 창이 텅 비어있음", "auto analysis 실패", "함수 인식 안됨"]
aliases: ["함수가 몇 개 없음", "코드가 대부분 data로 잡힘", "analysis가 덜 끝난 것 같음"]
symptom_keywords: ["Functions 창에 함수가 3~4개밖에 없음", "대부분이 회색/데이터로 표시됨", "생각보다 함수가 너무 적게 잡힘", "auto analysis 끝났는데 함수가 거의 없음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
IDA/Ghidra의 Functions 창에 함수가 예상보다 훨씬 적게(몇 개만) 보인다면, 대부분은 "코드가 진짜로 몇 개 없어서"가 아니라 **자동 분석기가 나머지 코드를 함수로 인식하지 못하고 데이터로 처리**했기 때문이다 — stripped, 정적 링킹, 패킹, 분석 옵션 문제 중 하나를 의심해야 한다.

## 언제 검색해야 하나
- 바이너리 크기는 수백 KB인데 Functions 창에 3~5개 함수만 보일 때
- 디스어셈블리 화면 대부분이 코드(흰색/연산자)가 아니라 데이터(회색 `db`, `dd` 나열)로 표시될 때
- Ghidra Auto Analysis가 "완료되었다"는 메시지를 띄웠는데도 함수 목록이 비어 보일 때
- 문제 설명이나 파일 크기로 봤을 때 로직이 이 정도로 단순할 리 없다고 느껴질 때

## 핵심 개념
IDA/Ghidra는 코드를 "이해"해서 함수를 찾는 게 아니라, **함수 프롤로그 패턴**(`push rbp; mov rbp, rsp` 또는 `endbr64` 등)과 **CALL 명령의 대상 주소**를 근거로 함수 경계를 추정한다. 이 추정이 실패하는 대표적인 상황은 다음과 같다.

1. **정적 링킹(static linking)** — libc 전체가 바이너리에 통째로 포함되어 있으면 함수 자체는 수백~수천 개지만, 심볼이 stripped라 이름이 전부 `sub_`로 나온다. 이 경우는 "함수가 적은 것"이 아니라 "이름만 없는 것"이라 착각하기 쉽다. 반대로 진짜로 함수 개수가 적게 잡히는 경우는 대부분 아래 2~4번이다.
2. **패킹/암호화** — 실제 코드가 런타임에 언패킹되어 메모리에 풀리기 때문에, 파일 상태에서는 대부분의 섹션이 의미 없는 바이트(엔트로피 높은 데이터)로 보여서 함수로 인식될 CALL/프롤로그 패턴 자체가 없다.
3. **분석 중단/타임아웃** — 매우 큰 바이너리에서 Ghidra/IDA의 자동 분석이 다 끝나기 전에 화면을 열어봤거나, 특정 섹션에서 예외가 나서 그 이후 분석이 진행되지 않은 경우.
4. **비표준 진입/컨벤션** — 컴파일러나 언어 런타임(Go, Rust, 커스텀 런타임)이 표준 프롤로그를 쓰지 않아서 자동 인식 휴리스틱이 통하지 않는 경우.
5. **분석 옵션이 꺼져있음** — Ghidra의 경우 "Analyze All Instructions" 옵션이 비활성화되어 있거나 특정 섹션이 코드 섹션으로 표시되지 않은 경우.

## 화면/코드에서 보이는 징후
- IDA: Functions 창(Ctrl+P)에 함수가 손에 꼽을 정도로만 보이고, IDA View에서 스크롤하면 대부분 `db 0FFh, 0AAh, ...` 같은 무의미한 바이트 나열.
- Ghidra: Symbol Tree의 Functions 폴더가 거의 비어있고, Listing 창 대부분이 `??` 또는 정의되지 않은 바이트(빨간 밑줄) 상태.
- `objdump -d` 결과가 몇 줄로 끝나거나, 반대로 disassemble 자체는 되는데 함수 경계 구분 없이 하나로 이어짐.

## 가장 먼저 할 것
`file`과 Detect It Easy(DIE)로 패킹 여부부터 확인한다. 패킹되어 있지 않다면 섹션별 엔트로피를 보고, 그다음 자동 분석을 강제로 다시 돌린다.

## 단계별 절차

**1) 패킹 여부 우선 확인**
```bash
file ./chall
```
`file`이 컴파일러/링커 정보를 제대로 못 읽거나(`data`로만 표시), DIE에서 UPX 등 알려진 패커 시그니처가 잡히면 REV-0224(패킹된 바이너리인지 의심하는 기준)로 이동한다. 패킹이 맞다면 정적 분석으로는 함수가 적게 보이는 게 정상이며, 언패킹 후 다시 열어야 한다.

**2) 섹션 엔트로피 확인**
DIE 또는 Ghidra의 Window > Function Graph 대신 섹션 헤더를 보고, `.text` 섹션의 크기 대비 실제 코드로 인식된 바이트 비율이 비정상적으로 낮은지 확인한다. 엔트로피가 7.0 이상이면 암호화/압축 가능성이 높다.

**3) 정적 링킹 여부 확인**
```bash
readelf -h ./chall | grep Type
ldd ./chall
```
`ldd`가 `not a dynamic executable`라고 하면 정적 링킹이다. 이 경우 함수 자체는 많지만 대부분 libc 내부 함수이므로, REV-0646(정적 링킹된 ELF 분석 접근법)을 참고해 실제 사용자 코드만 골라내야 한다.

**4) 자동 분석 강제 재실행**
- Ghidra: `Analysis > Auto Analyze` 메뉴에서 대상 바이너리를 다시 선택하고 "Non-Returning Functions - Discovered"와 "Function Start Search" 옵션이 체크되어 있는지 확인한 뒤 재실행한다.
- IDA: `Options > General > Analysis` 에서 코드 인식이 꺼져 있지 않은지 확인하고, entry point에서 커서를 두고 **C** 키(코드로 변환) 후 **P**(함수로 변환)를 눌러본다.

**5) 수동으로 함수 시작점 만들기**
자동 인식이 실패한 지점(예: entry point 직후, 혹은 CALL로 참조되는데 함수로 안 잡힌 주소)에 커서를 놓고 IDA는 **P**, Ghidra는 우클릭 > `Create Function`으로 강제 지정한다.

## 명령어/단축키
```bash
file ./chall
readelf -h ./chall
ldd ./chall
objdump -d ./chall | grep -c '^[0-9a-f]* <'
```
IDA: `C`(코드로 변환), `P`(함수로 변환), `Ctrl+P`(함수 목록)
Ghidra: `Analysis > Auto Analyze`, 우클릭 `Create Function`, `Window > Bookmarks`(분석 실패 지점 확인)

## 출력 해석
- `ldd: not a dynamic executable` → 정적 링킹, 함수는 많지만 이름 없는 libc 함수가 대부분.
- DIE에서 엔트로피 그래프가 특정 섹션에서 갑자기 치솟는다면 그 구간이 압축/암호화된 실제 코드일 가능성이 높다.
- `objdump -d`로 센 함수 개수와 IDA/Ghidra Functions 창의 개수가 크게 다르면, 도구의 자동 분석이 실패했다는 뜻이다.

## 흔한 실수
- 함수 개수가 적은 걸 보고 "이 문제는 로직이 짧구나"라고 성급히 결론짓는 것 — 대부분은 분석 실패지 실제 로직이 짧은 게 아니다.
- 정적 링킹된 바이너리에서 "함수가 몇 개 없다"고 착각하는 것 — 실제로는 함수가 수백 개인데 대부분 libc 내부 함수라 눈에 안 띄는 것뿐이다.
- Ghidra 자동 분석이 아직 진행 중인데(하단 진행바) 결과를 성급히 확인하는 것.
- 패킹된 바이너리를 그대로 정적 분석하며 "왜 코드가 없지"라고 헤매는 것 — 언패킹이 먼저다.

## 막혔을 때 다음 체크
- 패킹이 의심되면 → REV-0224 패킹된 바이너리인지 의심하는 기준.
- 정적 링킹이 확인되면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법.
- 함수는 있는데 이름만 없는 것 같다면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이.
- Ghidra 옵션 자체가 원인 같다면 → REV-0157 Ghidra Auto Analysis 옵션.

## 미니 예제
```bash
$ file chall
chall: data

$ readelf -h chall
readelf: Error: Not an ELF file - it has the wrong magic bytes at the start
```
`file`이 ELF/PE로 인식조차 못 하고 `data`라고만 답한다면, 이건 "함수가 적은" 문제가 아니라 파일 자체가 패킹/암호화되어 헤더까지 가려진 상태다. 이럴 땐 REV-0332(문제 파일이 손상된 것처럼 안 열릴 때)를 먼저 확인한다.

```
Ghidra Listing:
00401000  ??  ??  ??  ??   <- 대부분 미정의 바이트
00401804  <FUN_00401804>   <- 유일하게 인식된 함수
```
`.text` 섹션 대부분이 `??`(미정의)로 남아있고 함수가 하나뿐이라면, entry point 근처만 언패킹 스텁이고 나머지는 런타임에 풀리는 구조일 가능성이 크다.

## 관련 글
- REV-0224 — 패킹된 바이너리인지 의심하는 기준
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0157 — Ghidra Auto Analysis 옵션

## 출처/검증
- 함수 프롤로그 패턴 기반 자동 함수 탐지 원리: Ghidra 공식 문서 "Auto-Analysis" 섹션 및 Hex-Rays IDA 문서 "Analysis options" 기준 (2026-09-09 검증).
- 섹션 엔트로피와 패킹 판별 관계: Detect It Easy 프로젝트 공식 문서 개념 설명 기준.
