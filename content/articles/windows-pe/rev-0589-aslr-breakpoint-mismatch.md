---
id: REV-0589
title: "ASLR 때문에 x64dbg 브레이크포인트 주소가 안 맞을 때"
slug: "rev-0589-aslr-breakpoint-mismatch"
category: "windows-pe"
difficulty: "basic"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["ASLR", "IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE", "ImageBase", "rebase", "모듈 베이스 주소", "bp module+offset"]
aliases: ["bp 주소가 안 걸림", "ida 주소랑 x64dbg 주소가 다름", "brekapoint가 엉뚱한 곳에 걸림"]
symptom_keywords: ["ida에서 본 주소로 bp 걸었는데 안 멈춘다", "실행할 때마다 코드 주소가 바뀐다", "x64dbg 브레이크포인트가 실행할 때마다 다른 곳에 걸린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
IDA 정적 분석 화면에서 본 주소(예: `0x140012340`)를 그대로 복사해 x64dbg에서 `bp 0x140012340`으로 걸었는데 안 멈추는 이유는, PE의 `DllCharacteristics`에 `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE`(0x0040) 비트가 켜져 있어 **ASLR**로 실제 로드 베이스가 IDA가 가정한 기본 `ImageBase`와 다르기 때문이며, 해결책은 고정 주소 대신 `bp 모듈명+오프셋` 형식의 심볼릭 표현을 쓰는 것이다.

## 언제 검색해야 하나
- x64dbg에서 IDA 주소를 그대로 복사해 브레이크포인트를 걸었는데 실행해도 전혀 멈추지 않을 때
- 같은 파일을 실행할 때마다 코드/데이터 주소가 매번 달라 보일 때
- DLL을 분석 중인데 EXE 프로세스에 로드될 때마다 그 DLL의 베이스 주소가 바뀌어서 주소를 못 믿겠을 때

## 핵심 개념
PE의 `OptionalHeader.ImageBase`는 링커가 "가급적 이 주소에 로드해달라"고 지정한 **선호 베이스 주소**일 뿐이다. `OptionalHeader.DllCharacteristics`에 `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE`(0x0040) 비트가 설정되어 있으면, Windows 로더는 프로세스를 만들 때마다 이 선호 주소가 아니라 무작위로 재배치된 주소에 이미지를 매핑한다. 이것이 **ASLR(Address Space Layout Randomization)**이다. Windows Vista 이후 링커 기본값이 ASLR 활성화이므로, 최신 Visual Studio로 빌드한 실행 파일/DLL은 특별히 끄지 않는 한 대부분 이 비트가 켜져 있다.

IDA는 정적 분석 시 기본적으로 `OptionalHeader.ImageBase` 값을 그대로 데이터베이스의 베이스 주소로 사용해서 모든 함수/데이터 주소를 표시한다. 하지만 실제로 x64dbg에서 그 파일을 실행하면, ASLR 때문에 실제 로드 베이스가 IDA가 가정한 값과 다를 수 있다(EXE의 경우 실행할 때마다 달라짐, DLL의 경우 다른 모듈이 이미 그 주소를 쓰고 있으면 재배치됨). 그 결과 IDA 화면에서 읽은 절대 주소를 x64dbg에 그대로 입력하면, 실제 메모리에는 전혀 다른 코드가 있는 엉뚱한 위치를 가리키게 되어 브레이크포인트가 걸리지 않거나 걸려도 의미 없는 곳에서 멈춘다.

## 화면/코드에서 보이는 징후
- x64dbg의 CPU 탭에서 실행 파일의 실제 로드 베이스가 IDA 하단 상태바나 `Edit → Segments`에 표시된 `ImageBase`와 다름
- 같은 `bp <고정주소>` 명령을 실행할 때마다 걸리는 곳이 다르거나 아예 안 걸림
- x64dbg의 `Memory Map` 탭에서 대상 모듈의 시작 주소가 매 실행마다 달라짐
- PE-bear/CFF Explorer로 확인한 `DllCharacteristics`에 `DYNAMIC_BASE` 플래그가 체크되어 있음

## 가장 먼저 할 것
브레이크포인트를 절대 주소(VA)로 걸지 말고, x64dbg의 표현식 평가기가 지원하는 **`모듈명+오프셋`** 형식으로 건다. 예를 들어 IDA에서 확인한 함수가 이미지 베이스 기준으로 `+0x12340`(RVA) 위치에 있다면, x64dbg에서 `bp target.exe+12340`처럼 입력한다. x64dbg는 이 표현식을 현재 실제로 로드된 모듈의 베이스 주소에 오프셋을 더해 자동으로 계산해주므로 ASLR과 무관하게 항상 올바른 위치에 브레이크포인트가 걸린다.

## 단계별 절차
**1) IDA에서 함수의 RVA(오프셋) 구하기**
- IDA에서 대상 함수 주소를 확인한 뒤, `함수 주소 − ImageBase`로 RVA를 계산한다. IDA 하단 상태바에 현재 커서 위치의 오프셋이 표시되는 경우도 있다.

**2) x64dbg에서 모듈+오프셋 형식으로 브레이크포인트 걸기**
```text
bp target.exe+12340
```
- 여기서 `target.exe`는 파일 확장자를 포함한 실제 모듈 이름이고, `12340`은 16진수 RVA다(접두사 `0x` 없이 입력).
- DLL 안의 함수라면 `bp somelib.dll+3400`처럼 해당 DLL 모듈명을 쓴다.

