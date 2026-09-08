---
id: REV-0545
title: ".rdata 섹션 구조와 상수 데이터 읽는 법"
slug: "rev-0545-rdata-section-constants"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: [".rdata", "읽기 전용 데이터", "IMAGE_SCN_MEM_READ", "문자열 리터럴", "vtable", "switch 점프 테이블", "GS 쿠키", "IAT"]
aliases: ["rdata 섹션", "읽기전용 섹션", "상수 데이터 섹션", "read-only data section", "rdata 분석"]
symptom_keywords: [".rdata 섹션에서 문자열이 안 보인다", "vtable로 추정되는 포인터 배열이 rdata에 있다", "switch case 점프 테이블이 rdata에 있다", "rdata를 쓰려고 하면 access violation이 난다", "IAT가 rdata에 있는지 idata에 있는지 헷갈린다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`.rdata` 섹션은 PE 파일에서 "실행은 안 되지만 쓰기도 안 되는" 읽기 전용 초기화 데이터를 모아두는 곳으로, 문자열 리터럴·C++ vtable·switch-case 점프 테이블·부동소수점 상수·때로는 Import Address Table(IAT)까지 여기 들어가기 때문에, `.rdata`를 훑어보는 것만으로 프로그램이 어떤 문자열/타입/분기 구조를 갖는지에 대한 풍부한 정적 단서를 얻을 수 있다.

## 언제 검색해야 하나
- IDA/PE-bear에서 섹션 목록에 `.rdata`가 보이는데 이 섹션이 정확히 무엇을 담고 있는지 궁금할 때
- 문자열이 `.data`가 아니라 `.rdata`에 있는 이유가 궁금할 때
- C++ 바이너리를 분석하다가 함수 포인터 배열처럼 보이는데 실행 코드가 아닌 데이터로 표시된 영역(vtable 후보)을 발견했을 때
- `switch`/`case`가 많은 함수의 디스어셈블리에서 `jmp [rax*4 + offset]` 같은 코드를 만났을 때, 그 `offset`이 가리키는 테이블이 어디 있는지 찾고 싶을 때
- 실행 중 `.rdata` 영역에 값을 쓰려다가 `Access Violation`(쓰기 위반)이 나는 이유가 궁금할 때

## 핵심 개념

### 섹션 테이블에서의 정의
`.rdata`는 다른 모든 PE 섹션과 마찬가지로 특별한 헤더 구조가 있는 게 아니라, PE Section Table(REV-0117)의 `IMAGE_SECTION_HEADER` 엔트리 하나로 정의되는 "그냥 이름이 `.rdata`인 섹션"이다. 이 엔트리의 `Characteristics` 필드에는 보통 다음 플래그 조합이 설정된다.
- `IMAGE_SCN_CNT_INITIALIZED_DATA`(`0x00000040`): 파일에 초기값이 저장된 데이터.
- `IMAGE_SCN_MEM_READ`(`0x40000000`): 읽기 가능.
- 주의: `IMAGE_SCN_MEM_WRITE`(`0x80000000`)와 `IMAGE_SCN_MEM_EXECUTE`(`0x20000000`)는 **빠져 있다** — 이것이 "읽기 전용"이라는 이름의 근거다.

이 플래그 조합 때문에 Windows 로더는 `.rdata`가 매핑되는 메모리 페이지를 `PAGE_READONLY`로 보호한다. 런타임에 이 영역에 쓰기를 시도하면 `STATUS_ACCESS_VIOLATION`(쓰기 위반)이 발생한다.

### .rdata에 실제로 들어가는 것들
1. **문자열 리터럴**: `const char*`/`const wchar_t*`로 선언된 문자열 상수는 컴파일러가 자동으로 `.rdata`에 배치한다(반면 지역 배열 `char buf[100] = "hello"`처럼 런타임에 수정 가능한 문자열은 스택이나 `.data`에 복사됨).
2. **C++ vtable(가상 함수 테이블)**: 클래스에 가상 함수가 하나라도 있으면, 컴파일러는 그 클래스의 vtable(함수 포인터 배열)을 `.rdata`에 만들어 넣는다. IDA에서 함수 포인터들이 연속으로 나열된 배열을 발견하면 vtable 후보로 의심할 수 있다.
3. **switch-case 점프 테이블**: `case` 분기가 많고 값이 연속적인 `switch`문은 컴파일러가 개별 `cmp`/`je` 대신 점프 테이블(각 케이스의 목적지 주소 또는 상대 오프셋 배열)로 최적화하는 경우가 많고, 이 테이블 자체가 `.rdata`에 저장된다.
4. **부동소수점/SIMD 상수**: `double`/`float` 리터럴이나 SSE 명령어가 쓰는 상수 벡터는 레지스터에 즉시값으로 넣을 수 없어 메모리에서 로드해야 하므로 `.rdata`에 저장되고, `movsd xmm0, [rip+offset]` 같은 형태로 참조된다.
5. **__security_cookie 관련 상수, RTTI 정보**: 스택 보호(GS 쿠키) 관련 일부 상수나 C++ RTTI(런타임 타입 정보) 구조체도 여기 위치하는 경우가 많다.
6. **Import Address Table(IAT)**: 컴파일러/링커 설정에 따라 IAT가 별도의 `.idata` 섹션이 아니라 `.rdata`에 병합되어 들어가는 경우가 흔하다(특히 Visual Studio의 기본 링커 설정). 이 경우 Import 함수의 실제 호출은 `call [rdata의 IAT 슬롯]` 형태로 나타난다.

### .rdata vs .data vs .text 구분
| 섹션 | 실행(X) | 쓰기(W) | 읽기(R) | 대표 내용 |
|---|---|---|---|---|
| `.text` | O | X | O | 실행 코드 |
| `.rdata` | X | X | O | 상수/읽기 전용 데이터 |
| `.data` | X | O | O | 초기화된 전역/정적 변수(런타임에 값이 바뀔 수 있음) |

이 표만 기억해도 어떤 값이 왜 특정 섹션에 있는지 대부분 설명된다 — "이 값이 실행 중에 바뀔 수 있는가"가 `.rdata`와 `.data`를 가르는 핵심 기준이다.

### RVA/VA로 실제 위치 찾기
`.rdata`에 있는 데이터를 디스어셈블리에서 참조할 때는 RVA(Relative Virtual Address, REV-0118)를 통해 이루어진다. x64에서는 `lea rax, [rip+0x2000]`처럼 RIP 상대 주소 지정 방식이 흔히 쓰이고, x86에서는 절대 주소가 직접 `mov`/`push`의 즉시값으로 박혀 있는 경우가 많다.

## 화면/코드에서 보이는 징후
- IDA의 Segments 창(`Shift+F7`)에 `.rdata`가 `R`(읽기) 속성만 가지고 `W`(쓰기)/`X`(실행)는 없는 것으로 표시됨.
- IDA에서 `.rdata` 영역의 데이터를 더블클릭해 진입하면 `db`/`dq`(바이트/쿼드워드) 형태로 나열되고, 문자열은 자동으로 `aXxxxx` 이름이 붙은 채로 표시됨.
- `lea reg, [rdata_addr]` 또는 `mov reg, [rip+offset]` 형태로 상수를 로드하는 코드.
- 함수 포인터로 보이는 값들이 연속으로 나열된 배열(vtable 후보) — IDA가 자동으로 함수 시작 주소를 인식하면 각 항목에 `sub_XXXXXX`처럼 함수 이름이 붙어서 보이기도 한다.

## 가장 먼저 할 것
IDA에서 `Shift+F7`(Segments 창)을 열어 `.rdata`의 시작/끝 주소와 R/W/X 속성을 확인한다. 그 다음 `Shift+F12`(Strings 창)로 이 섹션에 있는 문자열들을 먼저 훑으면, 프로그램의 대략적인 기능(에러 메시지, API 이름, 힌트 문구 등)을 빠르게 파악할 수 있다.

## 단계별 절차
**1) 섹션 범위 확인**

