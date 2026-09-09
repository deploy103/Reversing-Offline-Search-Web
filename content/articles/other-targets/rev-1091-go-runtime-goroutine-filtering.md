---
id: REV-1091
title: "Go 바이너리에서 goroutine/런타임 함수 걸러내기"
slug: "rev-1091-go-runtime-goroutine-filtering"
category: "other-targets"
difficulty: "intermediate"
platform: [windows, linux]
architecture: [x86, x64]
format: [PE, ELF]
tools: [Ghidra, IDA, GDB]
keywords: ["Go 런타임 함수", "runtime 접두사", "goroutine 리버싱", "Go 함수 필터링"]
aliases: ["Go 바이너리 함수가 너무 많음", "runtime.으로 시작하는 함수 무엇"]
symptom_keywords: ["Go 바이너리에 함수가 수천 개 나옴", "runtime.mallocgc가 계속 보임"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
Go 바이너리는 프로그램 하나를 컴파일해도 표준 라이브러리와 런타임(스케줄러, GC, 채널 등)이 통째로 정적 링크되어 함수가 수천 개로 불어나므로, `runtime.`, `sync.`, `internal/`, `type.`, `go.` 같은 접두사를 가진 이름을 먼저 걸러내는 것이 실제 사용자 로직을 빨리 찾는 핵심 전략이다.

## 언제 검색해야 하나
- IDA/Ghidra의 Functions 창을 열었더니 함수가 수천 개이고 대부분 낯선 접두사(`runtime.`, `sync.`, `internal/`)로 시작할 때
- `nm`이나 `go tool nm` 결과에 `runtime.mallocgc`, `runtime.newobject`, `runtime.convT64` 같은 이름이 반복적으로 나와 정작 `main.main`을 찾기 어려울 때
- 함수 진입부마다 스택 크기를 확인하는 것처럼 보이는 동일한 몇 줄짜리 프롤로그가 계속 반복돼서 헷갈릴 때
- goroutine을 만드는 `go func(){...}()` 코드가 실제로 어떻게 어셈블리에 나타나는지 궁금할 때

## 핵심 개념

### 왜 함수가 이렇게 많은가
Go는 기본적으로 정적 링킹을 하고, 프로그램이 아주 작아도 스케줄러, 가비지 컬렉터(GC), 채널, map/slice 런타임 지원 코드가 함께 바이너리에 포함된다. strip되지 않은 바이너리라면 이 모든 런타임 함수 이름이 `.gopclntab`(프로그램 카운터-라인 테이블) 덕분에 그대로 남아 있어서(Go 1.2부터 존재), 함수 개수만 봐서는 "이 프로그램이 복잡한 프로그램이다"라고 착각하기 쉽다. 실제 사용자 코드는 보통 `main.` 패키지 접두사를 가진 소수의 함수에 몰려 있다.

### 걸러낼 접두사 목록
Go 바이너리 지문(fingerprint) 추출 도구인 gimphash 프로젝트의 방법론에 따르면, 함수 식별/분석 시 다음 접두사를 가진 이름은 컴파일러가 자동 생성한 산출물이거나 런타임 내부 구현이므로 우선적으로 걸러낸다.

- `runtime.` — 스케줄러, GC, 채널, 스택 관리 등 Go 런타임 그 자체
- `type.` — 컴파일러가 자동 생성한 타입 메타데이터(`_type`, `itab` 등)
- `sync.`, `sync/atomic.` — 표준 동기화 프리미티브
- `internal/...` — Go 표준 라이브러리 내부 전용 패키지
- `vendor/...` — 서드파티 벤더링된 의존성(이 경우 `vendor/` 앞부분까지 통째로 무시하고 그 뒤의 실제 패키지 경로만 본다)
- `go.` (예: `go.itab.*`, `go.string.*`) — 컴파일러가 만든 보조 심볼

반대로 남겨야 할 것은 프로그램 자체의 모듈 경로(예: `main.`, 또는 `go.mod`에 정의된 모듈 이름으로 시작하는 패키지)이다. 이런 이름을 가진 함수만 추려도 분석 대상이 수천 개에서 수십 개 수준으로 확 줄어든다.

### goroutine 관련 코드를 알아보는 두 가지 단서
1. **스택 체크 프롤로그**: Go의 네이티브 함수는 거의 대부분 함수 시작 부분에 "현재 goroutine의 스택이 충분히 큰지" 확인하는 동일한 패턴의 코드(스택 포인터와 `g` 구조체의 `stackguard0`를 비교하는 형태)를 갖고 있다. 이 프롤로그는 스택이 부족하면 `runtime.morestack`을 호출해 더 큰 스택으로 복사한다. 이 패턴 자체는 사용자 함수든 런타임 함수든 거의 모든 Go 함수에 공통으로 붙으므로, "이 프롤로그가 있으니 Go 함수구나"를 확인하는 용도로 쓰고, 그 안쪽의 실제 로직에 집중해야 한다.
2. **goroutine 생성 호출**: 소스 코드의 `go func(...)`는 컴파일되면 `runtime.newproc` 호출로 바뀐다. `runtime.newproc`는 실행할 네이티브 함수의 주소, 인자 크기, 실제 인자들을 받아 새 goroutine을 스케줄러 큐에 등록한다. 디스어셈블리에서 `call runtime.newproc` 직전에 함수 포인터로 보이는 주소가 로드되는 패턴을 찾으면, 그 주소가 바로 별도 goroutine으로 실행되는 함수의 시작점이다 — 이는 C의 `pthread_create`가 스레드 함수 포인터를 인자로 받는 것과 개념적으로 비슷하다.

## 화면/코드에서 보이는 징후
- Functions 창을 이름순 정렬하면 `runtime.`으로 시작하는 항목이 압도적으로 많아 스크롤이 끝없이 이어짐
- 여러 함수의 첫 3~5개 명령어가 토씨 하나 안 틀리고 똑같이 반복됨(스택 체크 프롤로그)
- `call runtime.newproc` 호출 직전에 낯선 함수 주소가 인자로 로드되는 코드
- `main.main`, `main.init` 같은 이름이 함수 목록 어딘가에 반드시 존재(strip 안 됐다면)

## 가장 먼저 할 것
strip 여부와 상관없이 먼저 함수 이름 목록(또는 pclntab에서 복구한 이름 목록)을 텍스트로 뽑아, `runtime.`/`type.`/`sync.`/`internal/`/`vendor/`/`go.` 접두사를 가진 줄을 제외한 나머지만 남긴다. 이 남은 목록이 실제로 분석해야 할 사용자 코드다.

## 단계별 절차
1. strip 안 된 바이너리면 `go tool nm ./chall` 또는 `nm ./chall`로 전체 심볼 목록 추출
2. `grep -v -E '^(runtime\.|type\.|sync\.|internal/|vendor/|go\.)'` 로 런타임 계열 이름 제외
3. 남은 목록에서 자신의 모듈 경로(보통 `main.`으로 시작)로 시작하는 함수부터 우선 분석
4. `main.main`을 시작점으로 잡고, 거기서 호출되는 함수 중 위 필터에 걸리지 않는 것만 따라가며 콜그래프를 그린다
5. `go func(){...}()` 같은 동시성 로직을 찾을 때는 `call runtime.newproc` 호출부를 전부 xref로 모아서, 그 직전에 로드되는 함수 주소들을 목록화한다
6. 반복되는 스택 체크 프롤로그는 "Go 함수 표시"로만 인식하고 넘어가되, 그 이후 로직에서 실제 분기/연산부터 읽는다

## 명령어/단축키
```bash
go tool nm ./chall | grep -v -E ' T (runtime\.|type\.|sync\.|internal/|vendor/|go\.)'
nm ./chall | grep ' T main\.'
objdump -d ./chall | grep -B2 "call.*runtime.newproc"
```
IDA/Ghidra: Functions 창에서 이름으로 정렬 후 `runtime.` 항목을 한 번에 접거나(IDA는 필터 박스에 `!runtime.` 형태 정규식 검색 활용), Ghidra는 Symbol Tree에서 우클릭 필터로 특정 접두사를 숨긴다.

## 출력 해석
- `grep -v` 필터를 통과한 목록이 여전히 수백 개라면, 대부분 표준 라이브러리(`fmt.`, `strconv.`, `os.` 등)일 가능성이 높다 — 이들은 런타임은 아니지만 여전히 사용자가 작성하지 않은 코드이므로, 자신의 모듈 이름을 알고 있다면 그것으로 한 번 더 좁힐 수 있다.
- `runtime.newproc` 호출부가 하나도 없다면 그 바이너리는 goroutine을 전혀 쓰지 않는 단순한 순차 프로그램일 가능성이 크다.
- 스택 체크 프롤로그가 없는 함수가 있다면, 이는 컴파일러가 인라인했거나 nosplit으로 표시된 특수한 저수준 런타임 함수일 수 있다.

## 흔한 실수
- `runtime.mallocgc`, `runtime.convT64` 같은 런타임 헬퍼 호출을 사용자 로직의 일부로 착각해서 시간을 낭비하는 것 — 이들은 각각 힙 할당과 인터페이스 박싱(boxing)을 위한 공통 헬퍼일 뿐이다.
- goroutine 생성을 C의 `pthread_create` 프롤로그와 똑같이 생각해서 `runtime.newproc`의 인자 순서(함수 포인터, 인자 크기, 인자들)를 스레드 함수/인자 하나로 오해하는 것.
- 스택 체크 프롤로그를 매번 처음부터 끝까지 분석해서 시간을 소모하는 것 — 이 패턴은 거의 모든 Go 함수에 동일하게 붙으므로 한 번 익히면 그냥 건너뛰어도 된다.
- `vendor/` 접두사가 붙은 이름을 서드파티 코드로 인지하지 못하고 프로그램 고유 로직으로 오해하는 것.

## 막혔을 때 다음 체크
- 함수 이름 자체가 strip되어 안 보이면 → REV-1089 Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함) (예정)
- 걸러낸 뒤에도 남은 함수의 문자열 인자를 못 찾겠으면 → REV-1090 Go 바이너리의 문자열 구조(길이+포인터) 읽는 법
- Ghidra/IDA가 인터페이스 호출을 제대로 못 그려서 콜그래프 추적이 막히면 → REV-1092 Go 바이너리 디컴파일 시 흔한 어려움과 대응(IDA/Ghidra)
- 애초에 이게 Go 바이너리인지부터 확신이 안 서면 → REV-1088 Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)

