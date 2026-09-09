---
id: REV-1092
title: "Go 바이너리 디컴파일 시 흔한 어려움과 대응(IDA/Ghidra)"
slug: "rev-1092-go-decompile-ida-ghidra-difficulties"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA, GDB]
keywords: ["Go 디컴파일", "pclntab", "gopclntab", "Go 인터페이스 호출 분석"]
aliases: ["Go 바이너리 Ghidra 함수 인식 안됨", "Go 바이너리 IDA 인터페이스 호출"]
symptom_keywords: ["gopclntab 섹션이 안 보임", "Ghidra가 Go 함수 경계를 못 잡음", "Go 인터페이스 메서드 호출이 뭘 부르는지 안 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Go 바이너리는 자체 메타데이터 테이블(pclntab)에 함수 이름/라인 정보를 담고 있어 원래는 strip 후에도 복구 가능하지만, 이 테이블의 형식이 Go 버전마다 계속 바뀌고 Windows PE에서는 전용 섹션조차 없어서 IDA/Ghidra의 기본 분석 기능만으로는 함수 경계와 인터페이스 호출을 제대로 복원하지 못하는 경우가 많다.

## 언제 검색해야 하나
- Ghidra/IDA로 Go 바이너리를 열었는데 함수가 몇 개 안 잡히거나 이름이 전부 `sub_`/`FUN_`로 나올 때
- ELF인데 `.gopclntab` 섹션이 있는 걸 확인했는데도 도구가 자동으로 함수 이름을 못 붙일 때
- PE(Windows용 Go 바이너리)인데 pclntab 관련 섹션 이름 자체가 안 보여서 당황할 때
- 인터페이스 값에 대한 메서드 호출(`v.Method()`)이 의사코드에서 함수 포인터를 통한 간접 호출로만 보이고 실제로 어떤 함수가 불리는지 안 보일 때

## 핵심 개념

### pclntab이 무엇이고 왜 중요한가
pclntab(program counter line table)은 Go 1.2부터 존재하는 Go 고유의 메타데이터 구조로, 원래 목적은 패닉 발생 시 스택 트레이스에 소스 파일/줄 번호를 출력하기 위함이다. 여기에 모든 함수의 시작 주소와 함수 이름 문자열에 대한 정보가 함께 들어 있어서, 심볼 테이블이 strip된 바이너리라도 pclntab만 온전하면 함수 이름과 경계를 재구성할 수 있다.

### 플랫폼별 위치 문제
Linux/macOS ELF/Mach-O 바이너리에서는 각각 `.gopclntab`, `__gopclntab`라는 전용 섹션 이름으로 pclntab을 바로 찾을 수 있다. 반면 Windows PE로 빌드된 Go 바이너리는 pclntab을 담는 전용 섹션이 없어서, 분석 도구가 Go 버전별로 달라지는 매직 값(magic number) 패턴을 데이터 섹션 전체에서 직접 스캔해 위치를 찾아야 한다. 이 차이 때문에 같은 스크립트/플러그인이라도 ELF에서는 잘 되던 것이 PE에서는 실패하는 경우가 흔하다.

### 버전마다 계속 바뀌는 구조
pclntab 헤더 포맷은 1.2 도입 이후 1.16, 1.18에서 구조가 바뀌었고, 이를 가리키는 상위 구조체인 `moduledata` 역시 1.5 도입 이후 1.7, 1.8, 1.10, 1.16에서 필드가 달라졌다. 즉 "Go 버전이 다르면 파서도 다시 맞춰야 한다"는 것이 Go 리버싱 도구 유지보수의 근본적인 어려움이며, 특정 버전에 맞춰 만들어진 IDA/Ghidra 스크립트가 다른 버전 바이너리에서는 그대로 안 먹히는 이유이기도 하다.

### strip돼도 함수 이름 자체는 남을 수 있다
심볼 테이블이 제거되어도, pclntab 내부의 `Func` 구조체들은 함수 이름 문자열에 대한 오프셋을 여전히 갖고 있는 경우가 많다. 즉 "strip = 이름 완전 소실"이 C/C++만큼 절대적이지 않다. `go_func.py`(Ghidra), `recreate_pclntab`/함수 자동 인식 스크립트(IDA), 그리고 독립 도구인 `GoReSym`, `redress` 등이 이 pclntab을 직접 파싱해 이름과 경계를 다시 붙여준다.

### 인터페이스 메서드 호출이 어려운 이유
Go의 인터페이스 값은 내부적으로 `itab`(interface table, 구체 타입과 인터페이스가 요구하는 메서드들의 함수 포인터 배열을 담음)과 실제 데이터 포인터의 쌍으로 표현된다. 인터페이스를 통한 메서드 호출은 이 `itab` 안의 함수 포인터를 읽어 간접 호출(`CALL [reg + offset]` 형태)하는 방식으로 컴파일되는데, 이는 C++ 가상 함수 호출이 vtable을 통해 간접 호출되는 것과 본질적으로 같은 문제를 일으킨다. IDA/Ghidra 모두 이런 함수 포인터 테이블을 통한 간접 호출에서 대상 함수와 인자를 정확히 추론하지 못하는 경우가 실제로 보고되어 있다(Ghidra 이슈 트래커에도 vtable 스타일 간접 호출에서 인자가 하나 누락되는 버그가 존재). Go 인터페이스 호출도 이와 같은 부류의 약점이며, `moduledata`의 `typelinks` 필드(타입 정보 목록)를 별도로 파싱해야 어떤 구체 타입의 어떤 메서드가 불리는지 재구성할 수 있다.

## 화면/코드에서 보이는 징후
- Ghidra Functions 목록에 이름이 거의 없고 `FUN_00401234`류만 잔뜩 있는데, `strings`로는 원래 함수 이름으로 보이는 문자열이 데이터 섹션에서 발견됨
- 의사코드에서 `(*(code **)(itab + offset))(data)` 같은 간접 호출 형태로만 보이고 실제 함수명이 안 붙음
- 같은 스크립트를 다른 CTF 문제(다른 Go 버전으로 컴파일된 바이너리)에 썼는데 이번엔 파싱 에러가 나거나 아무것도 안 나옴
- PE 바이너리인데 섹션 목록에 `.gopclntab` 같은 이름이 아예 없음

## 가장 먼저 할 것
`file ./chall`이나 문자열로 Go 버전 배너(`go1.XX`)부터 확인한 뒤, ELF라면 `readelf -S`로 `.gopclntab` 섹션 존재를 확인하고, PE라면 애초에 전용 섹션이 없다는 점을 인지한 상태에서 GoReSym 같은 독립 파서 도구를 먼저 시도한다. 도구가 해당 Go 버전을 지원하는지부터 확인하는 것이 시간 낭비를 줄인다.

## 단계별 절차
1. `strings ./chall | grep "^go1\."`로 정확한 Go 컴파일러 버전 확인
2. ELF면 `readelf -S ./chall | grep gopclntab`로 섹션 존재 확인, PE면 이 단계를 생략하고 다음으로
3. GoReSym(`GoReSym.exe`/`GoReSym`)을 바이너리에 실행해 함수 목록, 소스 파일명, 타입 정보를 JSON으로 추출 시도
4. GoReSym이 해당 버전을 지원하지 않으면 `redress` 또는 Ghidra용 `go_func.py` 스크립트로 재시도
5. 추출된 함수 이름/주소 목록을 Ghidra/IDA에 스크립트로 일괄 반영(Rename Function, Create Function)
6. 인터페이스 간접 호출부는 `moduledata`의 `typelinks`를 참고해 가능한 구체 타입 후보를 좁히고, 실행 중 GDB로 `itab` 포인터가 가리키는 실제 주소를 런타임에 찍어 검증한다

## 명령어/단축키
```bash
strings ./chall | grep -E "^go1\.[0-9]+"
readelf -S ./chall | grep -i gopclntab
GoReSym -p ./chall > chall_symbols.json
```
Ghidra: Script Manager에서 커뮤니티 제공 `go_func.py` 실행. IDA: Go 함수 자동 인식/`recreate_pclntab` 스크립트를 File → Script file로 실행(IDA 버전 호환성 사전 확인 필요).

## 출력 해석
- GoReSym JSON 출력에 함수 이름과 소스 파일 경로가 채워져 있다면, 그만큼 컴파일 당시의 원본 패키지 구조를 그대로 알 수 있다는 뜻이다.
- `.gopclntab`은 있는데 파싱이 실패한다면 십중팔구 도구가 지원하는 버전 범위(1.16 이전/이후, 1.18 이후 등)와 실제 바이너리 버전이 어긋난 경우다.
- 인터페이스 간접 호출부에서 후보 구체 타입이 여러 개로 좁혀졌다면, 실제로는 그 인터페이스 변수에 대입되는 값이 프로그램 흐름상 하나뿐인 경우가 많으므로 대입 지점을 역추적하면 확정할 수 있다.

## 흔한 실수
- 특정 CTF 문제에서 잘 통했던 스크립트/시그니처를 다른 Go 버전 바이너리에도 그대로 적용하고 안 된다고 포기하는 것 — 버전 차이가 원인일 가능성부터 확인해야 한다.
- PE 바이너리에서 `.gopclntab` 섹션 이름을 찾다가 없다고 "이건 Go가 아니다"라고 오판하는 것 — Windows Go 바이너리는 원래 전용 섹션이 없다.
- 인터페이스 간접 호출을 일반 함수 포인터 콜백과 똑같이 취급해서, `itab`이라는 별도의 메서드 테이블 개념을 놓치는 것.
- Ghidra/IDA의 기본 자동 분석 결과(함수 개수, 경계)를 그대로 신뢰하고 pclntab 기반 재구성을 시도조차 안 해보는 것.

## 막혔을 때 다음 체크
- 함수 이름은 복구했는데 런타임 함수가 너무 많아 헷갈리면 → REV-1091 Go 바이너리에서 goroutine/런타임 함수 걸러내기
- 문자열 인자를 못 찾겠으면 → REV-1090 Go 바이너리의 문자열 구조(길이+포인터) 읽는 법
- 애초에 Go 바이너리인지 확신이 안 서면 → REV-1088 Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)
- FLIRT/Function ID 같은 일반 시그니처 매칭 개념부터 다시 보고 싶으면 → REV-0729 FLIRT 시그니처 개념과 사용 빠른 참조

