---
id: REV-0965
title: "언패킹 후 원래 Entry Point로 못 돌아갈 때"
slug: "rev-0965-cant-return-to-original-entry-point"
category: "packing"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [x64dbg, "Scylla", "PE-bear", "Detect It Easy"]
keywords: ["Entry Point 복구 실패", "AddressOfEntryPoint 수정", "덤프 파일 EP 안맞음", "언패킹 검증 체크리스트", "unpacking verification checklist"]
aliases: ["덤프한 파일 entry point가 이상함", "언패킹 마무리 체크", "덤프 후 entry point 필드 수정"]
symptom_keywords: ["덤프 파일을 실행하면 원래 있던 곳이 아닌 이상한 곳에서 시작함", "PE 헤더의 AddressOfEntryPoint가 스텁 주소 그대로임", "덤프는 됐는데 실행하면 처음부터 다시 스텁이 실행됨", "언패킹이 끝난건지 확신이 안섬"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
OEP를 찾아 메모리를 덤프하고 IAT까지 복구했는데도 저장된 파일을 실행하면 여전히 원본(스텁) 코드부터 다시 시작하는 것처럼 보인다면, **PE 헤더의 `AddressOfEntryPoint` 필드가 여전히 패커 스텁의 주소를 가리키고 있어서** 언패킹 도구/절차가 이 필드를 OEP로 고쳐 쓰는 것을 빠뜨렸기 때문이다. 이 글은 패킹 카테고리를 마무리하며, 언패킹이 정말 끝났는지 확인하는 최종 체크리스트를 함께 정리한다.

## 언제 검색해야 하나
- Scylla로 덤프하고 Fix Dump까지 마쳤는데, 결과 파일을 실행하면 원래 있던 UPX/패커 스텁 코드가 다시 처음부터 실행되는 것처럼 보일 때
- PE-bear로 덤프 파일을 열어 헤더를 확인했더니 `AddressOfEntryPoint` 값이 OEP 주소가 아니라 여전히 스텁 코드의 주소로 되어 있을 때
- "언패킹이 이제 다 끝난 건지" 확신이 안 서서, 뭘 더 확인해야 하는지 체크리스트가 필요할 때
- 이 시리즈(REV-0954~0964)의 여러 문제를 하나씩 해결하고 마지막으로 전체가 제대로 됐는지 검증하고 싶을 때

## 핵심 개념

### AddressOfEntryPoint란
PE 헤더의 Optional Header 안에는 `AddressOfEntryPoint`라는 필드가 있는데, 이는 "이 실행 파일을 로더가 로드한 뒤 실행을 시작할 RVA(상대 가상 주소)"를 가리킨다. 패킹된 파일에서는 이 값이 원본 프로그램이 아니라 **패커 스텁의 시작 주소**로 설정되어 있다. 수동 언패킹의 목표 중 하나는 이 필드를 원본 OEP 주소로 바꿔서, 실행 시 곧바로 원본 코드부터 시작하도록 만드는 것이다.

### 왜 이 필드를 고치는 걸 빠뜨리기 쉬운가
Scylla 같은 도구는 "메모리 덤프"와 "IAT 복구(Fix Dump)"에 초점이 맞춰져 있어서, 이 두 가지만 하면 언패킹이 끝났다고 착각하기 쉽다. 하지만 Scylla의 `Fix Dump`는 기본적으로 IAT 관련 필드만 수정하며, `AddressOfEntryPoint`를 OEP로 맞추는 것은 **덤프를 뜨는 시점에 Scylla에게 OEP 주소를 정확히 알려줬는지**에 달려 있다. Scylla 플러그인 창의 OEP 입력란에 값을 정확히 입력하지 않고 기본값(패커의 원래 entry point)을 그대로 둔 채 덤프하면, 코드 내용은 언패킹된 상태로 저장되지만 헤더의 시작 주소만 여전히 스텁을 가리키는 어중간한 결과물이 나온다.

### 확인 방법
PE-bear나 CFF Explorer 같은 도구로 덤프 파일을 열어 Optional Header의 `AddressOfEntryPoint` 값을 직접 확인하고, 이 값이 실제로 OEP였던 주소(파일 오프셋이 아니라 RVA 기준)와 일치하는지 대조한다.

## 화면/코드에서 보이는 징후
- 덤프 파일을 실행하면 x64dbg에서 처음부터 다시 압축 해제 루프나 API resolve 코드가 보인다(원래 스텁이 다시 실행되고 있다는 뜻).
- PE-bear의 Optional Header 뷰에서 `AddressOfEntryPoint`가 스텁 코드가 있던 섹션(예: 원래 UPX0)의 범위 안에 있고, OEP가 있던 섹션(원래 UPX1 또는 .text) 범위 밖에 있다.
- IDA로 덤프 파일을 열었을 때, 자동으로 이동되는 Entry Point 위치가 예상한 OEP와 다르다.

## 가장 먼저 할 것
덤프 파일을 PE-bear로 열어 `AddressOfEntryPoint` 값부터 확인한다. 이 값이 원본 OEP의 RVA와 일치하는지가 이 문제의 핵심이다.

## 단계별 절차
1. PE-bear(또는 CFF Explorer)로 덤프 파일을 열어 `Optional Header`의 `AddressOfEntryPoint` 값을 확인한다.
2. x64dbg에서 확인했던 OEP의 VA(가상 주소)에서 이미지 베이스(ImageBase)를 빼서 RVA로 환산한 값과 비교한다.
3. 값이 다르다면, Scylla를 다시 열어 `OEP` 입력란에 정확한 OEP 주소(VA)를 직접 입력한 뒤 `Dump` 버튼으로 다시 덤프한다. Scylla는 이 입력란의 값을 기준으로 `AddressOfEntryPoint`를 RVA로 환산해 자동으로 고쳐 써준다.
4. Scylla를 쓰지 않고 직접 헤더를 고치는 경우, PE-bear의 헤더 편집 기능이나 HxD로 해당 필드(Optional Header 내 오프셋)를 직접 원하는 RVA 값으로 수정한다.
5. 수정 후 파일을 다시 실행해서, x64dbg에서 시작하자마자 곧바로 원본 코드(더 이상 스텁이 아닌)로 진입하는지 확인한다.

## 명령어/단축키
- PE-bear: 파일 열기 → 좌측 트리 `Optional Header` 클릭 → `AddressOfEntryPoint` 필드 확인/더블클릭으로 수정
- Scylla: `Plugins → Scylla` → OEP 입력란에 정확한 주소 입력 → `Dump`
- RVA 계산: `OEP(VA) - ImageBase = RVA` (ImageBase는 PE-bear의 Optional Header에서 확인)

## 출력 해석
- `AddressOfEntryPoint`가 OEP의 RVA와 정확히 일치하면 이 문제는 해결된 것이다.
- 실행 후 x64dbg에서 곧바로 정상적인 함수 프롤로그와 원본 API 호출이 보인다면 최종적으로 언패킹이 끝났다고 볼 수 있다.

## 흔한 실수
- Scylla의 OEP 입력란을 기본값 그대로 두고 덤프해서, 코드는 풀렸지만 시작 주소만 스텁을 가리키는 어중간한 파일을 만드는 것.
- IAT 복구(Fix Dump)만 하면 언패킹이 끝났다고 생각하고 Entry Point 필드를 확인하지 않는 것.
- RVA와 VA(가상 주소)를 혼동해서 잘못된 값을 헤더에 입력하는 것 — 반드시 ImageBase를 뺀 RVA 값을 넣어야 한다.

## 막혔을 때 다음 체크
- 이 문제까지 해결했는데도 실행이 이상하다면 → REV-0955(언패킹한 덤프가 크래시가 날 때)의 IAT 관련 절차를 다시 확인한다.
- OEP 자체가 맞는지 다시 의심된다면 → REV-0956(OEP를 찾았는데 실행이 이상하게 될 때)을 참고한다.

## 언패킹 검증 체크리스트 (마무리)
이 시리즈(REV-0954~0965)를 거치며 다룬 문제들을 하나로 모은 최종 점검표다. 언패킹 결과물을 "완료"로 판단하기 전에 아래 항목을 순서대로 확인한다.

1. **자동 도구 결과 재확인** — `upx -d` 등 자동 도구를 썼다면, 결과 파일을 Detect It Easy로 다시 스캔해 패커 시그니처가 완전히 사라졌는지 확인한다(REV-0954, REV-0960).
2. **OEP 확신** — OEP로 판단한 지점에서 함수 프롤로그와 원본 문자열 참조가 자연스럽게 보이는지 확인한다(REV-0956).
3. **덤프 무결성** — 덤프한 파일을 IDA로 열어 함수 개수와 코드 내용이 정상적인지 확인한다(REV-0955, REV-0962).
4. **IAT 복구** — Scylla의 `Get Imports`에 invalid 항목이 없는지 확인한다(REV-0958).
5. **Entry Point 필드** — `AddressOfEntryPoint`가 OEP의 RVA와 일치하는지 확인한다(이 글).
6. **문자열/로직 확인** — Strings 창에 원본 문자열이 정상적으로 보이고, 필요한 로직(비교 함수 등)을 읽을 수 있는지 확인한다(REV-0963).
7. **최종 실행 검증** — 덤프 파일을 실제로 실행해서, 원본 패킹 파일과 동일한 입력에 동일하게 반응하는지 비교한다.

7개 항목을 모두 통과하면 그 언패킹 결과물은 정적 분석에 안심하고 사용할 수 있는 상태다.

## 미니 예제
```text
1) PE-bear로 dumped_fixed.exe 열기
   -> ImageBase: 0x00400000
   -> AddressOfEntryPoint: 0x00005A10 (RVA)
   -> 실제 VA로 환산: 0x00400000 + 0x00005A10 = 0x00405A10
2) x64dbg로 확인했던 진짜 OEP: 0x004012C0 (VA)
   -> RVA로 환산: 0x004012C0 - 0x00400000 = 0x000012C0
3) 0x00005A10 != 0x000012C0 -> 헤더가 여전히 스텁 주소를 가리키는 것 확인
4) Scylla 재실행, OEP 입력란에 0x004012C0 입력 후 Dump
5) 재확인 -> AddressOfEntryPoint = 0x000012C0, VA 환산 시 0x004012C0과 일치
6) dumped_fixed.exe 실행 -> x64dbg에서 시작 즉시 원본 함수 프롤로그 확인, 정상 완료
```

## 관련 글
- REV-0227 — 수동 언패킹 개념 OEP와 Dump
- REV-0955 — 언패킹한 덤프가 크래시가 날 때
- REV-0956 — OEP를 찾았는데 실행이 이상하게 될 때
- REV-0958 — Import Table이 언패킹 후에도 비어있을 때

## 출처/검증
- PE 헤더의 `AddressOfEntryPoint` 필드 정의와 RVA/VA 관계: Microsoft PE/COFF 공식 명세 문서(Microsoft PE Format Specification) 기준(2026-09-09 검증).
- Scylla의 OEP 입력 및 Dump 시 Entry Point 필드 재기록 동작: Scylla 공식 저장소(github.com/NtQuery/Scylla) 문서 및 소스 코드 기준.
