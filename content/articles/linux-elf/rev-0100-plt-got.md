---
id: REV-0100
title: "PLT와 GOT 기초"
slug: "rev-0100-plt-got"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [IDA, GDB, objdump, readelf]
keywords: ["PLT", "GOT", "Procedure Linkage Table", "Global Offset Table", "동적 링킹", "lazy binding"]
aliases: ["plt got", "plt란", "got란", "plt got 차이", "동적 심볼 해석"]
symptom_keywords: ["call printf인데 실제 printf가 아님", "call이 이상한 stub으로 감", "동적 라이브러리 함수 호출 추적이 안됨"]
source_ids: []
last_verified: "2026-09-08"
---

## 한 줄 요약
Linux ELF에서 `call printf`처럼 보이는 코드는 사실 **PLT(Procedure Linkage Table)** 라는 작은 트램폴린 코드를 호출하는 것이고, PLT는 **GOT(Global Offset Table)** 에 저장된 실제 libc 함수 주소로 다시 점프한다.

## 언제 검색해야 하나
- IDA/objdump에서 `call printf`라고 나오는데 실제로 그 주소로 가보면 `printf` 본체가 아니라 `jmp` 한 줄짜리 작은 코드만 있을 때
- `.plt`, `.plt.sec`, `.got`, `.got.plt` 같은 섹션 이름이 헷갈릴 때
- 동적 링킹된 라이브러리 함수의 실제 주소가 실행 전에는 왜 확정되지 않는지 이해하고 싶을 때

## 핵심 개념

### 왜 이런 간접 구조가 필요한가
동적 링킹된 ELF 실행 파일은 `printf`, `malloc` 같은 함수의 실제 코드를 자기 안에 갖고 있지 않다. 그 코드는 `libc.so.6` 같은 공유 라이브러리 안에 있고, **프로그램이 실행될 때 로더(ld.so)가 라이브러리를 메모리에 매핑한 뒤에야 그 함수의 실제 주소가 정해진다.** 컴파일 시점에는 그 주소를 알 수 없다.

그런데 컴파일러는 `call printf`라는 명령어를 코드 어딘가에 이미 박아넣어야 한다. 이 문제를 푸는 방법이 **PLT + GOT**라는 두 단계 간접 호출 구조다.

### GOT (Global Offset Table)
GOT는 함수 포인터들의 배열이다. 처음에는(로더가 아직 값을 채우기 전) 각 슬롯이 PLT 내부의 "resolver 호출 코드"를 가리키도록 초기화되어 있다. 함수가 실제로 처음 호출되면 그 시점에 로더가 진짜 함수 주소를 찾아 GOT 슬롯에 덮어쓴다. 이후 같은 함수를 다시 호출하면 GOT에 이미 진짜 주소가 있으므로 바로 그 주소로 점프한다.

### PLT (Procedure Linkage Table)
PLT는 각 외부 함수마다 하나씩 존재하는 짧은 코드 조각(스텁, stub)이다. 대략 이런 모양이다 (x64, 단순화):
```asm
printf@plt:
    jmp   qword ptr [rip + GOT_offset_for_printf]   ; GOT 슬롯의 값으로 점프
```
프로그램 코드에서 `call printf`라고 쓰여있는 것은 실제로 `call printf@plt`이고, PLT 스텁이 GOT에 저장된 값으로 다시 점프(jmp)한다.

### Lazy Binding (지연 바인딩)
기본 동작(Lazy binding)에서는 함수가 **처음 호출될 때만** 실제 주소를 찾는(resolve) 비용을 지불한다:
1. 첫 호출: `call printf@plt` → PLT 스텁이 GOT의 아직 초기화 안 된 값(=PLT 내부의 resolver 코드 주소)으로 점프 → resolver(`_dl_runtime_resolve`)가 동적 심볼 테이블을 뒤져 진짜 `printf` 주소를 찾음 → 그 주소를 GOT에 써넣고 → 그 주소로 점프해서 실제 `printf` 실행.
2. 두 번째 호출부터: `call printf@plt` → PLT 스텁이 이번엔 GOT에 이미 채워진 **진짜 printf 주소**로 바로 점프 → resolver를 거치지 않음.

이 최적화 덕분에 프로그램이 한 번도 안 쓰는 함수는 주소 해석 비용을 아예 안 낸다.

`RELRO`(RELocation Read-Only) 보호가 `Full RELRO`로 켜져 있으면, 프로그램 시작 시점에 모든 GOT 엔트리를 즉시 채우고(Lazy binding 대신 Eager binding) GOT 전체를 읽기 전용으로 만들어버려 GOT 변조 공격을 막는다. `checksec` 결과의 `RELRO` 항목이 바로 이걸 알려준다 (REV-0102 참고).

## 화면/코드에서 보이는 징후
- IDA/objdump에서 함수 이름이 `printf`가 아니라 `printf@plt` 또는 `.plt`섹션 주소로 표시됨
- 그 주소로 들어가 보면 명령어가 몇 개 안 되고 결국 `jmp`로 끝남
- GDB에서 `x/3i printf@plt` 실행 시 `jmp *0x...(GOT주소)` 형태의 코드가 보임
- 섹션 목록에 `.plt`, `.plt.sec`(최신 glibc, CET 지원), `.got`, `.got.plt`가 따로 존재

## 가장 먼저 할 것
CALL 대상 이름에 신경 쓰지 말고(IDA가 알아서 `printf`라고 붙여준다), 이것이 **내가 작성한 코드가 아니라 외부 라이브러리 함수를 부르는 것**이라는 사실만 인지하면 충분하다. 그 함수의 정확한 동작이 궁금하면 GDB로 실제 실행 중 인자를 확인하거나 libc 문서를 참고한다 — PLT 스텁 자체의 코드를 분석할 필요는 거의 없다.

