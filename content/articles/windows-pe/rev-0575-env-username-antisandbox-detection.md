---
id: REV-0575
title: "환경변수/사용자명으로 분석 환경을 탐지하는 기법"
slug: "rev-0575-env-username-antisandbox-detection"
category: "windows-pe"
difficulty: "intermediate"
platform: [windows]
architecture: [x86, x64]
format: [PE]
tools: [IDA, x64dbg]
keywords: ["GetUserNameA", "GetComputerNameA", "GetEnvironmentVariable", "sandbox artifact", "샌드박스 아티팩트", "사용자명 탐지", "컴퓨터명 탐지"]
aliases: ["사용자명 안티샌드박스", "환경변수 안티샌드박스", "GetUserName 안티디버깅", "분석 환경 탐지"]
symptom_keywords: ["GetUserName을 호출한 뒤 특정 문자열과 비교한다", "computername이 sandbox인지 비교한다", "특정 사용자명이면 종료한다", "환경변수 개수를 센다"]
source_ids: ["SRC-MS-PE-FORMAT", "SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
많은 악성코드 분석 샌드박스와 자동화 도구가 특정한 기본값(사용자명 `sandbox`, `malware`, `virus`, 컴퓨터명 `DESKTOP-XXXXXXX`가 아닌 짧은 임의 문자열, 특정 환경변수 조합 등)을 그대로 쓰는 경향이 있기 때문에, 악성코드가 `GetUserName`, `GetComputerName`, `GetEnvironmentVariable` 등으로 이런 값을 읽어 알려진 분석 환경 패턴과 비교한 뒤, 일치하면 자기 자신이 관찰당하고 있다고 판단해 조용히 종료하거나 정상적인 동작만 흉내 내는 회피 기법이 흔하며, 이는 하이퍼바이저나 레지스트리 아티팩트를 뒤지는 것보다 훨씬 가볍고 흔적도 적어 자주 쓰인다.

## 언제 검색해야 하나
- 디스어셈블리에서 `GetUserNameA`/`GetUserNameW` 호출 직후, 리턴된 문자열을 특정 값들과 반복적으로 비교(`strcmp`류 호출이나 인라인 바이트 비교)하는 코드를 봤을 때
- `GetComputerNameA`/`GetComputerNameW`나 `GetEnvironmentVariableA`(`"NUMBER_OF_PROCESSORS"`, `"PROCESSOR_IDENTIFIER"` 등) 호출 뒤 조건 분기가 이어질 때
- CTF 문제나 악성코드 샘플이 특정 VM/샌드박스 환경에서는 실행이 안 되고 실사용자 환경에서만 정상 동작한다는 이야기를 들었을 때
- "sandbox evasion via environment artifacts"라는 표현을 리포트에서 보고 원리가 궁금할 때

## 핵심 개념
자동화 분석 시스템은 대량의 샘플을 반복 처리해야 하므로, 가상 머신 이미지를 매번 새로 손으로 세팅하지 않고 표준화된(그리고 종종 기본값을 그대로 둔) 환경을 재사용한다. 이 표준화 자체가 역설적으로 훌륭한 탐지 지표가 된다. 악성코드가 흔히 확인하는 항목들은 다음과 같다.

- **사용자명(`GetUserNameA`/`GetUserNameW`)**: 자동화 샌드박스가 기본 계정 이름을 `admin`, `user`, `sandbox`, `malware`, `test`, `virus`, `sample` 등으로 설정해두는 경우가 많다. 실제 사람이 쓰는 PC에서는 이런 이름을 잘 쓰지 않는다는 통계적 특징을 이용한다.
- **컴퓨터명(`GetComputerNameA`/`GetComputerNameW`)**: `SANDBOX`, `TEST-PC`, `VIRUS`, 또는 짧고 규칙적인 이름(예: 특정 샌드박스 벤더의 기본 호스트명 패턴)을 특정 목록과 비교.
- **환경변수(`GetEnvironmentVariableA`/`GetEnvironmentVariableW`)**: `NUMBER_OF_PROCESSORS`(가상 머신은 CPU 코어 수가 1~2개로 적게 할당된 경우가 많음), `PROCESSOR_IDENTIFIER`(가상화 환경 특유의 CPU 문자열), 또는 `USERDOMAIN`, `COMPUTERNAME` 등 다른 환경변수와 결합해서 확인.
- **최근 실행 파일/문서 개수, 바탕화면 아이콘 개수**: 직접적인 API는 아니지만 `SHGetFolderPath`로 최근 문서 폴더나 바탕화면을 열어 파일 개수를 세는 방식도 있다 — 샌드박스는 "갓 생성된" 깨끗한 환경이라 파일이 거의 없는 경우가 많기 때문이다.
- **화면 해상도(`GetSystemMetrics`)**: 가상 머신은 기본 해상도(800x600 등 낮은 해상도)를 쓰는 경우가 있어 이를 비교하기도 한다.

이런 체크들은 개별로는 정확도가 낮지만(실사용자도 `sandbox`라는 이름을 쓸 수 있고, 반대로 잘 꾸며진 샌드박스는 그럴듯한 사용자명을 쓸 수도 있음), 여러 항목을 조합해 점수를 매기는 방식(예: 5개 중 3개 이상 의심스러우면 종료)으로 정확도를 높이는 경우가 많다. 또한 이 기법들은 VM 레지스트리 키나 드라이버 파일을 뒤지는 것(REV-0576 가상머신 아티팩트 탐지 참고)보다 훨씬 API 호출이 단순하고 은밀해서, 다른 무거운 안티VM 기법과 함께 1차 필터로 자주 쓰인다.

## 화면/코드에서 보이는 징후
- `call GetUserNameA` 직후 리턴된 버퍼를 `lstrcmpiA`/`strcmp`류 함수로 `"sandbox"`, `"malware"`, `"virus"`, `"admin"` 등의 문자열과 반복 비교
- `call GetComputerNameA` 직후 유사한 반복 문자열 비교 패턴
- `call GetEnvironmentVariableA`의 첫 번째 인자로 `"NUMBER_OF_PROCESSORS"` 문자열이 전달되고, 리턴값을 `1`이나 `2`와 비교하는 코드
- 여러 개의 독립적인 체크 결과를 정수 변수에 누적(`add`)한 뒤, 마지막에 합계를 임계값과 비교하는 "점수 합산형" 구조

## 가장 먼저 할 것
1. `GetUserNameA/W`, `GetComputerNameA/W`, `GetEnvironmentVariableA/W`의 xref를 모두 확인해, 어떤 값과 비교되는지 각각 나열한다.
2. 비교 대상 문자열 목록을 모아두면, 그 자체가 이 샘플이 어떤 샌드박스/분석 환경을 특별히 겨냥해 회피하려 하는지 알려주는 단서가 된다.

## 단계별 절차
**1) 비교 문자열 목록 확보**
- IDA 문자열 뷰(`Shift+F12`)에서 `sandbox`, `virus`, `malware`, `test`, `sample`, `admin` 등 의심되는 리터럴을 검색하고, 각각이 어느 함수에서 어떤 API 결과와 비교되는지 xref로 역추적한다.
- 문자열이 암호화되어 있다면 REV-0128의 문자열 복호화 흔적 찾기 방법을 적용한다.