## 미니 예제
```
$ strings ./chall.exe | grep -E "^go1\.[0-9]+"
go1.21.3
$ GoReSym -p ./chall.exe > out.json
$ python3 -c "import json,sys; d=json.load(open('out.json')); print(len(d['Functions']))"
2103
```
Windows PE 바이너리라 섹션 이름으로는 pclntab을 못 찾았지만, GoReSym이 매직 값을 직접 스캔해 2,103개 함수의 이름/주소를 복구했다. 이 결과를 Ghidra 스크립트로 일괄 적용하면 `FUN_` 이름 대신 원래 패키지 경로가 붙은 이름으로 함수 목록이 채워진다.

## 관련 글
- REV-1090 — Go 바이너리의 문자열 구조(길이+포인터) 읽는 법
- REV-1091 — Go 바이너리에서 goroutine/런타임 함수 걸러내기
- REV-0729 — FLIRT 시그니처 개념과 사용 빠른 참조
- REV-1088 — Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)
- REV-1089 — Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함) (예정)

## 출처/검증
- pclntab의 목적, 플랫폼별 섹션 이름 차이(Linux `.gopclntab`, macOS `__gopclntab`, Windows는 매직 값 스캔 필요), 버전별 구조 변화(1.2/1.16/1.18, moduledata 1.5/1.7/1.8/1.10/1.16): CUJO AI "Reverse Engineering Go Binaries with Ghidra" 및 후속 파트 2 블로그 기준.
- strip 후에도 `Func` 구조체를 통한 함수명 복구 가능성과 `GoReSym`/`redress`/`go_func.py` 도구: 동일 CUJO 자료 및 GoReSym 공식 저장소 기준.
- 인터페이스/`itab` 기반 간접 호출이 디컴파일러에서 인자 누락 등으로 잘못 표시되는 문제(vtable류 간접 호출의 일반적 약점 포함): Ghidra 공식 이슈 트래커(NationalSecurityAgency/ghidra) 기준 (2026-09-10 검증).
