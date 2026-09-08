---
id: REV-0115
title: "DOS Header와 MZ 시그니처"
slug: "rev-0115-dos-header"
category: "windows-pe"
difficulty: "beginner"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, "PE-bear", x64dbg]
keywords: ["DOS Header", "IMAGE_DOS_HEADER", "MZ 시그니처", "e_magic", "e_lfanew", "DOS Stub"]
aliases: ["MZ 헤더", "mz로 시작하는 이유", "e_lfanew란", "dos header 구조", "dos stub이란"]
symptom_keywords: ["파일이 MZ로 시작하는 이유가 궁금함", "e_lfanew 값이 뭔지 모름", "dos stub 메시지가 왜 있는지 모름", "헥스에디터에서 PE 헤더 시작 위치를 못 찾음"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
모든 PE 파일은 파일 맨 앞 64바이트에 DOS 시절 흔적인 `IMAGE_DOS_HEADER`를 갖고 있으며, 이 구조체에서 현대 PE 분석에 실질적으로 의미 있는 필드는 매직 넘버 `e_magic`(`"MZ"`)과 진짜 PE 헤더 위치를 가리키는 `e_lfanew` 단 두 개뿐이다.

## 언제 검색해야 하나
- 헥스에디터로 `.exe` 파일을 열었을 때 맨 앞 2바이트가 항상 `4D 5A`(`MZ`)인 이유가 궁금할 때
- "이 프로그램은 DOS 모드에서 실행할 수 없습니다(This program cannot be run in DOS mode)"라는 문자열이 실행 파일 안에 왜 들어 있는지 궁금할 때
- PE 헤더(`IMAGE_NT_HEADERS`)가 파일 정확히 몇 바이트 지점에서 시작하는지 계산하고 싶을 때
- 직접 PE 파서를 짤 때 `IMAGE_DOS_HEADER` 구조체의 각 필드 크기와 오프셋을 알아야 할 때

## 핵심 개념

### 왜 지금도 DOS Header가 남아 있나
PE 포맷은 Windows NT를 설계할 때 완전히 새로 만든 게 아니라, 기존 MS-DOS의 `MZ` 실행 파일 포맷 위에 확장하는 방식으로 설계됐다. 그 이유는 하위 호환성이었다 — 같은 파일을 DOS에서 실행하면 "이 프로그램은 DOS에서 못 돌아갑니다"라는 안내 메시지를 띄우는 작은 16비트 DOS 프로그램(**DOS Stub**)이 실행되고, Windows에서 실행하면 로더가 DOS Header를 건너뛰고 뒤에 있는 진짜 PE 헤더를 찾아서 정상적으로 실행한다. 이 이중 설계 덕분에 하나의 파일이 두 환경 모두에서 "말이 되는" 동작을 할 수 있었다. 지금은 DOS 자체가 거의 쓰이지 않지만, 파일 포맷 하위 호환성 때문에 이 구조는 오늘날 만들어지는 PE 파일에도 그대로 남아 있다.

### IMAGE_DOS_HEADER 구조체
`winnt.h`에 정의된 이 구조체는 정확히 **64바이트**이며, 파일의 절대 오프셋 `0x00`에서 시작한다.

```c
typedef struct _IMAGE_DOS_HEADER {
    WORD   e_magic;      // 0x00: 매직 넘버, 반드시 "MZ" (0x5A4D)
    WORD   e_cblp;       // 0x02: 마지막 페이지의 바이트 수 (DOS 로더용, 무의미)
    WORD   e_cp;         // 0x04: 파일의 페이지 수 (DOS 로더용, 무의미)
    WORD   e_crlc;       // 0x06: 재배치 항목 수 (DOS 로더용, 무의미)
    WORD   e_cparhdr;    // 0x08: 헤더 크기 (paragraph 단위, DOS 로더용)
    WORD   e_minalloc;   // 0x0A: 최소 추가 메모리 (DOS 로더용, 무의미)
    WORD   e_maxalloc;   // 0x0C: 최대 추가 메모리 (DOS 로더용, 무의미)
    WORD   e_ss;         // 0x0E: 초기 SS 값 (DOS 로더용, 무의미)
    WORD   e_sp;         // 0x10: 초기 SP 값 (DOS 로더용, 무의미)
    WORD   e_csum;       // 0x12: 체크섬 (거의 사용 안 함)
    WORD   e_ip;         // 0x14: 초기 IP 값 (DOS 로더용, 무의미)
    WORD   e_cs;         // 0x16: 초기 CS 값 (DOS 로더용, 무의미)
    WORD   e_lfarlc;     // 0x18: 재배치 테이블 오프셋 (DOS 로더용, 무의미)
    WORD   e_ovno;       // 0x1A: 오버레이 번호 (DOS 로더용, 무의미)
    WORD   e_res[4];     // 0x1C: 예약 (0)
    WORD   e_oemid;      // 0x24: OEM 식별자
    WORD   e_oeminfo;    // 0x26: OEM 정보
    WORD   e_res2[10];   // 0x28: 예약 (0)
    LONG   e_lfanew;     // 0x3C: ★ 진짜 PE 헤더(IMAGE_NT_HEADERS)의 파일 오프셋
} IMAGE_DOS_HEADER;      // 총 크기: 64바이트 (0x40)
```

이 필드들 중 실제로 Windows PE 로더와 현대 리버싱 작업에 의미가 있는 건 딱 두 개다.

**1) `e_magic` (오프셋 0x00, 2바이트)**