## 단계별 절차

**1) PLT 엔트리 확인 (정적)**
```bash
objdump -d ./chall | grep -A3 '<printf@plt>:'
```
출력 예 (단순화):
```
0000000000401030 <printf@plt>:
  401030: ff 25 e2 2f 00 00    jmp    *0x2fe2(%rip)   # GOT 주소
```

**2) GOT 슬롯 확인**
```bash
readelf -r ./chall | grep printf
```
`R_X86_64_JUMP_SLOT` 타입의 재배치 엔트리로 `printf`가 나오면, 이 GOT 슬롯이 로더에 의해 나중에 채워질 자리라는 뜻이다.

**3) GDB로 런타임에 실제 주소 확인 (동적)**
```gdb
break main
run
print printf
```
`run` 이후(라이브러리가 로드된 상태) `print printf`를 하면 실제 libc 안의 주소가 출력된다. `printf@plt`와 다른 주소임을 확인할 수 있다.

**4) Pwndbg로 GOT 상태 한눈에 보기**
```gdb
got
```
Pwndbg의 `got` 명령은 바이너리의 모든 GOT 엔트리와, 현재 실제 함수를 가리키는지(resolved) 아직 PLT resolver를 가리키는지(lazy, 아직 안 불림)를 색으로 구분해서 보여준다.

**5) 첫 호출 vs 이후 호출 차이 관찰**

`printf@plt`에 브레이크포인트를 걸고 두 번 연속 호출하는 프로그램을 실행해보면, 첫 번째 호출 때는 resolver 코드(`_dl_runtime_resolve_xsavec` 등)를 거쳐 시간이 조금 더 걸리고, 두 번째 호출부터는 GOT에 저장된 값으로 바로 점프하는 것을 스텝 실행(stepi)으로 관찰할 수 있다.

## 명령어/단축키
```bash
objdump -d ./chall | grep '@plt'
readelf -r ./chall
checksec --file=./chall     # RELRO 상태 확인
```
GDB/Pwndbg: `got`, `x/3i <plt주소>`, `print <함수이름>`

## 출력 해석
- `checksec` 결과 `RELRO: Full RELRO`면 GOT가 읽기 전용이라 GOT overwrite 공격이 막혀 있다는 뜻(리버싱보다 pwn 관점에서 중요).
- `RELRO: Partial RELRO`면 GOT가 쓰기 가능한 상태 — lazy binding이 그대로 동작한다.
- `readelf -r` 출력에서 `JUMP_SLOT` 타입은 함수용 GOT 엔트리, `GLOB_DAT`는 전역 변수용 GOT 엔트리다.

## 흔한 실수
- `call printf`가 보이면 "printf 본체가 여기 있다"고 착각하는 것 — 실제로는 PLT 스텁이고, 진짜 코드는 런타임에 로드되는 libc 안에 있다.
- PLT와 GOT를 같은 것으로 혼동하는 것 — PLT는 **코드**(점프하는 명령어들), GOT는 **데이터**(주소가 저장된 테이블)다. PLT가 GOT를 참조해서 점프한다.
- 정적 링킹된 바이너리에서도 PLT/GOT가 있을 거라 기대하는 것 — 정적 링킹이면 라이브러리 코드가 바이너리 안에 통째로 포함되므로 PLT/GOT 간접 구조 자체가 필요 없다(`call printf`가 진짜 printf 코드로 direct call됨).

## 막혔을 때 다음 체크
- GOT 값이 왜 실행마다 달라지는지 궁금하면 → PIE/ASLR 관련 REV-0103, REV-0104(예정)로 이동.
- RELRO가 무엇을 의미하는지 더 알고 싶다면 → REV-0102 RELRO가 리버싱에 의미하는 것(예정).
- 임포트 함수 호출을 CALL 명령어 관점에서 더 깊이 알고 싶다면 → REV-0071(CALL 명령어) 참고.

## 미니 예제
```bash
$ objdump -d ./chall | grep -A2 '<puts@plt>:'
0000000000401040 <puts@plt>:
  401040: ff 25 c2 2f 00 00    jmp    *0x2fc2(%rip)
  401046: 68 00 00 00 00       push   $0x0

$ gdb ./chall
(gdb) break *0x401040
(gdb) run
(gdb) x/3i $pc
=> 0x401040 <puts@plt>: jmp    *0x2fc2(%rip)
```
브레이크포인트를 건 지점(`puts@plt`)에서 `jmp *0x2fc2(%rip)`가 실행되기 직전이다. 이 명령이 참조하는 메모리(GOT 슬롯)의 값을 `x/gx $rip+6+0x2fc2` 형태로 확인하면, 처음 실행 시엔 resolver 주소, 두 번째 실행 시엔 실제 `puts` 주소가 들어있는 것을 볼 수 있다.

## 관련 글
- REV-0071 — CALL: 함수 호출, 반환 주소, 인자 추적
- REV-0101 — Dynamic Linking과 Import 함수 추적
- REV-0102 — RELRO가 리버싱에 의미하는 것
- REV-0097 — ELF Entry Point에서 main까지

## 출처/검증
- PLT/GOT lazy binding 동작: System V Application Binary Interface, "Procedure Linkage Table" 섹션 및 glibc `elf/dl-runtime.c`(`_dl_runtime_resolve`) 개념 기준 (2026-09-08 검증).
- RELRO 개념: Fedora/Red Hat "Full/Partial RELRO" 보안 기능 설명 기준.
- Pwndbg `got` 명령: Pwndbg 공식 GitHub 문서/명령어 목록 기준.
