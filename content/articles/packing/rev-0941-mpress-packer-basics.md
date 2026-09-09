---
id: REV-0941
title: "MPRESS 패커 기초 알아보기"
slug: "rev-0941-mpress-packer-basics"
category: "packing"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, DIE, PE-bear]
keywords: ["MPRESS", "MPRESS 언패킹", "mpress 패커란", "MPRESS stub", "MPRESS 시그니처", "aPLib 압축"]
aliases: ["mpress이 뭐임", "MPRESS 패킹 확인법", "mpress 언패킹 방법", "MPRESS x64 지원"]
symptom_keywords: ["DIE에서 MPRESS라고 뜸", "섹션 이름이 MPRESS1", "mpress 패킹된 exe 분석", "닷넷 exe인데 mpress로 감싸짐"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
MPRESS는 aPLib 압축 알고리즘 기반의 무료 실행 압축기로, x86과 x64 PE를 모두 지원하고 안티 디버깅 기능이 거의 없어 ASPack과 비슷한 수준으로 다루기 쉽지만, .NET 어셈블리를 감싸는 데도 종종 쓰여서 "패킹된 .NET" 상황과 혼동하기 쉽다는 점이 특이하다.

## 언제 검색해야 하나
- DIE 스캔 결과에 `MPRESS`라는 이름이 나올 때
- 섹션 이름이 `MPRESS1`, `MPRESS2`로 보일 때
- .NET 프로그램인데 DIE가 native 패커 시그니처와 `.NET`을 동시에 표시해서 혼란스러울 때
- x64 PE인데 UPX가 아닌 다른 압축 스텁이 있다는 것을 확인하고 싶을 때

## 핵심 개념
MPRESS는 Matthias Prager가 만든 무료 실행 압축기로, 내부적으로 aPLib이라는 가벼운 압축 라이브러리를 사용한다. 특징은 다음과 같다.

- **x86/x64 모두 지원**: UPX가 오랫동안 32비트 위주였던 시절에도 MPRESS는 x64 PE를 초기부터 지원했기 때문에, 64비트 전용 CTF 문제나 오래된 x64 malware 샘플에서 종종 발견된다.
- **안티 디버깅이 사실상 없음**: 순수 압축 목적의 패커라서 디버거 탐지, SEH 트릭 같은 방해 요소가 거의 없다. ASPack과 마찬가지로 스텁을 그대로 따라가면 OEP를 찾을 수 있다.
- **.NET 어셈블리도 감쌀 수 있음**: MPRESS는 순수 native PE뿐 아니라 .NET(관리 코드) 실행 파일의 리소스나 전체 파일을 압축하는 용도로도 쓰인 사례가 있다. 이 경우 DIE가 `.NET` 표시와 `MPRESS` 패커 표시를 동시에 보여줄 수 있는데, 이때는 REV-0951에서 다루는 .NET 특유의 언패킹 접근(코드가 IL이라는 점)과 REV-0944의 native 스텁 추적을 구분해서 적용해야 한다 — 스텁 자체는 native 코드로 실행되지만 그 안에 들어있는 진짜 페이로드가 .NET 어셈블리이기 때문이다.

### 스텁 구조
MPRESS 스텁도 다른 압축 패커들과 마찬가지로 `pushad` → 압축 해제 루프(aPLib 알고리즘 기반) → IAT 채우기 → `popad` → `jmp OEP` 흐름을 따른다. aPLib 압축 해제 루틴은 UPX의 LZMA/NRV 계열과 바이트 패턴이 다르므로, IDA/Ghidra 시그니처 DB에도 별도로 등록되어 있는 경우가 많다.

## 화면/코드에서 보이는 징후
- DIE에 `MPRESS v2.19 -> Matthias Prager` 형태의 시그니처
- 섹션 이름 `MPRESS1`, `MPRESS2`
- x86과 x64 PE 양쪽에서 동일한 패턴의 스텁 관찰 가능(레지스터 크기만 다름 — x64는 `pushad` 대신 개별 레지스터를 `push`하는 방식으로 대체되는 경우가 많다는 점에 유의)
- 안티 디버깅 관련 팝업이나 예외가 거의 발생하지 않음

## 가장 먼저 할 것
DIE로 MPRESS 여부와 대상 아키텍처(x86/x64)를 확인한다. .NET 표시가 같이 뜬다면 먼저 페이로드가 진짜 native 코드인지 IL(.NET)인지부터 구분한다 — 방법은 언패킹 후 파일을 `dnSpyEx`나 `ILSpy`로 열어보거나, 언패킹 전 파일 자체에 `mscoree.dll` import나 `.NET` 관련 디렉토리 헤더가 있는지 REV-0136 방식으로 확인하는 것이다.

## 단계별 절차
1. DIE로 `MPRESS` 버전과 대상 비트수 확인, `.NET` 동시 표시 여부 확인
2. 원본 백업
3. x64dbg로 로드, entry point 스텁 확인(x64는 개별 `push` 나열, x86은 `pushad`)
4. 압축 해제 루프 종료 후 IAT 채우기 루틴이 끝나는 지점을 찾아 `jmp OEP` 확인
5. OEP에서 정지 후 코드 스타일 확인 — native 코드(함수 프롤로그)면 REV-0945로, .NET 로더 코드(예: `mscoree.dll`의 `_CorExeMain` 호출)로 이어지면 REV-0951로 이동
6. native면 Scylla로 덤프 + IAT 복구
7. .NET이면 덤프된 파일을 `dnSpyEx`로 열어 어셈블리 구조 확인

## 명령어/단축키
- DIE: `File → Open` 후 상단 배너에서 패커/CLR 헤더 여부 확인
- x64dbg: `F8`(Step Over)로 압축 해제 루프를 빠르게 넘기고, `F7`(Step Into)로 IAT 채우기 루틴 세부 관찰
- x64dbg 커맨드바: `bp <jmp_oep_addr>`

## 출력 해석
- DIE에서 `.NET` 항목이 함께 표시되면 native 패커 시그니처는 "겉포장"일 뿐이고 실제 프로그램 로직은 IL 코드 안에 있을 가능성이 높다. 이 경우 native 언패킹만으로는 분석이 끝나지 않는다.
- 압축 해제 루프가 끝난 직후 코드가 `call mscoree.dll!_CorExeMain` 형태라면 이 실행 파일은 결국 .NET 런타임을 로드하는 native 부트스트랩일 뿐이다.

## 흔한 실수
- MPRESS를 무조건 순수 native 패커로 가정하고 언패킹 후에도 IDA에서 의미 있는 함수가 안 보이는 것을 이상하게 여기는 것 — 사실은 .NET 페이로드였을 수 있다.
- x64 스텁에서 `pushad`가 안 보인다고 "MPRESS가 아니다"라고 오판하는 것. x64는 애초에 `pushad`/`popad` 명령이 없으므로 개별 레지스터 push/pop으로 대체된다.
- .NET과 native가 섞인 상황에서 native 언패킹 도구(Scylla 등)로 IAT 복구를 시도하며 시간을 낭비하는 것.

## 막혔을 때 다음 체크
- 언패킹 후에도 IDA에서 함수가 거의 안 보인다면 → REV-0136 .NET EXE인지 Native EXE인지 구분, REV-0951 패킹된 .NET 바이너리 기초
- OEP까지는 native인데 그 다음이 .NET 로더라면 → REV-0242 .NET 바이너리 식별과 첫 접근
- 순수 native로 확인되었다면 → REV-0945 IAT 복구 개념으로 계속 진행
- 예상보다 스텁이 복잡하다면 → 다른 패커가 위에 한 번 더 씌워진 이중 패킹 가능성, REV-0224 체크리스트 재확인

## 미니 예제
```text
; x64 MPRESS 스텁 예시(개별 레지스터 push로 pushad 대체)
entry:
  push rax
  push rbx
  push rcx
  push rdx
  ; aPLib 압축 해제 루프
  call decompress_aplib
  ; IAT 채우기
  call resolve_imports
  pop rdx
  pop rcx
  pop rbx
  pop rax
  jmp OEP
```
OEP에서 `call mscoree.dll!_CorExeMain`이 보인다면 이 바이너리는 사실 .NET 실행 파일을 감싼 native 래퍼이며, 진짜 분석 대상은 REV-0951에서 다루는 IL 코드다.

## 관련 글
- REV-0939 — ASPack 패커 기초 알아보기
- REV-0136 — .NET EXE인지 Native EXE인지 구분
- REV-0242 — .NET 바이너리 식별과 첫 접근
- REV-0951 — 패킹된 .NET 바이너리(ConfuserEx 등) 기초 알아보기
- REV-0945 — 언패킹 후 IAT를 복구하는 개념(Import Reconstruction)

## 출처/검증
- MPRESS의 aPLib 기반 압축과 x86/x64 지원 범위는 MPRESS 공식 배포 페이지(마티아스 프라거) 및 공개 리버싱 자료에서 공통적으로 확인되는 설명을 기준으로 정리했다.
- .NET 어셈블리를 native 실행 압축기로 감싸는 사례는 다수의 malware 분석 리포트와 CTF 라이트업에서 반복 관찰되는 패턴을 참고했다(2026-09-09 검증).
