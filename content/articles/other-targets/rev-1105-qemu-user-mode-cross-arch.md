---
id: REV-1105
title: "QEMU user-mode로 다른 아키텍처 바이너리 실행하기(qemu-arm/qemu-mips)"
slug: "rev-1105-qemu-user-mode-cross-arch"
category: "other-targets"
difficulty: "basic"
platform: [linux]
architecture: [ARM, ARM64]
format: [ELF]
tools: [QEMU, GDB]
keywords: ["qemu-arm", "qemu-mips", "qemu-user", "QEMU user-mode", "-L sysroot", "chroot ARM 바이너리 실행"]
aliases: ["ARM 바이너리 x86에서 실행", "다른 아키텍처 바이너리 돌리기", "qemu-arm-static 사용법", "펌웨어 바이너리 에뮬레이션"]
symptom_keywords: ["ARM 바이너리인데 x86 PC에서 실행이 안 됨", "cannot execute binary file Exec format error", "동적 링크된 라이브러리를 못 찾음(다른 아키텍처)"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-10"
---

## 한 줄 요약
QEMU user-mode 에뮬레이션(`qemu-arm`, `qemu-mips` 등)은 CPU 명령어와 시스템 콜만 번역해 다른 아키텍처용 리눅스 바이너리 하나를 x86 호스트에서 그대로 실행시켜주는 도구로, 정적 링크 바이너리는 바로 실행되지만 동적 링크 바이너리는 `-L` 옵션으로 대상 아키텍처의 라이브러리가 담긴 sysroot 경로를 함께 지정해야 동적 링커가 올바른 `.so`를 찾을 수 있다.

## 언제 검색해야 하나
- CTF 문제나 펌웨어에서 뽑아낸 파일이 ARM/MIPS용인데 이를 x86_64 리눅스 PC에서 직접 실행하며 동적 분석을 하고 싶을 때
- 그냥 실행했더니 `bash: ./chall: cannot execute binary file: Exec format error`가 뜰 때
- GDB로 원격 디버깅을 하고 싶은데 실제 ARM/MIPS 장비가 없을 때
- 동적 링크된 ARM 바이너리를 QEMU로 실행했더니 `error while loading shared libraries` 종류의 오류가 날 때

## 핵심 개념

### QEMU의 두 가지 모드 — full-system vs user-mode
QEMU는 전체 운영체제를 통째로 가상화하는 full-system 모드(`qemu-system-arm` 등)와, 리눅스 실행 파일 하나만 골라 CPU 명령어와 시스템 콜을 번역해 호스트 커널 위에서 바로 돌리는 user-mode 에뮬레이션(`qemu-arm`, `qemu-mips` 등)으로 나뉜다. CTF/리버싱에서 특정 바이너리 하나만 빠르게 돌려보고 싶을 때는 부팅 과정이 필요 없는 user-mode가 훨씬 가볍고 빠르다.

### user-mode가 내부적으로 하는 일
QEMU 공식 문서에 따르면 user-mode 에뮬레이터는 게스트 프로그램이 발생시키는 시스템 콜을 가로채 "범용 시스템 콜 변환기"를 통해 엔디안·32/64비트 파라미터 크기 등을 조정한 뒤 호스트 커널의 동등한 시스템 콜을 대신 호출해준다. 디바이스별 `ioctl()` 호출도 비슷하게 번역되고, POSIX 시그널도 호스트 시그널을 게스트 프로그램으로 리다이렉트하거나 가상 CPU 폴트(예: 0으로 나누기 → `SIGFPE`)로부터 합성해 전달한다. 즉 커널 자체는 에뮬레이션하지 않고, "이 CPU 명령어들이 하는 일"과 "커널에 요청하는 내용"만 번역하는 것이다.

### 아키텍처별 실행 파일 이름
QEMU는 대상 아키텍처/ABI/엔디안 조합마다 별도의 실행 파일을 제공한다. 예를 들어 `qemu-arm`, `qemu-armeb`(빅엔디안), `qemu-aarch64`(64비트 ARM), `qemu-mips`(32비트 빅엔디안 MIPS, O32 ABI), `qemu-mipsel`(리틀엔디안), `qemu-mips64` 등이 있다. 배포판 패키지에서는 정적으로 빌드된 `qemu-arm-static`류 이름으로 제공되는 경우도 흔하다(정적 빌드는 QEMU 자신이 호스트에 동적 라이브러리 의존성을 갖지 않게 해, chroot 환경 안에 QEMU 바이너리 하나만 복사해 넣어도 동작하게 만들기 위함).

### -L 옵션과 동적 링크 문제
정적으로 링크된 대상 바이너리는 필요한 코드가 파일 안에 다 들어있으므로 QEMU만 있으면 바로 실행된다. 반면 동적 링크된 바이너리는 실행 시점에 대상 아키텍처용 `ld.so`와 `libc.so` 등을 찾아야 하는데, 호스트의 x86용 라이브러리는 당연히 쓸 수 없다. `-L path` 옵션은 이 문제를 해결하기 위한 것으로, 지정한 경로를 대상 아키텍처 라이브러리들의 루트(sysroot)로 취급하게 한다. 예를 들어 크로스 컴파일 툴체인이나 대상 장비의 루트 파일시스템을 통째로 복사해온 디렉터리를 `-L`로 지정하면, QEMU가 그 안에서 `/lib/ld-linux-armhf.so.3` 등을 찾아 정상적으로 로드한다.

### chroot와 binfmt_misc로 더 매끄럽게 만들기
`-L`을 매번 지정하는 대신, 대상 아키텍처의 루트 파일시스템 디렉터리 안에 정적 빌드된 QEMU user-mode 바이너리를 복사해 넣고 그 디렉터리로 `chroot`하면, 마치 진짜 그 아키텍처 환경에 들어간 것처럼 여러 바이너리를 자연스럽게 실행할 수 있다. 여기에 리눅스 커널의 `binfmt_misc` 기능으로 "ELF 헤더의 machine 필드가 ARM이면 자동으로 `qemu-arm-static`을 실행기로 사용하라"고 등록해두면, 별도로 `qemu-arm ./chall`이라고 치지 않고 그냥 `./chall`만 실행해도 커널이 알아서 QEMU를 통해 실행해준다(Docker의 멀티아키텍처 빌드가 내부적으로 쓰는 방식이기도 하다).

## 화면/코드에서 보이는 징후
- `./chall` 직접 실행 시 `Exec format error` 또는 `cannot execute binary file`
- `file ./chall` 결과가 `ELF 32-bit ... ARM, EABI5` 등 호스트와 다른 아키텍처로 나옴
- 동적 링크된 대상 바이너리를 QEMU로 실행했더니 `/lib/ld-linux-armhf.so.3: No such file or directory` 류의 오류
- CTF 문제 파일과 함께 `lib/`, `rootfs/` 같은 디렉터리가 배포되어 있음(로컬 sysroot로 쓰라는 의도)

## 가장 먼저 할 것
`file ./chall`로 정확한 대상 아키텍처/엔디안/ABI를 확인하고, `ldd ./chall`(또는 `readelf -d`)로 동적 링크 여부를 확인한 뒤, 정적 링크면 바로 `qemu-arm ./chall`을, 동적 링크면 대상 아키텍처 라이브러리 경로를 `-L`로 준비해야 한다는 것부터 인지한다.

## 단계별 절차
1. `file ./chall`로 아키텍처(ARM/ARM64/MIPS 등), 엔디안, EABI 버전 확인
2. `sudo apt install qemu-user qemu-user-static`(또는 배포판에 맞는 패키지)로 QEMU user-mode 에뮬레이터 설치
3. 정적 링크 바이너리면: `qemu-arm ./chall`로 바로 실행 시도
4. 동적 링크 바이너리면: 문제와 함께 제공된 라이브러리 디렉터리 또는 크로스 툴체인의 sysroot 경로를 확보하고 `qemu-arm -L /path/to/sysroot ./chall`로 실행
5. GDB로 원격 디버깅하려면 `qemu-arm -g <port> ./chall`로 QEMU를 대기 상태로 띄우고, 별도 터미널에서 `gdb-multiarch ./chall` 후 `target remote :<port>`로 연결
6. 여러 바이너리를 반복 실행해야 하면 sysroot 디렉터리에 `qemu-arm-static`을 복사해 넣고 `chroot /path/to/sysroot ./chall`로 전환하는 방법도 고려

## 명령어/단축키
```bash
# 설치 (Debian/Ubuntu 계열)
sudo apt install qemu-user qemu-user-static

# 정적 링크 ARM 바이너리 바로 실행
qemu-arm ./chall

# 동적 링크 바이너리 - sysroot 지정
qemu-arm -L /path/to/arm-sysroot ./chall

# MIPS(빅엔디안 O32) 바이너리 실행
qemu-mips ./chall_mips

# GDB 원격 디버깅용으로 QEMU를 정지 상태로 대기
qemu-arm -g 1234 ./chall
# 다른 터미널에서
gdb-multiarch ./chall
(gdb) target remote :1234

# chroot 방식 (sysroot 안에 qemu-arm-static을 미리 복사해둔 경우)
sudo cp $(which qemu-arm-static) /path/to/arm-sysroot/usr/bin/
sudo chroot /path/to/arm-sysroot ./chall
```

## 출력 해석
`qemu-arm ./chall` 실행 후 `/lib/ld-linux-armhf.so.3: No such file or directory`가 나오면, 이는 x86 호스트 자체에 그 파일이 없다는 뜻이 아니라 QEMU가 대상 아키텍처의 동적 링커를 sysroot 안에서 찾지 못했다는 의미다 — `-L`로 올바른 sysroot를 지정하면 해결된다. 반대로 아무 오류 없이 프로그램이 정상 출력을 내면, 그 바이너리는 정적 링크이거나 `-L` 없이도 찾을 수 있는 위치에 라이브러리가 있었다는 뜻이다.

## 흔한 실수
- 대상 바이너리의 정확한 아키텍처(예: ARM 하드플로트 `armhf` vs 소프트플로트 `armel`)를 확인하지 않고 아무 sysroot나 연결해 여전히 라이브러리를 못 찾는 것.
- 32비트 ARM 바이너리에 `qemu-aarch64`(64비트용)를 쓰거나 그 반대로 실행해 즉시 실패하는 것 — 아키텍처와 비트수를 정확히 맞춰야 한다.
- `-L` 옵션 없이 동적 링크 바이너리를 실행해놓고 "QEMU가 고장났다"고 오해하는 것.
- 에뮬레이션 성능 문제를 잊는 것 — user-mode QEMU는 명령어 단위 번역이라 네이티브보다 느리므로, 무한루프나 브루트포스가 포함된 바이너리는 예상보다 훨씬 오래 걸릴 수 있다.

## 막혔을 때 다음 체크
- 대상 코드가 ARM인지 Thumb인지, 32비트인지 64비트인지부터 헷갈리면 → REV-1101 ARM/ARM64 레지스터와 호출 규약 기초, REV-1102 ARM Thumb 모드가 무엇이고 왜 헷갈리는지
- QEMU로 실행은 됐는데 정적으로도 구조를 보고 싶다면 → REV-1104 Ghidra/IDA에서 ARM 바이너리 아키텍처 설정하기
- GDB 자체 명령어가 기억 안 나면 → REV-0284 GDB 명령어 치트시트
- 정적 링킹된 바이너리라 라이브러리 함수 식별이 어렵다면(아키텍처는 다르지만 개념은 동일) → REV-0646 정적 링킹된(Statically Linked) ELF 분석 접근법

## 미니 예제
```bash
$ file chall
chall: ELF 32-bit LSB executable, ARM, EABI5 version 1 (SYSV), dynamically linked, ...

$ qemu-arm ./chall
/lib/ld-linux-armhf.so.3: No such file or directory

$ qemu-arm -L ./arm-rootfs ./chall
Welcome! Enter password: 
```
첫 시도는 동적 링커를 못 찾아 실패했지만, 문제와 함께 제공된(또는 직접 준비한) `arm-rootfs` 디렉터리를 `-L`로 지정하자 정상적으로 프로그램이 실행되어 표준입력을 기다리는 상태까지 도달한 예다.

## 관련 글
- REV-1101 — ARM/ARM64 레지스터와 호출 규약 기초
- REV-1104 — Ghidra/IDA에서 ARM 바이너리 아키텍처 설정하기
- REV-0284 — GDB 명령어 치트시트
- REV-0646 — 정적 링킹된(Statically Linked) ELF 분석 접근법

## 출처/검증
- QEMU user-mode가 시스템 콜/ioctl을 호스트 커널용으로 번역하고 시그널을 리다이렉트/합성하는 동작 방식, `qemu-arm`/`qemu-mips` 등 아키텍처별 실행 파일과 `-L`(sysroot/interpreter prefix 지정) 옵션: QEMU 공식 문서 - User Mode Emulation (https://www.qemu.org/docs/master/user/main.html) 기준 확인(2026-09-10).
- 정적 빌드(`qemu-*-static`) 배포 관행과 `chroot`/`binfmt_misc`를 결합해 자동 실행하는 방식은 QEMU 공식 문서에 직접 명시되어 있지 않으나, 리눅스 커널 `binfmt_misc` 메커니즘과 결합해 크로스 아키텍처 실행을 자동화하는 것은 널리 알려진 표준 관행(Docker `buildx`/`binfmt` 등에서 채택)이다.
