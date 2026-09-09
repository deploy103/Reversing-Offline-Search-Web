---
id: REV-1088
title: "Go 바이너리 식별하는 법(특징적인 심볼/문자열)"
slug: "rev-1088-go-binary-identification"
category: "other-targets"
difficulty: "basic"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA, strings, "go tool"]
keywords: ["Go 바이너리 식별", "gopclntab", "go build id", "runtime. 함수", "go1.XX 버전 문자열"]
aliases: ["Go 실행파일 확인법", "이 바이너리가 Go로 만들어졌는지 확인", "gopclntab이 뭔지"]
symptom_keywords: ["파일 크기가 유난히 크고 함수가 이상하게 많음", "runtime.morestack 같은 심볼이 잔뜩 보임", "IDA로 열었더니 함수가 수만 개 나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
파일 크기가 몇 MB 이상으로 크고, `strings` 결과에 `Go build ID:`나 `go1.XX`(버전) 문자열이 보이거나, IDA/Ghidra의 함수 목록에 `runtime.`으로 시작하는 이름이 수백~수천 개 나온다면 Go로 컴파일된 바이너리이며, 이 경우 정적 링킹된 런타임 전체가 들어있다는 전제로 분석 전략을 세워야 한다.

## 언제 검색해야 하나
- ELF/PE 파일 하나가 유독 크고(보통 1MB를 훌쩍 넘음), import는 몇 개 안 되는데 함수 개수는 수천 개로 나올 때
- `strings`에서 `runtime.`, `.gopclntab`, `go1.`로 시작하는 낯선 이름이 반복적으로 보일 때
- IDA/Ghidra Functions 창에 `main_main`, `runtime.main`, `runtime morestack noctxt` 같은 언더스코어/공백 섞인 이름이 보일 때(Go 심볼의 `.`을 디스어셈블러가 그대로 못 쓰는 문자로 치환해서 나타나는 경우가 있다)

## 핵심 개념

### Go 바이너리가 큰 이유 — 정적 링킹이 기본값
Go 컴파일러(`go build`)는 기본적으로 Go 런타임(가비지 컬렉터, 고루틴 스케줄러 등)과 표준 라이브러리를 실행파일 안에 정적으로 전부 포함시킨다. 그래서 "Hello World" 수준의 프로그램도 수 MB 크기가 되는 경우가 흔하다. 이는 REV-0646에서 다룬 정적 링킹된 C/C++ ELF와 비슷한 맥락이지만, Go는 아예 언어 차원에서 기본 동작이 정적 링킹이라는 점이 다르다.

### pclntab(gopclntab) — Go 런타임이 반드시 필요로 하는 테이블
Go 컴파일러/링커는 모든 함수의 주소를 소스 파일명·줄 번호·함수 이름에 매핑하는 **pclntab**(PC Line Table, ELF에서는 보통 `.gopclntab` 섹션에 위치)이라는 자체 데이터 구조를 바이너리에 넣는다. 이 테이블은 디버깅 편의용이 아니라 **Go 런타임 자체가 스택 트레이스 생성, `panic`/`recover`, 프로파일링을 위해 실행 중에 참조하는 필수 데이터**다. 그래서 `strip`으로 일반 심볼 테이블을 지워도 pclntab은 프로그램이 정상 동작하려면 남아있어야 하며, 바로 이 성질 때문에 strip된 Go 바이너리에서도 함수 이름 복구가 가능해진다(REV-1089에서 자세히 다룬다). pclntab은 Go 버전마다 헤더 포맷(매직 넘버)이 달라졌는데, Go 1.2·1.16·1.18·1.20 시점에 각각 헤더 구조가 바뀐 것으로 확인된다.

### 식별에 쓸 수 있는 구체적 문자열/심볼
- **`Go build ID:`**: Go 툴체인이 빌드 재현성/캐싱을 위해 심어두는 빌드 ID 문자열로, `strings` 결과에서 바로 확인 가능한 대표적 식별자다.
- **`go1.XX` 형태의 버전 문자열**: 바이너리 안에 컴파일에 사용된 Go 런타임 버전이 `go1.21.5`처럼 문자열로 남아 있으며, `go version <바이너리>` 명령으로 이를 직접 파싱해서 보여준다(`debug/buildinfo` 패키지가 이 기능을 제공).
- **`runtime.` 접두사 함수들**: strip되지 않았거나 pclntab에서 복구된 함수 목록에 `runtime.main`, `runtime.morestack`, `runtime.gopanic`, `runtime.newobject` 같은 이름이 대량으로 나타난다. 사용자가 작성한 코드는 보통 `main.함수이름`, 임포트한 패키지 코드는 `패키지경로.함수이름` 형태로 나온다.
- **섹션 이름**: ELF라면 `.gopclntab`, `.gosymtab`(구버전), `.go.buildinfo`(빌드 정보 블롭이 저장되는 위치) 같은 Go 전용 섹션 이름이 그대로 보인다.

## 화면/코드에서 보이는 징후
- `file ./chall` 결과가 일반 ELF/PE인데 크기가 수 MB 이상.
- `strings ./chall | grep "Go build ID"` 나 `strings ./chall | grep -E "go1\.[0-9]+"`에서 결과가 나온다.
- `readelf -S ./chall`(ELF) 목록에 `.gopclntab`, `.go.buildinfo`가 보인다.
- IDA/Ghidra Functions 창을 정렬해보면 `runtime.` 접두사가 붙은 이름이 압도적으로 많다.

## 가장 먼저 할 것
`strings ./chall | grep -E "Go build ID|go1\.[0-9]"`부터 실행한다. 하나라도 걸리면 Go 바이너리로 확정하고, 만약 Go 툴체인이 로컬에 있다면 `go version ./chall`로 정확한 버전까지 바로 뽑아낸다.

## 단계별 절차
1. `file ./chall`로 크기와 포맷(PE/ELF)을 확인한다.
2. `strings ./chall | grep -i "go build id"`와 `strings ./chall | grep -E "go1\.[0-9]+"`로 Go 특유의 문자열을 찾는다.
3. (Go 툴체인이 설치되어 있다면) `go version ./chall`로 정확한 컴파일 버전을 확인한다.
4. ELF라면 `readelf -S ./chall | grep -i go`로 `.gopclntab`/`.go.buildinfo` 섹션 존재를 확인한다.
5. IDA/Ghidra로 열어 Functions 창을 이름순 정렬해 `runtime.` 접두사 함수가 대량으로 있는지 확인한다.
6. strip 여부(`file` 출력의 `not stripped`/`stripped`)를 확인하고, strip됐다면 REV-1089로 넘어가 pclntab 기반 함수명 복구를 시도한다.

## 명령어/단축키
```bash
file ./chall
strings ./chall | grep -i "go build id"
strings ./chall | grep -E "go1\.[0-9]+"
go version ./chall          # Go 툴체인이 설치되어 있을 때
readelf -S ./chall | grep -i go
nm ./chall | grep '^.* T runtime\.' | head
```

## 출력 해석
- `Go build ID: "abcdef0123..."`가 나오면 Go로 빌드됐다는 것이 사실상 확정이다.
- `go version` 명령이 `chall: go1.21.5`처럼 출력하면 정확한 컴파일러/런타임 버전을 바로 알 수 있고, 이는 이후 pclntab 파싱 도구(REV-1089)가 어떤 버전 포맷(Go 1.2/1.16/1.18/1.20 계열)을 써야 하는지 정하는 데 중요한 단서가 된다.
- `runtime.`으로 시작하는 함수가 대부분이고 `main.`으로 시작하는 함수가 상대적으로 적게 섞여 있다면, `main.`으로 시작하는 쪽이 이 프로그램 고유의 로직이므로 분석 우선순위를 여기에 둔다(REV-1091류의 "런타임 함수 걸러내기" 전략과 연결된다).

## 흔한 실수
- 함수 개수가 수천 개라고 "이 바이너리는 분석이 불가능하다"고 지레 포기하는 것 — 대부분은 `runtime.` 계열 라이브러리 코드이고, 실제로 봐야 할 `main.` 코드는 그 일부에 불과하다.
- Go 바이너리를 일반 C/C++ 정적 바이너리(REV-0646)와 똑같은 방식(FLIRT/Function ID 시그니처)으로만 접근하려는 것 — Go는 심볼 네이밍 규칙과 pclntab이라는 별도 메커니즘이 있어 이를 활용하는 것이 훨씬 효율적이다.
- strip된 Go 바이너리를 보고 "심볼이 다 지워졌으니 함수 이름 복구가 불가능하다"고 오해하는 것 — pclntab은 런타임 동작에 필요해서 strip 후에도 대부분 남아있다.

## 막혔을 때 다음 체크
- strip된 상태에서 함수 이름을 실제로 복구하는 절차가 필요하면 → REV-1089 Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함)
- 정적 링킹된 C/C++ ELF와의 차이가 헷갈리면 → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법
- strip 여부 자체를 판단하는 기본기가 필요하면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 미니 예제
```text
$ file chall
chall: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, Go BuildID=..., not stripped

$ strings chall | grep -i "go build id"
Go build ID: "3q6R7f1c2H8s9k_abcdEFghijK/xyz..."

$ strings chall | grep -E "go1\.[0-9]+"
go1.21.5

$ readelf -S chall | grep -i go
  [26] .gopclntab        PROGBITS
  [27] .go.buildinfo     PROGBITS
```
이 네 가지 신호(빌드 ID, 버전 문자열, `.gopclntab`/`.go.buildinfo` 섹션)만 확인해도 Go 바이너리라는 것과 정확한 컴파일 버전(1.21.5)까지 5분 안에 알아낼 수 있다.