**2) 점수 합산 구조 파악**
- 여러 체크가 독립 함수로 나뉘어 있고 각각이 불리언(0/1) 또는 점수를 리턴하는 구조라면, 이 값들이 최종적으로 어디서 합산되고 어떤 임계값과 비교되는지 찾는다. 이 최종 비교 지점을 패치하는 것이 개별 체크를 하나씩 우회하는 것보다 훨씬 효율적이다.

**3) 동적 분석으로 실제 값 확인**
- x64dbg로 `GetUserNameA` 호출 직후 멈춰서, 실제 분석용 VM의 사용자명이 무엇으로 설정되어 있는지 확인한다. 만약 실제로 `sandbox`, `test` 같은 이름을 쓰고 있다면 이 자체가 탐지 트리거가 될 수 있으므로, 분석 환경의 사용자명/컴퓨터명을 미리 평범한 이름(예: `John`, `DESKTOP-A1B2C3`처럼 실제 Windows가 자동 생성하는 형식)으로 바꿔두는 것이 좋은 사전 대비다.

**4) 코드 패치로 우회**
- 최종 판정 분기(`cmp score, threshold` 뒤의 조건 점프)를 찾아, 항상 "정상 환경"으로 판정되도록 조건 분기를 반전시키거나 무조건 통과하도록 `nop` 처리한다.
- 개별 API 호출의 리턴값 자체를 바꾸는 방법(예: `GetUserNameA`가 항상 `"John"`을 리턴하도록 후킹)도 가능하지만, 체크 지점이 여러 곳에 흩어져 있으면 최종 판정 분기 하나만 패치하는 것이 더 효율적이다.

## 명령어/단축키
- IDA: `Shift+F12`(문자열 뷰), `X`(교차 참조), `Alt+T`(텍스트 검색)
- x64dbg: `F2`(브레이크포인트), 리턴 후 버퍼 `Follow in Dump`로 실제 문자열 확인, 조건 분기 `Assemble`로 패치
- 분석 환경 사전 준비: VM 설치 시 사용자명/컴퓨터명을 평범한 값으로 설정, 필요 시 `netsh`/`레지스트리 편집`으로 `NUMBER_OF_PROCESSORS` 등 환경 아티팩트를 현실적인 값(4코어 이상 등)으로 맞춰두는 것도 도움이 된다.

