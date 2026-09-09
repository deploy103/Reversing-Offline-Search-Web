---
id: REV-0762
title: "컴파일러가 생성한 헬퍼 함수(__security_check_cookie 등) 걸러내기"
slug: "rev-0762-compiler-helper-functions-filtering"
category: "static-analysis"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [IDA, Ghidra]
keywords: ["__security_check_cookie", "_RTC_CheckStackVars", "__chkstk", "__memcpy_chk", "__stack_chk_fail", "FORTIFY_SOURCE", "컴파일러 삽입 헬퍼 함수"]
aliases: ["보안 쿠키 검사 함수 무시하기", "스택 체크 함수 걸러내기", "가드 함수 필터링"]
symptom_keywords: ["모든 함수 끝에 이상한 함수 호출이 반복됨", "__security_check_cookie가 뭔지 모름", "__memcpy_chk 때문에 함수 이름이 낯섦", "함수마다 똑같은 체크 코드가 끼어있음"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`__security_check_cookie`, `_RTC_CheckStackVars`, `__chkstk`, `__memcpy_chk`, `__stack_chk_fail` 같은 함수들은 문제 출제자가 작성한 코드가 아니라 컴파일러 보안/안전 옵션(`/GS`, `/RTC1`, `-fstack-protector`, `_FORTIFY_SOURCE`)이 **거의 모든 함수 안에 자동으로 끼워 넣는 가드(guard) 호출**이므로, 이름 패턴과 "인자가 문제 도메인과 무관하다"는 특징만 알아두면 함수 하나하나를 열어보지 않고도 빠르게 통과시킬 수 있다.

## 언제 검색해야 하나
- REV-0167(Compiler Generated Code와 실제 문제 로직 구분)에서 진입점~`main` 사이의 부트스트랩 체인은 걸렀는데, `main` *안*의 여러 함수 곳곳에서도 똑같은 패턴의 낯선 호출이 반복해서 보일 때
- 함수 에필로그 직전에 `mov ecx, [rbp+var_8]` 후 알 수 없는 함수를 호출하는 코드가 서로 다른 함수 수십 개에서 토씨 하나 안 틀리고 똑같이 나올 때
- `memcpy`/`sprintf`가 아니라 `__memcpy_chk`/`__sprintf_chk`처럼 뒤에 `_chk`가 붙은 이름이 보여서 원래 함수와 다른 것인지 헷갈릴 때
- 스택 크기가 큰 함수 초입에 `__chkstk`/`__chkstk_ms` 호출이 있어서 이게 취약점 관련 코드인지 헷갈릴 때

## 핵심 개념

### REV-0167과의 차이 — "체인"이 아니라 "산발적으로 흩뿌려진 호출"
REV-0167은 `entry`/`_start`부터 `main`까지 이어지는 **부트스트랩 호출 체인**을 다룬다. 이 문서는 그와 별개로, `main` 진입 이후 사용자 로직이 담긴 함수들 **내부 곳곳에** 컴파일러가 개별적으로 삽입하는 짧은 가드 호출을 다룬다. 즉 REV-0167이 "입구에서 한 번 거르는 필터"라면, 이 문서는 "모든 함수 내부에 반복적으로 나타나는 잡음을 거르는 필터"다.

### MSVC 계열 헬퍼 함수
| 이름 | 삽입 조건 | 역할 |
|---|---|---|
| `__security_check_cookie` | `/GS`(기본 활성화) | 함수 에필로그 직전, 스택 카나리 값이 프롤로그에서 심은 값과 같은지 검사. 다르면 `__fastfail`로 즉시 종료 |
| `__security_init_cookie` | `/GS` | 프로그램 시작 시 카나리 시드 값을 한 번 초기화(REV-0167의 부트스트랩 체인에 위치) |
| `_RTC_CheckStackVars` / `_RTC_CheckStackVars2` | `/RTC1`(디버그 빌드) | 지역 변수 앞뒤에 심어둔 패턴이 변조됐는지 검사(버퍼 오버런 조기 탐지용, 디버그 전용이라 릴리스 빌드엔 없음) |
| `__report_rangecheckfailure` | `/RTC1` | 위 검사 실패 시 호출되는 종료 루틴 |
| `__chkstk` / `__chkstk_ms` | 스택 프레임이 한 페이지(4KB)보다 클 때 자동 삽입 | 스택을 한 번에 크게 확장하기 전에 가드 페이지를 순차적으로 터치해 스택 오버플로우로 인한 크래시를 예방 |
| `_alloca_probe` | `alloca()`/가변 크기 지역 배열 사용 시 | 위와 유사하게 스택 확장 전 안전 검사 |
| `__GSHandlerCheck` / `__CxxFrameHandler3`/`4` | C++ 예외 처리, `/GS` | SEH/C++ 예외 처리 프레임 검증(REV-0446과도 연관) |

### GCC/Clang(glibc) 계열 헬퍼 함수
| 이름 | 삽입 조건 | 역할 |
|---|---|---|
| `__stack_chk_fail` | `-fstack-protector`(대부분 배포판 기본 활성화) | 스택 카나리(`__stack_chk_guard`)가 변조됐을 때 호출되어 프로그램을 즉시 종료(REV-0442, REV-0676과 연관) |
| `__memcpy_chk` / `__memset_chk` / `__sprintf_chk` / `__strcpy_chk` | `_FORTIFY_SOURCE` 매크로(Ubuntu/Debian 기본 활성화) | 원래 함수에 "버퍼 크기" 인자를 하나 추가해 컴파일 타임에 알 수 있는 크기 범위를 넘으면 즉시 중단시키는 안전 래퍼. **동작은 원본 함수와 완전히 동일**하므로 `memcpy`로 그대로 치환해서 읽어도 무방하다 |
| `__assert_fail` | `assert()` 매크로 | 디버그 빌드에서 조건이 거짓일 때 메시지를 출력하고 종료 |
| `__cxa_throw` / `__cxa_begin_catch` / `__cxa_end_catch` | C++ 예외(`throw`/`catch`) | 예외 처리 런타임 지원 함수 |

### 공통 식별 특징
이 함수들은 (1) 인자가 문제 도메인의 값(사용자 입력, 플래그 후보 문자열 등)과 무관하게 컴파일러가 자동으로 계산한 값(카나리 값, 버퍼 크기 상수, 프레임 크기)이고, (2) 서로 다른 함수 수십 개에서 완전히 동일한 바이트 패턴으로 반복되며, (3) 함수 자체의 내부 로직이 항상 똑같다(버전 하나로 고정). 이 세 가지 중 두 가지 이상이 겹치면 "가드 함수"로 잠정 분류하고 넘어가도 된다.

## 화면/코드에서 보이는 징후
- 함수 에필로그 근처에서 `mov rcx, [rbp+var_8]` → `call __security_check_cookie` 패턴이 함수마다 반복
- 디스어셈블리에 `_chk` 접미사가 붙은 함수 이름이 보이는데, 원래 알던 CRT 함수(`memcpy`, `sprintf`)와 인자 개수가 하나 더 많음
- 함수 진입 직후, 지역 변수를 채우기도 전에 `call __chkstk`가 먼저 나옴(큰 지역 배열을 선언한 함수에서 흔함)
- IDA Functions window에서 이런 함수들이 FLIRT 인식으로 회색/라이브러리 함수 색상으로 표시되거나, Ghidra에서 Function ID로 실제 이름이 그대로 붙어 있음(REV-0157)

## 가장 먼저 할 것
분석 중인 함수의 에필로그 직전 호출이 위 표의 이름과 일치하는지부터 확인한다. 일치하면 그 호출 자체는 검증 로직과 무관하다고 확정하고, 그 호출의 인자(카나리 변수)가 아니라 그 앞뒤에 있는 실제 조건 분기·반복문에 집중한다.

## 단계별 절차
1. 함수를 열어 에필로그(`leave`/`ret` 또는 `mov rsp, rbp` 계열) 직전 호출을 확인한다.
2. 호출 대상 이름이 위 두 표(MSVC/GCC)에 있으면 가드 함수로 분류하고 그 줄은 건너뛴다.
3. 이름이 FLIRT/Function ID로 인식되지 않아 `sub_`/`FUN_`로 남아 있다면, 인자가 스택 지역 변수 하나뿐이고 반환값을 아무 데도 안 쓰거나 단순 비교 후 종료 계열 API(`__fastfail`, `abort`, `exit`)만 호출하는지 확인해 패턴으로 추정한다.
4. `_chk` 접미사 함수는 원래 함수 이름(`memcpy`, `sprintf` 등)으로 마음속에서 치환해서 읽고, 추가된 크기 인자는 무시해도 로직 이해에는 지장이 없다.
5. `__chkstk`/`_alloca_probe`가 보이면 "이 함수가 큰 지역 버퍼를 쓴다"는 정보로만 활용하고 넘어간다(버퍼 크기를 스택 프레임 배치 추정에 참고할 수는 있다).
6. 이 필터를 통과한 뒤 남은 코드—조건 분기, 반복문, 사용자 정의 함수 호출—만 REV-0163~0166 방식으로 분석을 이어간다.

## 명령어/단축키
- IDA: Functions window에서 이름 필터에 `chk`, `security`, `RTC` 입력해 일괄 확인, FLIRT 재적용은 `File → Load file → FLIRT signature file`
- Ghidra: Symbol Tree 필터에 동일 키워드 입력, Function ID는 `Analysis → One Shot → Function ID`
- 공통: 가드 함수로 확정한 주소는 REV-0147/0161 방식으로 색상 태그나 주석(`// guard, skip`)을 남겨 다음에 다시 볼 때 바로 알아보게 한다.

## 출력 해석
- `__security_check_cookie(v)`에서 `v`가 지역 변수라면 그 값은 프롤로그에서 전역 `__security_cookie`와 XOR된 형태로 저장된 카나리이며, 사용자 입력과는 무관하다.
- `__memcpy_chk(dst, src, len, dstlen)`에서 마지막 인자 `dstlen`이 컴파일 타임 상수라면 컴파일러가 `dst` 버퍼의 실제 크기를 알고 있었다는 뜻이므로, 오히려 그 버퍼의 진짜 크기를 역으로 알아내는 데 활용할 수 있다(디컴파일러가 지역 배열 크기를 잘못 추정했을 때 교차검증용으로 유용).
- 가드 함수 호출 실패 시 도달하는 코드(`__fastfail`, `__stack_chk_fail` 이후)는 일반적인 실행 경로에서는 도달하지 않으므로, 이 경로를 검증 로직의 일부로 착각하지 않아야 한다.

## 흔한 실수
- `__security_check_cookie`나 `__stack_chk_fail` 호출을 보고 "이 문제는 스택 카나리 우회가 핵심이다"라고 성급히 결론짓는 것 — pwnable이 아닌 일반 crackme/reversing 문제라면 이 코드는 거의 항상 무관한 잡음이다.
- `_chk` 접미사가 붙은 함수를 완전히 다른 함수로 착각하는 것 — `__strcpy_chk`는 `strcpy`와 동작이 사실상 같고 인자만 하나 늘어난 것이다.
- FORTIFY 관련 함수가 안 보인다고 "이 바이너리는 이런 보호가 없다"고 단정하는 것 — 컴파일 옵션에 따라 아예 없을 수도 있으므로 없다고 문제가 되는 것은 아니다.
- 이런 가드 함수들을 걸러내다가 실제로 가드 함수 근처에 숨겨둔 사용자 코드(가드 호출 바로 앞에 추가된 검증 조건 등)까지 통째로 건너뛰는 것 — 걸러야 할 것은 가드 함수 "호출 그 자체"이지 그 주변 코드 전체가 아니다.

## 막혔을 때 다음 체크
- 진입점부터 `main`까지의 부트스트랩 체인 자체가 헷갈린다면 → REV-0167(Compiler Generated Code와 실제 문제 로직 구분)
- 스택 카나리의 정확한 체크 시퀀스가 궁금하다면 → REV-0442(스택 카나리 체크 시퀀스 분석), REV-0676(AT_RANDOM과 스택 카나리 초기화 관계)
- 가드 함수를 걸러낸 뒤 남은 로직에서 검증 함수를 계속 좁혀가고 싶다면 → REV-0164(Imports에서 검증 함수 후보 좁히기), REV-0166(함수 Call Graph로 핵심 로직 좁히기)
- FLIRT/Function ID로 인식이 안 되는 정적 바이너리라면 → ../linux-elf/rev-0646-statically-linked-elf-analysis.md

## 미니 예제
Ghidra 디컴파일 결과가 다음과 같다고 하자.

```c
undefined8 check_password(char *param_1) {
  long in_FS_OFFSET;
  int local_2c;
  long local_28;

  local_28 = *(long *)(in_FS_OFFSET + 0x28);
  local_2c = strcmp(param_1, "s3cr3t_flag");
  if (*(long *)(in_FS_OFFSET + 0x28) != local_28) {
    __stack_chk_fail();
  }
  return CONCAT44(0, local_2c == 0);
}
```

`in_FS_OFFSET + 0x28`을 읽고 마지막에 비교하는 부분, 그리고 `__stack_chk_fail()` 호출은 전형적인 GCC 스택 카나리 패턴(REV-0442)이다. 이 부분을 무시하고 나면 실제 로직은 단 한 줄, `strcmp(param_1, "s3cr3t_flag")`뿐이라는 것이 바로 드러난다. 가드 코드를 걸러내지 않았다면 이 짧은 함수도 훨씬 복잡해 보였을 것이다.

## 관련 글
- REV-0167 — Compiler Generated Code와 실제 문제 로직 구분
- REV-0442 — 스택 카나리(Stack Canary) 체크 시퀀스 분석
- REV-0676 — AT_RANDOM과 스택 카나리 초기화 관계
- REV-0157 — Ghidra Auto Analysis 옵션
- REV-0761 — Import된 CRT 함수 이름으로 원본 로직 추정하기
- REV-0767 — 정적분석만으로 Flag 검증 로직을 완전히 복원하는 절차

## 출처/검증
- MSVC `/GS`, `/RTC1`, `__security_check_cookie`, `_RTC_CheckStackVars`, `__chkstk` 동작은 Microsoft Learn의 Buffer Security Check(`/GS`) 및 Run-Time Error Checks(`/RTC`) 공식 문서 기준으로 정리했다.
- GCC `-fstack-protector`와 `__stack_chk_fail`, glibc `_FORTIFY_SOURCE`(`__memcpy_chk` 등 `*_chk` 계열)는 GCC 공식 문서 및 glibc 공식 매뉴얼(Fortification) 기준이다.
- IDA FLIRT/Ghidra Function ID를 통한 라이브러리 함수 자동 인식은 각 도구의 공식 Help 문서 기준.