## 관련 글
- REV-1089 — Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함)
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이

## 출처/검증
- pclntab(`.gopclntab`)의 목적(PC-라인 매핑), Go 런타임이 스택 트레이스/패닉/프로파일링을 위해 이를 실행 중 필요로 한다는 점, 헤더 매직 넘버가 Go 1.2/1.16/1.18/1.20 시점에 바뀌었다는 점, strip 후에도 pclntab이 남아 함수명 복구에 쓰인다는 메커니즘: Go 공식 저장소 `src/debug/gosym/pclntab.go` 소스 주석 기준 (2026-09-10 WebFetch로 원문 확인).
- `debug/buildinfo` 패키지와 `go version <바이너리>` 명령이 바이너리에 내장된 Go 버전/모듈 정보를 읽어 보여준다는 점: Go 공식 패키지 문서 `pkg.go.dev/debug/buildinfo` 기준 (2026-09-10 WebFetch 검증). 다만 이 정보가 저장되는 정확한 섹션명(`.go.buildinfo`)과 내부 매직 바이트 시퀀스는 해당 공식 문서 페이지 자체에는 명시되어 있지 않아, 이 글에서는 일반적으로 알려진 섹션명을 참고 수준으로 제시했다는 점을 밝혀둔다. 정확한 바이트 레벨 포맷이 필요하면 `debug/buildinfo` 패키지의 실제 소스(`src/debug/buildinfo/buildinfo.go`)를 직접 확인할 것.
- `Go build ID:` 문자열, `runtime.` 접두사 심볼 네이밍 관례는 Go 툴체인 및 런타임의 잘 알려진 특징이다.