값이 항상 `0x5A4D`여야 하며, 이걸 리틀엔디안 바이트 순서로 파일에 저장하면 `4D 5A`가 되고, 이 두 바이트를 ASCII로 읽으면 `"MZ"`가 된다. 이 이니셜은 초기 MS-DOS 실행 파일 포맷을 설계한 **Mark Zbikowski**라는 실제 인물의 이니셜에서 따온 것으로 널리 알려져 있다. Windows 로더는 파일을 열자마자 이 두 바이트가 `MZ`가 아니면 곧바로 "이 파일은 유효한 실행 파일이 아니다"라며 실행을 거부한다.

**2) `e_lfanew` (오프셋 0x3C, 4바이트)**

이름 자체가 "**l**ogical **f**ile **a**ddress of **new** exe header"의 줄임말로, 값은 **파일 시작(오프셋 0)으로부터 `IMAGE_NT_HEADERS`(진짜 PE 헤더)까지의 바이트 오프셋**이다. 이 필드가 없다면 로더는 DOS Stub이 얼마나 긴지(가변 길이!) 일일이 파싱해서 PE 헤더 시작점을 찾아야 하는데, `e_lfanew` 덕분에 그럴 필요 없이 한 번에 점프할 수 있다. 실무에서 PE 파일을 다룰 때 "DOS Header를 읽는다"는 사실상 "이 4바이트(`e_lfanew`)만 읽고 나머지 60바이트는 무시한다"는 뜻이나 마찬가지다.

나머지 필드들(`e_cblp`, `e_cp`, `e_crlc` 등)은 순수하게 DOS 시절 16비트 `EXE` 로더가 세그먼트 기반 메모리를 계산하는 데 쓰던 값들로, 오늘날 Windows PE 로더나 리버싱 작업에서는 거의 항상 무시해도 무방하다.

### DOS Stub이란
DOS Header(64바이트) 바로 뒤, `e_lfanew`가 가리키는 오프셋까지의 공간에는 실제로 실행 가능한 작은 16비트 DOS 프로그램이 들어 있다. 이 프로그램의 역할은 딱 하나 — 화면에 다음과 같은 메시지를 출력하고 종료하는 것이다.

```text
This program cannot be run in DOS mode.
```

이 문자열은 대부분의 컴파일러(예: Visual Studio 링커)가 기본으로 삽입하는 표준 DOS Stub의 일부이며, 파일을 헥스에디터나 `strings`로 훑을 때 파일 맨 앞부분에서 거의 항상 볼 수 있는 문자열이다. DOS Stub은 선택 사항이라 이론적으로는 링커 옵션으로 최소화하거나 커스텀 메시지로 바꿀 수도 있지만, 실무에서 보는 PE 파일 대부분은 이 표준 메시지를 그대로 갖고 있다.

