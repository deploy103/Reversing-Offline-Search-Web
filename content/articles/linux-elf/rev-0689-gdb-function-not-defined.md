---
id: REV-0689
title: "GDB에서 breakpoint를 걸었는데 Function not defined라고 할 때"
slug: "rev-0689-gdb-function-not-defined"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [GDB, Pwndbg]
keywords: ["Function not defined gdb", "break main 안됨", "gdb pending breakpoint", "stripped 바이너리 break", "gdb info functions"]
aliases: ["gdb function not defined", "break main Function main not defined", "gdb pending breakpoint 설정"]
symptom_keywords: ["gdb에서 break main 했더니 Function main not defined가 뜸", "stripped 바이너리 break 안걸림", "gdb break malloc 했더니 함수 없다고 함", "Make breakpoint pending on future shared library load"]
source_ids: ["SRC-GDB-DOCS"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`Function "함수이름" not defined.`는 GDB의 현재 심볼 테이블에 그 이름의 함수가 없다는 뜻으로, 원인은 크게 (1) 바이너리가 stripped라 아예 이름 정보가 없거나, (2) 오타/C++ 네임 맹글링 때문에 이름이 다르거나, (3) 그 함수가 아직 로드되지 않은 공유 라이브러리(libc 등) 안에 있는 경우(이 경우 GDB가 `Make breakpoint pending on future shared library load? (y or [n])`를 함께 물어본다)이며, 상황에 맞게 `info functions`로 실제 이름을 찾거나 `y`로 pending 브레이크포인트를 걸거나 raw 주소로 거는 방식으로 해결한다.

## 언제 검색해야 하나
- `break main`을 쳤는데 `Function "main" not defined.`가 뜰 때
- `break malloc`이나 `break printf`처럼 libc 함수에 브레이크포인트를 걸려는데 같은 오류가 뜰 때
- C++ 바이너리에서 클래스 메서드 이름으로 `break`를 걸었는데 안 될 때
- `Make breakpoint pending on future shared library load? (y or [n])`라는 프롬프트가 왜 뜨는지, `y`를 눌러도 되는지 궁금할 때

## 핵심 개념

### 원인 ①: 바이너리 자체가 stripped — 실행 파일 안의 함수 이름이 아예 없음
`strip --strip-all`로 만든 바이너리는 `.symtab`(심볼 테이블) 섹션 자체가 제거되어 있어서, GDB는 `main`이라는 이름이 원래 어느 주소였는지 알 방법이 없다(REV-0038 참고). 이때는 이름으로 거는 대신 주소로 걸어야 한다.

### 원인 ②: 오타, 대소문자, C++ 네임 맹글링
함수 이름을 잘못 기억했거나, C++ 코드에서 컴파일러가 만든 맹글링된 이름(`_ZN7MyClass6methodEv` 같은)과 사람이 읽는 이름(`MyClass::method()`)을 혼동한 경우다. GDB는 데몬글된 이름으로도 대부분 인식하지만, 오버로드된 함수가 여러 개면 어느 것인지 특정이 안 될 수 있다.

### 원인 ③: 아직 로드되지 않은 공유 라이브러리 함수 — pending breakpoint
`malloc`, `printf`처럼 **동적으로 링크된 libc 함수**는 프로세스가 실제로 시작해서 동적 링커가 `libc.so.6`을 메모리에 매핑하기 전까지는 GDB의 심볼 테이블에 전혀 존재하지 않는다. `run`하기 전에 `break malloc`을 걸면 GDB는 이렇게 되묻는다.
```gdb
(gdb) break malloc
Function "malloc" not defined.
Make breakpoint pending on future shared library load? (y or [n]) y
Breakpoint 1 (malloc) pending.
```
`y`를 누르면 "지금 당장은 못 찾았지만, 나중에 어떤 라이브러리가 로드되면서 이 이름이 나타나면 그때 실제로 브레이크포인트를 걸어달라"는 **pending(보류) 브레이크포인트**가 설정된다. `run`을 실행해 동적 링커가 libc를 매핑하는 순간 자동으로 실제 주소에 브레이크포인트가 붙는다. 매번 `y`를 누르기 귀찮다면 아래처럼 미리 설정해둘 수 있다.
```gdb
(gdb) set breakpoint pending on
```

## 화면/코드에서 보이는 징후
```gdb
(gdb) break main
Function "main" not defined.
(gdb) break malloc
Function "malloc" not defined.
Make breakpoint pending on future shared library load? (y or [n])
```

## 가장 먼저 할 것
`info functions <이름의 일부>`로 정말 그 이름이 없는지, 있다면 어떻게 다르게 보이는지부터 확인한다.

## 단계별 절차

**1) 실제 존재하는 함수 이름 검색**
```gdb
(gdb) info functions main
(gdb) info functions ^malloc$
```
정규식을 지원하므로 부분 검색이 가능하다. C++이라면 데몬글된 이름과 맹글링된 이름이 함께 나온다.

**2) stripped 바이너리라면 셸에서 심볼 존재 여부 확인**
```bash
file ./chall
readelf -sW ./chall | grep -i FUNC | head
nm -D ./chall
```
`nm -D`는 동적 심볼 테이블(`.dynsym`)을 보여주므로, `.symtab`이 지워졌어도 동적 링킹에 필요한 최소 심볼(예: `printf@plt`로 연결되는 이름 등)은 남아있을 수 있다.