PE-bear(REV-0125) 또는 IDA Segments 창에서 `.rdata`의 `VirtualAddress`/`VirtualSize`(REV-0117)를 확인해 이 섹션이 정확히 어느 범위인지 메모해둔다.

**2) 문자열부터 훑기**

`Shift+F12`로 Strings 창을 열고 주소 컬럼을 기준으로 `.rdata` 범위에 속하는 문자열만 필터링해서 본다. 에러 메시지, 포맷 문자열, 하드코딩된 키워드 등을 빠르게 훑을 수 있다.

**3) 포인터 배열(vtable 후보) 찾기**

`.rdata` 안에서 연속된 8바이트(x64)/4바이트(x86) 값들이 모두 `.text` 범위 안의 함수 주소를 가리키면 vtable일 가능성이 높다. IDA가 `off_XXXXXX` 형태의 오프셋 배열로 자동 인식하지 못했다면, 수동으로 `Array`(단축키 `*`)로 배열 지정 후 `Xrefs`로 각 항목을 확인한다.

**4) switch 점프 테이블 역추적**

`jmp [reg*4+table_addr]` 형태의 간접 점프를 만나면 IDA가 보통 자동으로 점프 테이블을 인식해 각 케이스로 화살표를 그려준다. 자동 인식이 안 됐다면 `table_addr`을 수동으로 배열로 지정한 뒤 각 값을 코드 주소로 변환(`D`→`C` 전환 또는 `Edit → Code`)해준다.

**5) x64dbg로 실행 중 값 확인**

정적으로 애매한 값은 x64dbg에서 해당 주소에 브레이크포인트를 걸고 실행 중 실제로 어떤 값이 로드되는지 `dump <주소>`로 직접 확인한다.

## 명령어/단축키
- IDA: `Shift+F7`(Segments), `Shift+F12`(Strings), `*`(배열로 지정), `D`(데이터로 변환), `C`(코드로 변환)
- IDA: 포인터 배열 선택 후 `Array`(구조체/배열 지정) 다이얼로그에서 원소 크기를 8바이트(x64)/4바이트(x86)로 지정
- x64dbg: `dump <rdata 주소>`(Dump 창으로 이동), 우클릭 → `Follow in Disassembler`(코드 주소를 가리키면 바로 이동)