## 출력 해석
- 비교 문자열이 일치해 "샌드박스로 판단"되는 분기로 빠지면, 프로그램은 대개 정상적인(무해한) 동작만 하거나 즉시 종료해 진짜 페이로드를 노출하지 않는다.
- 반대로 이 체크들을 모두 통과(정상 환경으로 판정)한 뒤에야 진짜 악성 행위 API 호출들이 시작되는 경우가 많으므로, 이 판정 이후 코드가 실제 분석해야 할 핵심이다.

## 흔한 실수
- 문자열 비교 하나만 우회하고 다른 체크(환경변수, 컴퓨터명 등)를 놓쳐서 여전히 페이로드가 실행 안 되는 것을 "패치가 잘못됐다"고 오해하는 것 — 점수 합산형 구조에서는 모든 체크 지점을 다 찾아야 한다.
- 분석 VM의 사용자명을 기본값(`WDAGUtilityAccount`, `sandbox` 등)으로 그대로 두고 분석해서 이 기법에 매번 걸리는 것.
- `GetEnvironmentVariable`로 확인하는 값이 항상 악의적인 목적이라고 단정하는 것 — 정상 프로그램도 CPU 코어 수에 따라 스레드 풀 크기를 조정하는 등 합법적인 이유로 같은 API를 쓸 수 있으므로, 비교 대상 값과 분기 결과를 반드시 함께 봐야 한다.
- 문자열 비교가 대소문자를 구분하는지(`strcmp`) 안 하는지(`lstrcmpi`, `_stricmp`) 확인하지 않아 우회 조건을 잘못 판단하는 것.

## 막혔을 때 다음 체크
- 이 체크와 함께 레지스트리/파일 기반 VM 아티팩트도 확인한다면 → REV-0576(가상머신 아티팩트로 VM 탐지하는 기법)을 함께 본다.
- 실행 지연이나 뮤텍스 체크와 결합되어 있다면 → REV-0573(Sleep 남용), REV-0574(Mutex 이름 기반 판단)를 참고한다.
- 문자열이 암호화되어 안 보인다면 → REV-0128(Windows 문자열 ASCII와 UTF-16 찾기)을 확인한다.

## 미니 예제
```c
char username[256];
DWORD len = sizeof(username);
GetUserNameA(username, &len);

const char* suspicious[] = { "sandbox", "malware", "virus", "test", "sample" };
for (int i = 0; i < 5; i++) {
    if (_stricmp(username, suspicious[i]) == 0) {
        ExitProcess(0);  // 알려진 분석 환경 사용자명과 일치 → 조용히 종료
    }
}
// 여기부터 정상 페이로드 실행
```
이 코드는 현재 로그인한 사용자명을 읽어 알려진 분석 환경 이름 목록과 대소문자 구분 없이 비교한다. 하나라도 일치하면 즉시 종료해 페이로드 실행 자체를 막는다. 분석자는 `for` 루프 이후의 `ExitProcess(0)` 분기로 이어지는 조건 점프를 찾아 무조건 건너뛰게 패치하거나, 애초에 분석 VM의 사용자명을 `John`, `Alice` 같은 평범한 이름으로 설정해 이 체크 자체가 걸리지 않도록 사전에 대비할 수 있다.

## 관련 글
- REV-0576 — 가상머신 아티팩트(레지스트리/파일)로 VM 탐지하는 기법
- REV-0573 — Sleep 남용과 안티디버깅/안티샌드박스 기법
- REV-0574 — Mutex 이름으로 중복 실행 방지/샌드박스 회피 판단하기
- REV-0128 — Windows 문자열 ASCII와 UTF-16 찾기

## 출처/검증
- `GetUserNameA/W`, `GetComputerNameA/W`, `GetEnvironmentVariableA/W`, `GetSystemMetrics`의 시그니처는 Microsoft Learn Win32 API 공식 문서 기준이다.
- 사용자명/컴퓨터명/환경변수를 이용한 샌드박스 회피 패턴(알려진 분석 환경 기본값과 비교)은 다수의 공개 악성코드 분석 리포트와 보안 리서치 자료에서 공통적으로 다루는 표준적인 안티샌드박스 기법이다(2026-09-08 기준 서술).
- 구체적인 비교 대상 문자열(사용자명/컴퓨터명 목록)은 샘플과 시기에 따라 계속 바뀌므로, 실제 분석 시 발견한 값을 최신 위협 인텔리전스 자료와 대조해 확인할 것을 권장한다.
