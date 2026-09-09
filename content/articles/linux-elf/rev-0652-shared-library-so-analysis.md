---
id: REV-0652
title: "공유 라이브러리(.so) 자체를 분석 대상으로 다루기"
slug: "rev-0652-shared-library-so-analysis"
category: "linux-elf"
difficulty: "intermediate"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, Ghidra, GDB, Pwndbg, readelf, objdump]
keywords: [".so 분석", "공유 라이브러리 리버싱", "DT_SONAME", "dlopen dlsym", "라이브러리 단독 분석"]
aliases: ["so 파일 분석하는 법", "라이브러리만 주는 CTF 문제", "so 파일을 어떻게 실행하나", "shared object 리버싱"]
symptom_keywords: ["so 파일만 주고 실행파일이 없음", "so를 IDA로 열었는데 entry point가 이상함", "so 파일을 어떻게 실행시켜서 디버깅하나", "라이브러리 함수에 브레이크포인트가 안 걸림"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-08"
---

## 한 줄 요약
CTF나 실무에서 `.so` 파일 자체(또는 이를 로드하는 얇은 하니스 실행 파일과 함께)가 분석 대상으로 주어지는 경우가 있는데, `.so`는 그 자체로 독립 실행되지 않는 `ET_DYN` 오브젝트이므로 export된 함수 목록으로 진입점을 찾고, `dlopen`/`ctypes` 같은 방법으로 직접 로드해 실행하거나 GDB의 지연 브레이크포인트로 접근해야 한다.

## 언제 검색해야 하나
- CTF 문제 배포 파일이 `libchall.so`처럼 라이브러리 하나와 `chall`(하니스) 실행 파일 하나로 구성되어 있을 때
- `.so` 파일을 IDA/Ghidra로 열었는데 `main`이나 익숙한 진입점이 안 보여서 어디부터 봐야 할지 모를 때
- 문제에서 준 `.so`를 직접 실행하고 싶은데 `./libchall.so`가 그냥 실행이 안 될 때
- GDB에서 아직 로드되지 않은 라이브러리 안의 함수에 미리 브레이크포인트를 걸고 싶을 때

## 핵심 개념

### .so는 ET_DYN이다
공유 라이브러리는 ELF 헤더의 `e_type`이 `ET_DYN`(Shared object file)이다. 이는 사실 PIE 실행 파일(REV-0103)과 같은 타입이며, ELF 구조만으로는 "이게 실행용인지 라이브러리용인지" 완전히 구분되지 않는다. `readelf -h libchall.so`로 `Type: DYN (Shared object file)`을 확인할 수 있고, `readelf -d libchall.so`에서 `DT_SONAME` 태그(예: `Library soname: [libchall.so.1]`)가 있으면 이 파일이 다른 프로그램에 로드되도록 의도된 라이브러리라는 강한 신호다.

### 진입점이 있어도 의미가 다르다
`.so`도 `e_entry` 필드에 값이 있을 수 있지만, 이는 프로그램의 `main`처럼 "실행 시작점"이 아니라 라이브러리가 로드될 때 실행되는 초기화 루틴(`.init`/`.init_array`, 생성자 함수)을 가리키는 경우가 많다. 실질적인 분석 대상은 `main`이 아니라 **export된 함수들**이다.

### export 함수 목록 뽑기
동적 심볼 테이블에서 "정의됨(undefined 아님)" 심볼만 골라내면 이 라이브러리가 외부에 제공하는 함수 목록이 나온다.

```bash
readelf --dyn-syms libchall.so | grep -v UND
nm -D --defined-only libchall.so
objdump -T libchall.so | grep -v UND
```

CTF에서는 대개 하니스 프로그램(`chall`)이 `dlopen("./libchall.so", ...)` 후 `dlsym`으로 특정 함수를 찾아 호출하는 구조이거나, 컴파일 시점에 `-lchall`로 링크되어 있는 구조다. 후자라면 하니스의 Import 목록(REV-0101)에 `libchall.so`가 제공하는 함수 이름이 그대로 나타나므로, 하니스 쪽 분석이 오히려 더 쉬운 출발점이 될 수 있다.

### .so를 직접 실행/로드하는 법
라이브러리 자체는 셸에서 `./libchall.so`로 바로 실행되지 않는다(실행 권한이 있어도 대개 즉시 종료되거나 에러). 함수 하나를 호출해보고 싶다면 작은 "드라이버"를 직접 만드는 것이 가장 빠르다.

**Python ctypes 방식** (컴파일 없이 즉석 테스트):
```python
import ctypes
lib = ctypes.CDLL("./libchall.so")
lib.check.restype = ctypes.c_int
lib.check.argtypes = [ctypes.c_char_p]
print(lib.check(b"test_input"))
```

**C 드라이버 방식** (더 정교한 제어가 필요할 때):
```c
#include <dlfcn.h>
#include <stdio.h>
int main() {
    void *h = dlopen("./libchall.so", RTLD_NOW);
    int (*check)(const char *) = dlsym(h, "check");
    printf("%d\n", check("test_input"));
}
```
컴파일: `gcc driver.c -ldl -o driver`

### GDB에서 아직 로드 안 된 함수에 브레이크포인트 걸기
`.so`가 실행 중간에 `dlopen`으로 로드되는 구조라면, 프로세스 시작 시점에는 그 함수의 주소를 알 수 없다. GDB는 이런 상황을 위한 지연 브레이크포인트(pending breakpoint)를 지원한다.

```gdb
set breakpoint pending on
break libchall.so:check
run
```
또는 심볼 이름만으로 `break check`를 걸어도, GDB가 "이 심볼을 아직 못 찾았는데 나중에 로드되면 걸까요?"라고 물으면 `y`로 답하면 된다. 라이브러리가 실제로 매핑되는 순간(공유 라이브러리 이벤트)에 GDB가 자동으로 브레이크포인트를 활성화한다. `set stop-on-solib-events 1`을 켜두면 새 라이브러리가 로드될 때마다 실행이 멈춰서 `info sharedlibrary`로 로드 상태를 확인할 수도 있다.

### pwntools로 다루기
pwntools의 `ELF()` 클래스는 `.so`도 실행 파일과 동일하게 열어 심볼/함수 주소를 조회할 수 있다. `process()`로 하니스를 띄운 뒤 `proc.libs()`를 호출하면 실행 중 실제 로드된 각 라이브러리의 베이스 주소를 딕셔너리로 얻을 수 있어, ASLR이 켜진 상태에서도 `라이브러리_베이스 + 함수의_파일오프셋`으로 런타임 주소를 계산할 수 있다.

## 화면/코드에서 보이는 징후
- `file libchall.so` → `ELF 64-bit LSB shared object, x86-64, ...`
- `readelf -h libchall.so` → `Type: DYN (Shared object file)`
- `readelf -d libchall.so`에 `SONAME` 태그 존재
- 하니스 실행 파일(`chall`)의 strings에 `dlopen`, `dlsym` 문자열이나 `libchall.so`라는 파일명 문자열이 보임
- IDA로 `.so`를 열면 Functions 창에 `main`은 없고 `check`, `verify` 등 도메인 특화 이름이 export로 보임

## 가장 먼저 할 것
`file`과 `readelf -h`로 `.so`임을 확인한 뒤, `readelf --dyn-syms libchall.so | grep -v UND`로 export 함수 목록부터 확보한다. 하니스 실행 파일이 함께 있다면 하니스의 Import 목록과 대조해서 실제로 호출되는 함수가 무엇인지 좁힌다.

## 단계별 절차
1. `file libchall.so`, `readelf -h libchall.so`로 타입 확인
2. `readelf --dyn-syms libchall.so | grep -v UND`로 export 함수 목록 확보
3. 하니스가 있다면 `strings chall | grep -E 'dlopen|libchall'`, `readelf --dyn-syms chall`로 연결 방식(정적 링크 vs `dlopen`) 파악
4. IDA/Ghidra로 `.so`를 열어 export 함수부터 분석 시작(진입점이 아니라 함수 목록이 출발점)
5. 함수를 직접 호출해서 입출력을 관찰하고 싶다면 Python `ctypes` 드라이버로 빠르게 테스트
6. 실제 실행 컨텍스트(하니스 안)에서 관찰해야 한다면 GDB `set breakpoint pending on` + `break 라이브러리이름:함수이름`으로 지연 브레이크포인트 설정
7. ASLR 환경에서 주소 계산이 필요하면 pwntools `process().libs()`로 런타임 베이스 확보

## 명령어/단축키
```bash
file libchall.so
readelf -h libchall.so
readelf -d libchall.so | grep SONAME
readelf --dyn-syms libchall.so | grep -v UND
nm -D --defined-only libchall.so
```
GDB: `set breakpoint pending on`, `break libchall.so:check`, `set stop-on-solib-events 1`, `info sharedlibrary`

## 출력 해석
- `readelf --dyn-syms`에서 `UND`가 아닌 줄(섹션 인덱스가 숫자로 채워진 줄)이 이 라이브러리가 실제로 정의(export)한 함수다. `UND`인 줄은 반대로 이 라이브러리가 외부(libc 등)에서 가져다 쓰는 함수다.
- `DT_SONAME`이 파일명과 다르면(예: 파일은 `libchall.so`인데 SONAME은 `libchall.so.1`), 실제 로딩 시 이 SONAME으로 심볼릭 링크나 캐시 등록이 되어 있어야 한다는 뜻이니 배포 스크립트를 확인한다.
- GDB `info sharedlibrary` 출력에서 `Syms Read` 열이 `Yes`로 바뀌는 시점이 실제로 그 라이브러리의 디버그 심볼을 GDB가 다 읽어들인 시점이다.

## 흔한 실수
- `.so` 파일에서 `main` 함수를 찾으려고 헤매는 것 — 라이브러리에는 보통 `main`이 없다.
- `.so`를 `./libchall.so`로 그냥 실행해보고 "실행이 안 되네, 분석 불가"라고 결론짓는 것 — 드라이버(ctypes/dlopen)로 직접 함수를 호출해야 한다.
- `dlopen`으로 늦게 로드되는 라이브러리 함수에 프로세스 시작 직후 `break 함수이름`을 걸었다가 "심볼을 찾을 수 없다"는 에러를 보고 포기하는 것 — pending breakpoint 옵션을 켜야 한다.
- 하니스와 라이브러리 중 하나만 분석하고 나머지를 무시하는 것 — 인자 검증/흐름 제어는 하니스에, 핵심 로직은 라이브러리에 나뉘어 있는 경우가 많아 둘 다 봐야 한다.

## 막혔을 때 다음 체크
- import/export 심볼 테이블의 기본 개념이 헷갈리면 → REV-0101 Dynamic Linking과 Import 함수 추적
- 라이브러리가 정확히 어디서 로드되는지 탐색 경로가 궁금하면 → REV-0651 LD_LIBRARY_PATH와 라이브러리 탐색 순서
- 라이브러리 함수 호출을 가로채서 관찰하고 싶다면 → REV-0650 LD_PRELOAD로 함수 후킹해서 관찰하기
- 이 라이브러리가 심볼 버전을 어떻게 export하는지 궁금하면 → REV-0653 ELF Symbol Versioning(GLIBC_2.x) 이해하기
- PIE와 ET_DYN 타입의 관계가 헷갈리면 → REV-0103 PIE와 주소 계산

## 미니 예제
```bash
$ readelf -h libchall.so | grep Type
  Type:                              DYN (Shared object file)

$ readelf -d libchall.so | grep SONAME
 0x000000000000000e (SONAME)            Library soname: [libchall.so]

$ readelf --dyn-syms libchall.so | grep -v UND | grep FUNC
    45: 0000000000001189    98 FUNC    GLOBAL DEFAULT   13 check
    52: 0000000000001210    45 FUNC    GLOBAL DEFAULT   13 init_state
```
`check`와 `init_state`가 export된 함수이므로, 이 라이브러리를 분석할 때는 이 두 함수부터 시��하는 것이 올바른 진입점이다.

## 관련 글
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0651 — LD_LIBRARY_PATH와 라이브러리 탐색 순서
- REV-0650 — LD_PRELOAD로 함수 후킹해서 관찰하기
- REV-0653 — ELF Symbol Versioning(GLIBC_2.x) 이해하기
- REV-0103 — PIE와 주소 계산

## 출처/검증
- `ET_DYN` 타입과 `DT_SONAME` 구조: ELF Specification 및 System V ABI 기준.
- `dlopen`/`dlsym` API: `man 3 dlopen`, `man 3 dlsym` 공식 매뉴얼 기준.
- GDB pending breakpoint(`set breakpoint pending on`) 및 `set stop-on-solib-events`: GDB 공식 매뉴얼(Shared Libraries, Set Breaks 챕터) 기준 (2026-09-08 검증).