## 출력 해석
- `.rdata`의 어떤 값이 `.text` 범위 안의 유효한 함수 시작 주소들로만 이루어져 있다면 vtable로 봐도 무방하다 — 이 vtable을 참조하는 생성자 코드를 찾으면 해당 클래스의 실제 크기와 가상 함수 목록을 재구성할 수 있다.
- 문자열 주소가 `.rdata` 범위 안이라면 이 문자열은 프로그램 실행 중 절대 수정되지 않는다 — 즉 이 문자열을 담는 버퍼를 변조해 프로그램 동작을 바꾸는 접근은 불가능하고, 대신 이 문자열을 참조하는 코드(비교/출력 로직)를 찾아 그쪽을 패치해야 한다.
- `.rdata`에 대한 쓰기 시도가 `Access Violation`을 일으켰다면, 이는 버그가 아니라 섹션 보호 속성이 의도대로 동작한 정상적인 결과다.

## 흔한 실수
- `.rdata`에 있는 문자열이 실행 중 바뀔 수 있다고 착각하고 그 주소에 패치를 시도했다가 페이지 보호 위반으로 실패하는 것 — 값을 바꾸려면 링커/컴파일러 단계에서 애초에 `.data`로 배치되게 하거나, 실행 중 `VirtualProtect`로 보호 속성을 임시로 바꿔야 한다.
- IAT가 항상 `.idata`라는 별도 섹션에 있다고 가정하는 것 — 많은 Visual Studio 빌드에서 IAT는 `.rdata`에 병합되어 들어간다.
- vtable 후보 배열을 그냥 데이터로만 보고 각 항목이 가리키는 함수(가상 함수 구현체)까지 따라가 보지 않는 것 — 클래스 구조를 재구성하는 데 핵심 단서를 놓치게 된다.
- switch 점프 테이블의 값이 절대 주소가 아니라 상대 오프셋(RVA 기반)으로 저장된 경우도 있는데, 이를 절대 주소로 착각해 잘못된 위치로 따라가는 것.

## 막혔을 때 다음 체크
- PE Section Table 자체의 필드 구조가 헷갈린다면 → REV-0117 PE Section Table 읽기
- RVA/VA/Raw Offset 변환이 헷갈린다면 → REV-0118 RVA VA Raw Offset 계산
- 다른 섹션 이름들의 관례를 한눈에 정리한 표가 필요하다면 → REV-0525 — PE Section 이름 관례 사전(.text .rdata .data .rsrc 등)
- x64 예외 처리 정보가 담긴 `.pdata` 섹션이 궁금하다면 → REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- PE-bear로 섹션을 처음 살펴보는 법이 낯설다면 → REV-0125 PE-bear로 헤더 분석하는 방법

## 미니 예제
```c
const char* g_errorMsg = "Invalid flag format!"; // .rdata에 배치됨

class Base {
public:
    virtual void Greet() { printf("Base\n"); }
    virtual void Bye()   { printf("Bye\n"); }
};
// Base의 vtable(함수 포인터 2개)도 .rdata에 배치됨

int Classify(int x) {
    switch (x) { // case가 연속적이면 점프 테이블(.rdata)로 컴파일될 수 있음
        case 0: return 10;
        case 1: return 20;
        case 2: return 30;
        default: return -1;
    }
}
```
IDA에서 `Classify` 함수를 열면 `jmp [rax*4 + jptr_XXXXXX]` 형태의 코드와 함께, `.rdata`에 있는 `jptr_XXXXXX` 배열(각 case의 목적지 주소 4개)을 확인할 수 있다.

## 관련 글
- REV-0117 — PE Section Table 읽기
- REV-0118 — RVA VA Raw Offset 계산
- REV-0525 — PE Section 이름 관례 사전(.text .rdata .data .rsrc 등)
- REV-0546 — .pdata 섹션과 x64 예외 처리 정보 읽는 법
- REV-0125 — PE-bear로 헤더 분석하는 방법

## 출처/검증
- `IMAGE_SECTION_HEADER.Characteristics` 플래그(`IMAGE_SCN_CNT_INITIALIZED_DATA`, `IMAGE_SCN_MEM_READ`, `IMAGE_SCN_MEM_WRITE`, `IMAGE_SCN_MEM_EXECUTE`)의 정의와 값은 Microsoft PE/COFF 공식 스펙(`SRC-MS-PE-FORMAT`) 기준.
- `.rdata`에 문자열 리터럴, C++ vtable, switch 점프 테이블, IAT가 배치되는 관행은 Visual C++ 컴파일러/링커의 일반적인 코드 생성 패턴으로, 다수의 공개 리버싱 레퍼런스 및 실제 MSVC 빌드 결과물 관찰을 통해 정리한 것이다(2026-09-08 확인).