**3) 실제 걸린 주소 확인**
- `Breakpoints` 탭(하단 탭)에서 방금 건 브레이크포인트를 확인하면, 실제로 계산된 절대 주소가 함께 표시된다. 이 값이 실행마다 달라지는지 재실행(`Ctrl+F2` → `F9`)해서 확인하면 ASLR이 실제로 적용되고 있는지 검증할 수 있다.

**4) (선택) 정적 분석과 동적 분석 주소를 맞추고 싶다면 ASLR을 끄고 테스트**
- 자신이 소유한 샘플을 재빌드할 수 있다면 링커 옵션에서 `/DYNAMICBASE:NO`로 ASLR을 끄고 다시 빌드하면 IDA와 x64dbg 주소가 항상 일치한다.
- 이미 빌드된 파일이라면 CFF Explorer 등으로 `DllCharacteristics`의 `DYNAMIC_BASE` 비트를 직접 꺼서 재배치를 강제로 비활성화할 수도 있다(단, 이는 원본 파일을 수정하는 것이므로 사본에만 적용한다).

## 명령어/단축키
```text
x64dbg: bp 모듈명+오프셋16진수   (예: bp target.exe+12340)
x64dbg: Ctrl+G로 주소 이동 시에도 동일한 모듈+오프셋 표현식 사용 가능
IDA: Edit → Segments로 현재 데이터베이스의 ImageBase 확인
```

## 출력 해석
- `Breakpoints` 탭에 표시되는 절대 주소가 매 실행마다 바뀐다면 ASLR이 정상 동작 중이라는 뜻이고, `모듈+오프셋` 방식이 아니면 브레이크포인트를 신뢰할 수 없다는 확인이기도 하다.
- `모듈명+오프셋` 표현식을 입력했는데 x64dbg가 "모듈을 찾을 수 없습니다" 류의 오류를 낸다면, 아직 그 모듈이 로드되기 전(예: 아직 실행하지 않은 DLL)이라 발생한 것이므로, 먼저 그 모듈이 로드되는 지점까지 실행한 뒤 다시 시도한다.

## 흔한 실수
- IDA에서 본 절대 주소를 아무 변환 없이 x64dbg에 그대로 붙여넣는 것 — EXE 자체도 ASLR 대상이라면 실행할 때마다 주소가 바뀐다.
- DLL 분석 시 "DLL은 항상 같은 주소에 로드된다"고 착각하는 것 — DLL도 `DYNAMIC_BASE`가 켜져 있으면 다른 모듈과의 주소 충돌 여부에 따라 매번 다른 위치에 재배치될 수 있다.
- ASLR과 REV-0588의 TLS 콜백 문제를 혼동하는 것 — 전자는 "주소가 안 맞아서" 안 걸리는 것이고, 후자는 "타이밍이 늦어서" 못 잡는 것으로 원인이 다르다.

## 막혔을 때 다음 체크
- 모듈+오프셋으로 걸었는데도 여전히 안 멈춘다면 → 그 모듈이 실제로 로드됐는지 x64dbg `Memory Map` 탭에서 먼저 확인한다.
- ASLR 우회 자체가 아니라 Entry Point 자체를 못 찾는 문제라면 → REV-0585(Entry Point를 찾을 수 없다는 오류가 뜰 때)를 참고한다.
- PE 헤더의 `DllCharacteristics` 필드 구조 자체가 궁금하면 → REV-0116(PE Header COFF Optional Header 읽기)을 참고한다.

## 미니 예제
IDA에서 어떤 함수가 `0x140015230`에 있는 것을 확인했고, 데이터베이스의 `ImageBase`는 `0x140000000`이라고 하자. RVA는 `0x140015230 - 0x140000000 = 0x15230`이다. x64dbg에서 다음과 같이 브레이크포인트를 건다.

```text
bp target.exe+15230
```

실제로 ASLR 때문에 이번 실행에서 모듈이 `0x7FF612340000`에 로드됐다면, x64dbg는 자동으로 `0x7FF612340000 + 0x15230 = 0x7FF612355230`을 계산해 그 주소에 브레이크포인트를 건다. 다음 실행에서 베이스가 또 바뀌어도 같은 명령을 다시 걸 필요 없이, 저장된 `모듈+오프셋` 브레이크포인트는 자동으로 새 베이스에 맞춰 재계산된다.

## 관련 글
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0588 — TLS 콜백 때문에 브레이크포인트가 먼저 안 걸릴 때
- REV-0585 — Entry Point를 찾을 수 없다는 오류가 뜰 때
- REV-0121 — Entry Point와 WinMain 찾기

## 출처/검증
- `IMAGE_DLLCHARACTERISTICS_DYNAMIC_BASE` 비트와 ASLR의 관계는 Microsoft PE/COFF 형식 공식 문서 및 Microsoft Learn 링커 `/DYNAMICBASE` 옵션 문서 기준.
- x64dbg의 `모듈명+오프셋` 표현식 평가 기능은 x64dbg 공식 문서(Expression 문법)에 기술된 동작이며, 세부 UI는 버전에 따라 다를 수 있다(2026-09-08 기준 서술).