### DOS Header와 PE Header 사이의 관계 정리
```text
파일 오프셋 0x00                     e_lfanew가 가리키는 오프셋
      │                                      │
      ▼                                      ▼
┌───────────────┬─────────────────┬──────────────────────┐
│ IMAGE_DOS_HEADER│   DOS Stub      │  IMAGE_NT_HEADERS      │
│   (64바이트)     │  (가변 길이)      │  "PE\0\0" 로 시작       │
└───────────────┴─────────────────┴──────────────────────┘
```
`e_lfanew` 값은 컴파일러/링커 설정에 따라 달라지며, Visual Studio 기본 링커로 만든 64비트 실행 파일이라면 흔히 `0xE8` ~ `0xF8` 근처의 값을 갖는다. 이 값이 정확히 얼마인지는 파일마다 다르므로, "PE 헤더는 항상 오프셋 0x80에 있다" 같은 식으로 고정 오프셋을 외우면 안 되고, 반드시 `e_lfanew` 필드를 읽어서 확인해야 한다.

## 화면/코드에서 보이는 징후
- 헥스에디터로 파일을 열었을 때 오프셋 `0x00`~`0x01`이 `4D 5A`
- 오프셋 `0x3C`에 4바이트 값(리틀엔디안)이 있고, 그 값이 가리키는 위치에 `50 45 00 00`(`PE\0\0`)이 있음
- 파일에 `strings`나 `Sysinternals Strings`를 돌리면 파일 맨 앞부분에서 `This program cannot be run in DOS mode.` 문자열이 항상 보임
- PE-bear의 `DOS Header` 트리 항목을 클릭하면 `Magic`, `e_lfanew` 값이 표 형태로 보임

## 가장 먼저 할 것
어떤 PE 파일이든 분석 첫 단계로 헥스에디터에서 오프셋 `0x00`이 `4D 5A`인지부터 확인한다. 아니라면 이 파일은 PE가 아니거나 헤더가 손상/난독화된 것이므로 이후 분석 방향 자체가 달라진다. `4D 5A`를 확인했다면 바로 오프셋 `0x3C`로 이동해서 `e_lfanew` 값을 읽고, 그 오프셋으로 점프해서 `50 45 00 00`이 있는지 확인한다. 이 두 확인만으로 "이 파일이 정상적인 PE 구조를 갖고 있다"는 걸 몇 초 안에 검증할 수 있다.

## 단계별 절차

**1) 헥스에디터로 오프셋 0x00~0x01 확인 (HxD 기준)**
```text
HxD로 파일 열기 → Ctrl+G → 오프셋 0 입력 → 맨 앞 2바이트가 4D 5A인지 눈으로 확인
```

**2) 오프셋 0x3C로 이동해서 e_lfanew 읽기**
```text
Ctrl+G → 오프셋 0x3C(60) 입력 → 4바이트를 리틀엔디안으로 해석
예: 파일에 F8 00 00 00 이 보이면 → e_lfanew = 0x000000F8
```

**3) e_lfanew가 가리키는 오프셋으로 이동해서 PE 시그니처 확인**
```text
Ctrl+G → 위에서 읽은 값(예: 0xF8) 입력 → 4바이트가 50 45 00 00("PE\0\0")인지 확인
```

**4) PE-bear로 같은 내용을 자동으로 확인**
```text
PE-bear로 파일 열기 → 좌측 트리 "DOS Header" 클릭 → Magic / e_lfanew 값 표에서 바로 확인
→ 좌측 트리 "NT Headers" 클릭 → Signature가 "PE" 로 표시되는지 확인
```

## 명령어/단축키
```text
HxD: Ctrl+G (오프셋으로 이동)
PE-bear: 좌측 트리에서 DOS Header 클릭
Sysinternals Strings: strings.exe -n 8 파일.exe | findstr "cannot be run"
```

## 출력 해석
- `e_magic == 0x5A4D`이 아니면 이 파일은 표준 PE가 아니다. 일부 커스텀 로더/패커는 이 값을 의도적으로 바꿔서 일반 도구의 자동 파싱을 방해하기도 하므로, 값이 다르다면 "패킹/난독화 가능성"으로 의심해볼 수 있다.
- `e_lfanew` 값이 파일 전체 크기보다 크거나 음수처럼 보이는 이상한 값이면 헤더가 손상됐거나 의도적으로 조작된 파일일 수 있다.
- `e_lfanew`가 가리키는 위치의 4바이트가 `PE\0\0`이 아니라면 링크가 깨졌거나, 이 필드 자체가 안티 리버싱 목적으로 조작된 것일 수 있다 — 이런 경우 실제 로더가 참조하는 것은 이 필드가 맞는지, 아니면 다른 진입 경로(예: 커스텀 로더 코드)가 있는지 별도로 확인해야 한다.