## 미니 예제
```
$ go tool nm ./chall | grep ' T ' | wc -l
4821
$ go tool nm ./chall | grep ' T ' | grep -v -E ' T (runtime\.|type\.|sync\.|internal/|vendor/|go\.)' | grep '^.* T main\.'
  0000000000471200 T main.checkPassword
  00000000004712d0 T main.main
  0000000000471350 T main.xorDecrypt
```
필터 전에는 4,821개였던 함수 목록이 필터 후에는 사용자 패키지(`main.`) 함수 3개로 좁혀진다. 이제 이 3개 함수만 집중해서 읽으면 된다.

## 관련 글
- REV-1090 — Go 바이너리의 문자열 구조(길이+포인터) 읽는 법
- REV-1092 — Go 바이너리 디컴파일 시 흔한 어려움과 대응(IDA/Ghidra)
- REV-1088 — Go 바이너리 식별하는 법(특징적인 심볼/문자열) (예정)
- REV-1089 — Go 바이너리에서 함수 이름 복구하기(strip된 경우 포함) (예정)

## 출처/검증
- 함수 이름 접두사(`runtime.`, `type.`, `sync.`, `internal/`, `vendor/`, `go.`) 필터링 방법론: NextronSystems `gimphash` 프로젝트의 Go 바이너리 지문 추출 방법론 기준.
- `.gopclntab`을 통한 strip 후에도 남는 함수명 복구 가능성: OSIRIS Lab(NYU Tandon) "Reverse Engineering Go, Part I" 기준.
- 네이티브 함수 공통 스택 체크 프롤로그와 `runtime.newproc`을 통한 goroutine 생성 패턴: 동일 OSIRIS Lab 자료 기준 (2026-09-10 검증).