**3) stripped인데 이름 정보가 전혀 없다면 주소로 건다**
IDA/Ghidra/objdump로 함수 시작 주소를 찾은 뒤:
```gdb
(gdb) start
(gdb) info proc mappings
(gdb) break *(0x555555554000 + 0x1349)
```
PIE라면 반드시 실행 후 베이스를 구해서 더해야 한다(REV-0693 참고).

**4) 공유 라이브러리 함수라면 pending으로 걸기**
```gdb
(gdb) set breakpoint pending on
(gdb) break malloc
(gdb) run
```
또는 `run` 이후에(이미 libc가 로드된 상태) 다시 걸면 pending 질문 자체가 안 뜨고 바로 걸린다.
```gdb
(gdb) start
(gdb) break malloc
```

**5) C++ 오버로드/맹글링 문제라면 따옴표로 정확히 지정**
```gdb
(gdb) break 'MyClass::method()'
(gdb) break MyClass::method(int)
```

## 명령어/단축키
```gdb
info functions REGEX
break FUNC
break *ADDR
set breakpoint pending on
start
info proc mappings
```
```bash
nm -D ./chall
readelf -sW ./chall
```

## 출력 해석
- `info functions`에 함수 이름이 아예 안 뜨면 그 이름의 심볼은 GDB가 접근 가능한 범위 어디에도 없다는 뜻이다(stripped이거나 인라인/최적화로 사라졌을 가능성).
- `Breakpoint 1 (malloc) pending.`는 아직 실제 주소가 없는 "예약" 상태라는 뜻이며, `run` 이후 `info breakpoints`로 실제 주소가 채워졌는지 확인할 수 있다.
- `nm -D`에서 이름은 보이는데 `U`(undefined) 타입이면, 그 심볼은 이 바이너리 자체에 정의된 게 아니라 외부(libc 등)에서 온다는 뜻이므로 pending 방식으로 접근해야 한다.

## 흔한 실수
- stripped 바이너리에 대고 계속 이름으로만 걸려고 시도하는 것 — `.symtab`이 없으면 이름은 애초에 존재하지 않으므로 주소로 걸어야 한다.
- `Make breakpoint pending on future shared library load?`에 무심코 `n`을 눌러서 브레이크포인트가 아예 설정되지 않은 채 `run`을 계속 반복하는 것.
- `-O2`/`-O3` 최적화로 함수가 인라인된 경우, 그 함수 이름 자체가 최종 바이너리에는 독립된 심볼로 존재하지 않을 수 있다는 것을 모르고 계속 오타를 의심하는 것 — 이 경우 호출부 근처(caller)에 걸거나 어셈블리에서 직접 위치를 찾아야 한다.
- C++ 오버로드 함수에서 어느 버전인지 특정하지 않고 이름만 쳐서 `Breakpoint N (2 locations)`처럼 여러 곳에 걸려버리는 것을 눈치채지 못하는 것.

## 막혔을 때 다음 체크
- 아예 GDB에 파일이 안 물려 있어서 나는 비슷한 메시지라면 → REV-0686 GDB에서 No symbol table is loaded 오류가 뜰 때
- PIE 바이너리에서 주소 계산이 계속 안 맞는다면 → REV-0693 PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때
- stripped와 심볼 있는 바이너리 차이 자체가 궁금하면 → REV-0038 심볼이 있는 바이너리와 Stripped 바이너리 차이
- GDB break 문법 기초가 헷갈리면 → REV-0186 GDB break와 address breakpoint

## 미니 예제
```gdb
$ gdb -q ./chall
(gdb) break main
Function "main" not defined.
(gdb) info functions main
All functions matching regular expression "main":
Non-debugging symbols:
0x0000000000001189  main
(gdb) break *0x1189
Breakpoint 1 at 0x1189
(gdb) break malloc
Function "malloc" not defined.
Make breakpoint pending on future shared library load? (y or [n]) y
Breakpoint 2 (malloc) pending.
(gdb) run
Breakpoint 1, 0x0000555555555189 in main ()
```
`main`이라는 이름 자체는 없었지만(디버그 정보 없는 non-debugging symbol) `info functions`로 정확한 주소를 찾아 `break *0x1189`로 걸었고, `malloc`은 pending 브레이크포인트로 등록해 두었다가 `run` 이후 실제로 적용됐다.

## 관련 글
- REV-0686 — GDB에서 No symbol table is loaded 오류가 뜰 때
- REV-0693 — PIE 바이너리에서 GDB 브레이크포인트 주소가 계속 안 맞을 때
- REV-0038 — 심볼이 있는 바이너리와 Stripped 바이너리 차이
- REV-0186 — GDB break와 address breakpoint

## 출처/검증
- `Function "X" not defined.`와 pending breakpoint(`Make breakpoint pending on future shared library load?`, `set breakpoint pending`) 동작: GDB 공식 문서 "Set Breaks" 섹션 기준.
- `info functions`, `nm -D`를 통한 심볼 검색: GDB 공식 문서 및 binutils `nm(1)` man page 기준 (2026-09-08 검증).
