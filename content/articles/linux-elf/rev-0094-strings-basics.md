---
id: REV-0094
title: "strings로 빠르게 단서 찾기"
slug: "rev-0094-strings-basics"
category: "linux-elf"
difficulty: "beginner"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: ["strings", "binutils"]
keywords: ["strings", "strings -a", "strings -n", "문자열 추출", "wide string", "UTF-16 문자열"]
aliases: ["strings 사용법", "strings 옵션", "strings 명령어", "문자열로 분석"]
symptom_keywords: ["바이너리에서 문자열만 빠르게 뽑고 싶음", "flag 문자열이 안 보임", "strings로 아무것도 안나옴"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-08"
---

## 한 줄 요약
`strings`는 바이너리 파일 안에서 사람이 읽을 수 있는 연속된 텍스트(ASCII/유니코드) 조각을 전부 뽑아 보여주는 도구로, 어떤 분석 도구를 쓰기도 전에 "이 바이너리가 뭘 하는지" 감을 잡는 가장 빠른 첫 삽질이다.

## 언제 검색해야 하나
- 바이너리를 받자마자 5초 안에 "이게 뭐 하는 프로그램인지" 대략 감을 잡고 싶을 때
- `flag{`, `Enter password`, 에러 메시지 같은 문자열을 코드를 하나도 안 읽고 먼저 찾아보고 싶을 때
- IDA의 Strings 창(Shift+F12)과 같은 정보를 커맨드라인에서 얻고 싶을 때
- 실행 파일이 아니라 core dump, 메모리 덤프, 알 수 없는 바이너리 blob에서도 텍스트 단서를 찾고 싶을 때

## 핵심 개념
`strings`는 ELF 구조를 전혀 이해하지 못해도 동작한다. 그냥 파일을 처음부터 끝까지 바이트 단위로 훑으면서, **연속으로 출력 가능한(printable) 문자가 기본 4바이트 이상** 이어지다가 널바이트(`\0`)나 비출력 문자로 끊기면 그 구간을 하나의 문자열로 뽑아 출력한다. 그래서 ELF든 PE든 압축된 파일이든 순수 바이너리 blob이든 상관없이 무조건 실행할 수 있는 것이 장점이다.

컴파일된 프로그램 안에는 코드가 참조하는 문자열 리터럴(`printf("Enter password: ")`의 `"Enter password: "` 부분)이 `.rodata` 섹션에 그대로 텍스트로 남아있다. 이걸 미리 훑어보면 코드를 한 줄도 안 읽고도 "이 프로그램이 비밀번호를 요구하는구나", "flag 문자열 형식이 `flag{...}`구나" 같은 정보를 얻을 수 있다.

## 화면/코드에서 보이는 징후
분석 워크플로의 거의 항상 첫 단계로 등장한다. IDA/Ghidra를 열기 전에도, 열고 나서도(Strings 창) 계속 참조하게 되는 정보다.

## 가장 먼저 할 것
```bash
strings ./chall | less
```
또는 눈에 띄는 키워드부터 바로 찾는다:
```bash
strings ./chall | grep -iE 'flag|password|correct|wrong|key'
```

## 단계별 절차

**1) 기본 실행**
```bash
strings ./chall
```
기본적으로 4바이트 이상 연속된 ASCII printable 문자열만 출력한다.

**2) 최소 길이 조정**
```bash
strings -n 8 ./chall     # 8바이트 이상만 (짧은 노이즈 제거)
strings -n 3 ./chall     # 3바이트 이상까지 (더 촘촘히, 노이즈 증가)
```

**3) 파일 내 위치(오프셋)도 같이 보기**
```bash
strings -t x ./chall     # 16진수 오프셋과 함께 출력
```
출력 예:
```
   2004 Enter the password:
   2019 Correct!
   2022 Wrong password
```
이 오프셋을 `readelf -S`(REV-0091)나 IDA의 "Jump to file offset" 기능과 대조하면, 그 문자열이 정확히 어느 섹션/주소에 있는지 추적할 수 있다.

**4) 어느 섹션에서 나왔는지까지 표시**
```bash
strings -t x -a ./chall
```
`-a`(`--all`)는 파일 전체를 대상으로 스캔(기본값이 이미 전체인 GNU strings에서는 명시적 의미가 약하지만, 일부 구버전/다른 OS의 strings에서는 로드 가능한 섹션만 보는 게 기본이라 `-a`가 필요할 수 있다).

