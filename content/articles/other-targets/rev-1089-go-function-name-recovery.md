---
id: REV-1089
title: "Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함)"
slug: "rev-1089-go-function-name-recovery"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA, "go tool"]
keywords: ["gopclntab 함수명 복구", "strip된 Go 바이너리", "go tool nm", "Ghidra Go 분석", "IDA golang loader"]
aliases: ["Go strip 바이너리 분석", "Go 함수 이름 다시 찾기", "gopclntab 파싱"]
symptom_keywords: ["Go 바이너리인데 strip돼서 함수 이름이 다 sub_로 나옴", "Ghidra에서 Go 함수명이 이상하게 붙음", "go tool nm이 뭔지 모름"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Go 바이너리는 `strip`으로 일반 심볼 테이블을 지워도 런타임이 스택 트레이스·패닉 처리를 위해 반드시 필요로 하는 **pclntab(`.gopclntab`)** 테이블이 대부분 그대로 남기 때문에, 이 테이블을 파싱할 수 있는 도구(최신 Ghidra의 Go 분석 기능, `go tool nm`, 전용 스크립트)만 있으면 strip된 상태에서도 함수 이름을 상당 부분 복구할 수 있다.

## 언제 검색해야 하나
- REV-1088로 Go 바이너리임을 확인했는데 `file` 결과가 `stripped`로 나와서 IDA/Ghidra Functions 창에 `sub_401234` 같은 이름만 잔뜩 보일 때
- Go 바이너리인데 심볼이 하나도 없어서 "이건 분석 불가능한가?"라는 생각이 들 때
- Ghidra/IDA에서 함수 경계 자체가 이상하게 잡혀서(Go는 자체 호출 규약과 스택 관리 방식을 쓰기 때문에 x86/x64 표준 프롤로그 패턴과 다르게 보임) 분석이 막힐 때

## 핵심 개념

### pclntab이 살아남는 이유
REV-1088에서 다뤘듯 pclntab은 디버그 편의용 부가 정보가 아니라, Go 런타임이 실행 중에 **직접 참조하는 필수 데이터 구조**다. 함수 하나가 패닉을 일으켰을 때 콜스택을 출력하거나(`goroutine 1 [running]: main.checkFlag(...)` 같은 표준 Go 패닉 메시지), `runtime.Caller`로 현재 실행 위치의 파일/줄 번호를 얻거나, 프로파일러가 CPU 프로파일을 만들 때 모두 이 테이블을 사용한다. 이런 기능이 정상 동작해야 하므로 링커는 일반 심볼 테이블(`.symtab`)이 strip으로 제거되더라도 pclntab만은 남겨두는 경우가 대부분이다.

### pclntab 내부 구조 개요
pclntab은 크게 다음 요소로 구성된다(Go 공식 `debug/gosym` 패키지 소스 기준).
- **헤더**: 4바이트 매직 넘버(Go 1.2/1.16/1.18/1.20 시점마다 값이 다름, 두 방향 엔디안으로 읽어 매칭되는 쪽으로 포맷을 확정) + 예약된 2바이트 0 + PC 단위(quantum, 보통 1) + 포인터 크기(4 또는 8) 바이트.
- **함수 이름 테이블(`funcnametab`)**: 각 함수 이름이 널 종료 문자열로 저장된 영역.
- **함수 테이블(`functab`)**: 각 함수의 시작 주소(PC)와 함수별 메타데이터(`_func` 레코드)로의 오프셋을 정렬된 순서로 나열 — 주소만 알면 이진 탐색으로 어느 함수에 속하는지 바로 찾을 수 있다.
- **함수별 메타데이터(`_func`)**: 이름 오프셋(`nameOff`), PC-라인/PC-파일 매핑 서브테이블, (신버전은) 컴파일 유닛 오프셋 등을 담아 특정 PC에 대응하는 함수 이름/파일/줄 번호까지 재구성 가능하게 한다.

즉 이 테이블 하나만 제대로 파싱하면, DWARF 디버그 정보나 일반 심볼 테이블 없이도 **모든 함수의 주소, 이름, 소속 파일, 줄 번호**까지 통째로 복원할 수 있다.

### 실전 도구들
- **`go tool nm <바이너리>`**: Go 툴체인에 내장된 명령으로, pclntab을 파싱해 함수 이름과 주소를 nm과 유사한 형식으로 나열해준다. strip된 바이너리에도 동작하는 경우가 많다(단, 일반 `nm`이 아니라 반드시 `go tool nm`이어야 한다).
- **Ghidra**: 최신 버전은 Go 바이너리를 열었을 때 pclntab을 자동 인식해서 함수 이름을 복구해주는 전용 분석기를 내장하고 있다(버전에 따라 지원 수준이 다르므로, 오래된 Ghidra라면 별도 스크립트/플러그인이 필요할 수 있다).
- **IDA**: 커뮤니티에서 만든 Go 전용 로더/스크립트(예: golang_loader_assist류)가 pclntab을 읽어 IDA의 함수 이름을 자동으로 붙여주는 방식으로 동작해왔다. IDA 자체 버전과 스크립트 호환성을 확인해야 한다.
- **`redress`**: Go 바이너리 전용 분석 도구로 pclntab을 파싱해 함수 목록, 버전 정보 등을 추출해주는 커맨드라인 도구로 잘 알려져 있다.

## 화면/코드에서 보이는 징후
- `file ./chall` 결과에 `stripped`가 포함되어 있는데도 프로그램 실행 중 패닉이 나면 `main.함수이름` 형태의 콜스택이 여전히 출력된다 — 이는 pclntab이 살아있다는 직접적 증거다.
- IDA/Ghidra 초기 로딩 시 함수 이름이 전부 `sub_`/`FUN_` 접두사인데, `.gopclntab` 섹션 자체는 여전히 존재한다(`readelf -S`로 확인 가능).
- `go tool nm ./chall`을 돌렸을 때 `T main.checkFlag`처럼 정상적인 이름이 주소와 함께 출력된다.

## 가장 먼저 할 것
Go 툴체인이 로컬에 설치되어 있다면 가장 빠른 확인 방법은 `go tool nm ./chall | grep main\\.`이다. 이 한 줄만으로 strip 여부와 무관하게 사용자 정의 함수(`main.` 접두사) 목록을 바로 뽑을 수 있다.

## 단계별 절차
1. `go tool nm ./chall`을 실행해 pclntab 기반 함수 목록이 나오는지 확인한다.
2. 결과가 나오면 `grep '^.\{1,\} T main\.'`처럼 `main.` 접두사 함수만 걸러 사용자 코드 목록을 얻는다.
3. Go 툴체인이 없거나 IDA/Ghidra 안에서 바로 이름을 붙이고 싶다면, 사용 중인 Ghidra 버전이 Go 바이너리 자동 분석을 지원하는지 확인하고 Auto Analysis를 그대로 돌려본다.
4. IDA를 쓴다면 pclntab을 파싱해 이름을 붙여주는 커뮤니티 스크립트/로더의 최신 버전을 구해 실행한다.
5. 이름이 복구된 함수 중 `runtime.`/`vendor.`/서드파티 패키지 경로 접두사가 붙은 것은 라이브러리 코드이므로 건너뛰고, `main.`으로 시작하는 함수부터 분석을 시작한다(REV-1091 방향과 연결).
6. 자동 도구가 전혀 없는 최악의 경우, `readelf -x .gopclntab ./chall`로 raw 데이터를 덤프해 위 "pclntab 내부 구조"에서 설명한 헤더(매직 넘버로 버전 판단)부터 직접 파싱하는 것도 이론적으로 가능하다 — 다만 상당한 리버싱 난이도가 있으므로 최후의 수단이다.

## 명령어/단축키
```bash
go tool nm ./chall | head
go tool nm ./chall | grep ' T main\.'
readelf -S ./chall | grep gopclntab
readelf -x .gopclntab ./chall | head
```

## 출력 해석
- `go tool nm` 출력에서 왼쪽은 주소, 가운데 문자(`T`, `t` 등)는 심볼 종류(전역/지역 텍스트 심볼), 오른쪽이 `패키지경로.함수이름`이다.
- `main.` 접두사가 붙은 항목이 이 프로그램의 핵심 로직이고, `runtime.`/`fmt.`/`net/http.` 같은 접두사는 표준 라이브러리 또는 런타임 코드이므로 우선순위가 낮다.
- Ghidra가 Go 바이너리를 자동 인식하면 Symbol Tree에 `main_checkFlag`처럼 `.`이 `_`로 치환된 형태로 이름이 붙는 경우가 많다(디스어셈블러가 심볼 이름에 `.`을 직접 허용하지 않는 경우가 있어서다).

## 흔한 실수
- strip됐다는 이유만으로 Go 바이너리 분석을 포기하는 것 — pclntab이 살아있는 한 함수 이름 복구는 충분히 가능하다.
- `go tool nm`이 아니라 일반 `nm`만 써보고 "심볼이 없다"고 결론짓는 것 — 일반 `nm`은 `.symtab`만 보므로 strip된 바이너리에서는 실패하지만, `go tool nm`은 pclntab을 직접 파싱하므로 결과가 다를 수 있다.
- 복구된 함수 이름 중 `runtime.`/서드파티 패키지 코드까지 전부 하나하나 분석하려다 실제 문제 로직(`main.` 함수)에 도달하기 전에 시간을 다 쓰는 것.
- 오래된 Ghidra/IDA 버전을 쓰면서 최신 Go 바이너리(pclntab 헤더가 Go 1.18/1.20 시점 포맷으로 바뀐 버전)에 구버전 파서를 그대로 적용해 파싱이 깨지는 것 — 사용 중인 도구/스크립트가 대상 Go 버전(REV-1088에서 확인한 `go1.XX`)의 pclntab 포맷을 지원하는지 확인해야 한다.

## 막혔을 때 다음 체크
- 애초에 Go 바이너리인지부터 확인이 안 됐다면 → REV-1088 Go 바이너리 식별하는 법(특징적인 심볼/문자열)
- 복구된 함수 중 어디까지가 런타임 코드이고 어디부터가 실제 로직인지 구분하는 전략이 필요하면 → REV-1091 Go 바이너리에서 goroutine/런타임 함수 걸러내기 (예정)
- strip 자체의 개념과 일반 ELF에서의 영향이 헷갈리면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이
- 정적 링킹된 C/C++ 바이너리와의 접근법 차이를 비교하고 싶다면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```text
$ file chall
chall: ELF 64-bit LSB executable, x86-64, ... statically linked, stripped

$ go tool nm chall | grep ' T main\.'
0000000000481a40 T main.checkFlag
0000000000481c10 T main.main
0000000000481f30 T main.xorDecrypt
```
`file` 결과가 `stripped`라고 나와도 `go tool nm`은 `main.checkFlag`, `main.main`, `main.xorDecrypt` 같은 이름을 그대로 복구해낸다. 이후 IDA/Ghidra에서 해당 주소(`0x481a40` 등)에 직접 이름을 붙이거나, Ghidra의 Go 자동 분석 기능을 사용해 같은 결과를 자동으로 얻을 수 있다.

## 관련 글
- REV-1088 — Go 바이너리 식별하는 법(특징적인 심볼/문자열)
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 출처/검증
- pclntab이 strip 이후에도 남는 이유(런타임의 스택 트레이스/패닉/프로파일링 의존성), pclntab의 내부 구성(`funcnametab`, `functab`, `_func` 메타데이터, PC-라인/PC-파일 매핑), 헤더 매직 넘버가 Go 1.2/1.16/1.18/1.20 시점에 바뀐다는 점: Go 공식 저장소 `src/debug/gosym/pclntab.go` 소스 주석 기준 (2026-09-10 WebFetch로 원문 확인).
- `go tool nm`이 pclntab을 이용해 strip된 바이너리에서도 함수 심볼을 나열할 수 있다는 점, Ghidra/IDA의 Go 바이너리 지원(자동 분석기/커뮤니티 로더)이 존재한다는 점은 Go 리버싱 관련 공개 자료에서 널리 알려진 사실이나, 이번 세션에서 Ghidra/IDA 공식 문서로 개별 버전별 지원 범위를 재확인하지는 못했다. 실제 사용 전 해당 도구의 현재 버전이 대상 Go 버전을 지원하는지 별도 확인을 권장한다.