## 흔한 실수
- `e_lfanew`가 항상 같은 고정값(예: 항상 `0x80`)이라고 외워버리는 것 — 컴파일러/링커 버전, DOS Stub 크기에 따라 파일마다 다르다. 반드시 필드 값을 직접 읽어야 한다.
- DOS Header의 다른 필드들(`e_cs`, `e_ip`, `e_ss` 등)을 실행 관련 의미 있는 값으로 착각하고 분석 시간을 쓰는 것 — 이 필드들은 순수 DOS 16비트 로더용이며 Windows PE 로더는 이 값들을 사실상 참조하지 않는다.
- DOS Stub 문자열이 항상 "This program cannot be run in DOS mode."라고 단정하는 것 — 링커 옵션이나 커스텀 스터브로 이 메시지가 바뀌거나 아예 다른 코드로 교체될 수 있으며, 일부 정교한 패커/프로텍터는 이 영역에 실제로 의미 있는 코드를 숨겨두기도 한다.
- `IMAGE_DOS_HEADER` 크기를 정확히 외우지 못해서 DOS Stub이 오프셋 `0x40`(64)부터 시작한다는 걸 놓치는 것 — DOS Header는 정확히 64바이트이므로 Stub은 항상 오프셋 `0x40`에서 시작한다.

## 막혔을 때 다음 체크
- `e_lfanew`가 가리키는 진짜 PE 헤더(`IMAGE_NT_HEADERS`)의 내부 필드가 궁금하면 → [REV-0116 PE Header COFF Optional Header 읽기](./rev-0116-pe-coff-optional-header.md)
- PE 전체 구조에서 DOS Header가 어느 위치인지 큰 그림이 다시 헷갈리면 → [REV-0114 PE 파일 구조 한 번에 보기](./rev-0114-pe-overview.md)
- RVA/VA/파일 오프셋 계산이 필요하면 → [REV-0118 RVA VA Raw Offset 계산](./rev-0118-rva-va-raw-offset.md)
- ELF의 시작 부분(ELF 헤더)과 비교하고 싶으면 → [ELF 헤더 읽는 법](../linux-elf/rev-0089-elf-header.md)

## 미니 예제
```text
오프셋 0x00: 4D 5A 90 00 03 00 00 00 04 00 00 00 FF FF 00 00   MZ..............
오프셋 0x10: B8 00 00 00 00 00 00 00 40 00 00 00 00 00 00 00   ........@.......
오프셋 0x20: 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   ................
오프셋 0x30: 00 00 00 00 00 00 00 00 00 00 00 00 F8 00 00 00   ............ø...
```
`0x00`에서 `4D 5A` 확인, `0x3C`(60번째 바이트)에서 `F8 00 00 00` → 리틀엔디안으로 `0x000000F8`. 따라서 진짜 PE 헤더는 파일 오프셋 `0xF8`에서 시작하며, 그 위치를 확인해보면 `50 45 00 00`(`PE\0\0`)이 있어야 정상이다.

## 관련 글
- REV-0114 — PE 파일 구조 한 번에 보기
- REV-0116 — PE Header COFF Optional Header 읽기
- REV-0117 — PE Section Table 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0089 — ELF 헤더 읽는 법

## 출처/검증
- `IMAGE_DOS_HEADER` 구조체 필드 정의: Microsoft Learn "PE Format" 공식 문서, `winnt.h` 정의 기준 (2026-09-08 검증).
- `e_lfanew` 필드 명칭 유래("logical file address of new exe header") 및 역할: Microsoft PE Format 문서 및 다수 리버싱 참고자료 공통 설명 기준.
- Mark Zbikowski와 `MZ` 매직 유래: 널리 알려진 PE 포맷 역사적 배경(다수 공개 리버싱/윈도우 내부구조 자료에서 공통적으로 언급).