**5) 와이드 문자열(UTF-16, Windows 프로그램/일부 유니코드 문자열)도 찾기**
```bash
strings -e l ./chall     # little-endian 16bit 문자
strings -e b ./chall     # big-endian 16bit 문자
```
Linux ELF 바이너리에서는 잘 안 쓰이지만, 크로스 컴파일된 바이너리나 임베딩된 리소스에서 필요할 수 있다.

**6) grep과 조합해서 바로 단서 찾기**
```bash
strings ./chall | grep -iE 'flag\{|password|scanf|Usage'
```

## 명령어/단축키
```bash
strings ./chall                       # 기본(4바이트 이상 ASCII)
strings -n 6 ./chall                  # 최소 길이 조정
strings -t x ./chall                  # 16진수 오프셋 포함
strings ./chall | grep -i flag        # 키워드 필터
strings ./chall | sort -u             # 중복 제거
```

## 출력 해석
- 짧은 문자열(3~4글자)은 대부분 노이즈(코드 바이트가 우연히 printable 범위와 겹친 것)다. `-n` 값을 6~8 정도로 올리면 노이즈가 크게 줄어든다.
- 컴파일러/링커가 자동으로 삽입한 문자열(`GCC: (Ubuntu ...)`, `GLIBC_2.34`, 섹션 이름 등)과 실제 프로그램 로직이 참조하는 문자열이 섞여 나온다 — 처음엔 구분이 어렵지만, 대체로 사용자 메시지처럼 보이는 문장형 텍스트가 실제 단서다.
- `flag{`처럼 시작하는 문자열이 바로 나온다면, 하드코딩된 flag이거나(문제 설계상 의도된 것일 수도, 아닐 수도) 최소한 flag 포맷을 미리 알 수 있어 이후 검증 로직을 읽을 때 무엇을 찾아야 하는지 기준이 생긴다.

## 흔한 실수
- `strings` 결과에 원하는 문자열이 안 보인다고 "이 바이너리엔 문자열이 없다"고 결론 내리는 것 — 문자열이 암호화/인코딩되어 저장되고 실행 중에만 복호화되는 경우, UPX 등으로 패킹된 경우 등은 정적으로 안 보인다. 이럴 땐 동적 분석(디버거로 실행 중 메모리 dump)이 필요하다.
- `strings` 결과의 문자열이 코드에서 실제로 어떻게 쓰이는지 확인하지 않고 넘어가는 것 — IDA/Ghidra에서 해당 문자열을 찾아 Xref(참조하는 함수)로 이동해야 진짜 의미를 알 수 있다. `strings` 자체는 "존재한다"만 알려줄 뿐 "어떻게 쓰이는지"는 알려주지 않는다.
- 기본 최소 길이(4바이트)가 항상 적절하다고 가정하는 것 — 짧은 키(예: XOR 키 문자열)를 찾을 땐 `-n 2`나 `-n 3`으로 낮춰야 보일 수 있다.

## 막혔을 때 다음 체크
- 찾은 문자열이 코드 어디서 참조되는지 추적하려면 → IDA/Ghidra의 Xref 기능, 또는 [REV-0092 objdump 기본 사용법](./rev-0092-objdump-basics.md)으로 `.rodata` 오프셋 대조
- 문자열도 임포트 함수도 거의 안 보이면 패킹/난독화 의심 → 파일 종류부터 재확인: [REV-0095 file 명령으로 ELF 정보 확인](./rev-0095-file-command.md)
- `main`을 아직 못 찾았다면 → [REV-0009 main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)

## 미니 예제
```bash
$ strings -n 6 -t x chall | head
    1188 GCC: (Ubuntu 13.2.0-4ubuntu3) 13.2.0
    2004 Enter the password: 
    201a Correct! flag{sample_flag_value}
    2035 Wrong password.

$ strings chall | grep -i flag
Correct! flag{sample_flag_value}
```
단 두 줄 명령으로 이 프로그램이 비밀번호를 입력받고, 정답이면 flag를 출력한다는 것과 flag 포맷까지 코드를 한 줄도 안 읽고 파악했다. (실전에서는 flag가 이렇게 그대로 하드코딩된 경우도 있지만, 비교 로직 안에 숨겨져 있는 경우가 더 많으므로 반드시 코드로 검증해야 한다.)

## 관련 글
- [REV-0009 — main 함수가 안 보일 때 찾는 방법](../triage/rev-0009-finding-main.md)
- [REV-0092 — objdump 기본 사용법](./rev-0092-objdump-basics.md)
- [REV-0095 — file 명령으로 ELF 정보 확인](./rev-0095-file-command.md)

## 출처/검증
- 옵션과 기본 동작(4바이트 최소 길이): GNU binutils `strings(1)` man page 기준 (2026-09-08 검증).
