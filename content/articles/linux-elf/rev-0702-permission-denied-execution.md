---
id: REV-0702
title: "Permission denied로 바이너리 실행이 안 될 때"
slug: "rev-0702-permission-denied-execution"
category: "linux-elf"
difficulty: "basic"
platform: [linux]
architecture: [x86, x64]
format: [ELF]
tools: [chmod, mount, dmesg]
keywords: ["Permission denied", "chmod +x", "noexec", "실행 권한", "실행 파일 권한 오류"]
aliases: ["실행이 안 됨 permission denied", "bash Permission denied", "chmod x 안 먹힘", "noexec 마운트"]
symptom_keywords: ["./chall 실행하면 Permission denied가 뜸", "chmod +x 했는데도 실행이 안 됨", "다운받은 바이너리를 실행하면 권한 오류가 남", "/tmp에서 실행하면 Permission denied가 뜸"]
source_ids: ["SRC-GENERAL-REVERSING", "SRC-SYSV-ABI"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`./chall`을 실행했을 때 나오는 `bash: ./chall: Permission denied`는 대부분 실행 비트(`x`)가 없거나, 파일 시스템이 `noexec` 옵션으로 마운트되어 있거나, 디렉터리 자체에 실행 권한이 없어서 발생하며, 아키텍처 문제로 나는 `Exec format error`와는 원인과 해결책이 다르다.

## 언제 검색해야 하나
- CTF에서 받은 바이너리를 `chmod +x` 없이 바로 실행해서 `Permission denied`가 뜰 때
- `chmod +x ./chall`을 분명히 했는데도 여전히 같은 오류가 날 때
- 압축을 풀거나 다운로드한 위치(`/mnt/c/...`, Windows 공유 드라이브 등)에서 실행이 안 될 때
- Docker/WSL 환경에서 특정 디렉터리(`/tmp`, 마운트된 볼륨)에서만 실행이 안 될 때

## 핵심 개념

### 실행 비트가 없는 가장 흔한 경우
리눅스에서 파일을 실행하려면 그 파일에 실행 권한(`x`) 비트가 있어야 한다. `wget`, `scp`, 압축 해제(`unzip`, `tar`) 등으로 받은 파일은 기본적으로 실행 비트가 빠진 채로 저장되는 경우가 많다. `ls -l ./chall` 결과 앞자리가 `-rw-r--r--`처럼 `x`가 하나도 없으면 이 경우다.

### chmod +x를 했는데도 안 되는 경우 — noexec 마운트
`chmod +x`를 했는데도 여전히 `Permission denied`가 난다면, 파일 자체 권한이 아니라 **그 파일이 놓인 파일 시스템이 `noexec` 옵션으로 마운트되어 있는 경우**를 의심해야 한다. 예를 들어 일부 시스템에서 `/tmp`나 `/dev/shm`, USB/네트워크 마운트 지점이 보안상 `noexec`로 마운트되어 있으면, 그 안의 파일은 실행 비트가 있어도 커널이 실행 자체를 거부한다. WSL 환경에서 Windows 쪽 드라이브(`/mnt/c/...`)가 `noexec` 옵션으로 마운트된 경우도 흔하다.

### 디렉터리 자체의 실행(x) 권한 부족
파일이 아니라 그 파일이 들어있는 **디렉터리**에 실행 권한이 없어도 `Permission denied`가 난다. 디렉터리의 `x` 비트는 "그 디렉터리 안의 파일에 접근(경로 통과)할 수 있는가"를 의미하므로, 상위 디렉터리 중 하나라도 `x`가 빠져 있으면 파일 자체 권한과 무관하게 실행이 막힌다.

### 착각하기 쉬운 다른 오류와 구분
`Permission denied`와 `cannot execute binary file: Exec format error`는 완전히 다른 문제다. 후자는 아키텍처 불일치(32비트 바이너리를 32비트 지원 없는 시스템에서 실행 등)나 손상된 헤더 때문이며, 권한과는 무관하다. 또한 SELinux/AppArmor 같은 강제 접근 제어(MAC)가 걸린 배포판에서는 권한 비트가 다 맞아도 정책에 의해 거부될 수 있는데, 이 경우 `dmesg`에 `avc: denied` 같은 로그가 남는다.

## 화면/코드에서 보이는 징후
```
$ ./chall
bash: ./chall: Permission denied

$ chmod +x ./chall
$ ./chall
bash: ./chall: Permission denied
```
`chmod +x` 이후에도 동일 오류가 반복되면 파일 권한이 아니라 마운트 옵션/디렉터리 권한/MAC 정책 쪽 문제다.

## 가장 먼저 할 것
`ls -l ./chall`로 실행 비트 유무를 확인하고, 없으면 `chmod +x ./chall`부터 시도한다. 그래도 안 되면 `mount | grep "$(df --output=target . | tail -1)"`로 현재 위치의 마운트 옵션에 `noexec`가 있는지 확인한다.

## 단계별 절차
1. `ls -l ./chall`로 `x` 비트 확인
2. 없으면 `chmod +x ./chall` 실행 후 재시도
3. 그래도 `Permission denied`면 `mount | grep noexec`로 현재 파일 시스템이 noexec인지 확인
4. noexec이면 실행 가능한 위치(`~/` 홈 디렉터리 등)로 파일을 복사해서 그쪽에서 실행
5. 여전히 안 되면 `namei -l ./chall`로 경로상의 모든 디렉터리 권한을 한 줄씩 점검(상위 디렉터리 `x` 비트 누락 확인)
6. 그래도 이상하면 `dmesg | tail -20`으로 SELinux/AppArmor 거부 로그(`avc: denied`, `apparmor="DENIED"`) 확인

## 명령어/단축키
```bash
ls -l ./chall
chmod +x ./chall
mount | grep noexec
df --output=target .
namei -l ./chall
dmesg | tail -20
```

## 출력 해석
`mount` 결과에서 현재 경로가 속한 줄에 `noexec`가 보이면 원인이 확정된 것이다. `namei -l` 출력에서 어느 한 줄의 권한이 `d---------` 등으로 `x`가 빠져 있으면 그 디렉터리가 원인이다. `dmesg`에 `avc: denied { execute }` 같은 줄이 있으면 SELinux 정책이 원인이다.

## 흔한 실수
- `chmod +x`만 하고 그래도 안 되면 "권한을 더 풀어야 하나"라며 `chmod 777`을 반복 시도하는 것 — noexec 마운트는 파일 권한을 아무리 바꿔도 소용없다.
- `Permission denied`와 `Exec format error`를 같은 문제로 보고 아키텍처 문제 해결법을 시도하는 것.
- root로 실행하면 되겠지 하고 `sudo ./chall`을 시도하는 것 — noexec 마운트는 root 권한과 무관하게 커널이 막는다. 실행 가능한 위치로 옮기는 것이 정답이다.
- 상위 디렉터리 권한은 확인하지 않고 파일 권한만 계속 들여다보는 것.

## 막혔을 때 다음 체크
- 권한 문제는 해결됐는데 이번엔 `Exec format error`가 뜬다면 → REV-0089 ELF 헤더 읽는 법으로 아키텍처/클래스 필드 확인.
- Docker 컨테이너 안에서만 실행/디버깅 권한 문제가 난다면 → REV-0715 Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때 (예정).
- 공유 라이브러리 자체를 못 찾는 오류라면 → REV-0706 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때.

## 미니 예제
```bash
$ ls -l chall
-rw-r--r-- 1 user user 16800 Sep  9 10:00 chall
$ ./chall
bash: ./chall: Permission denied
$ chmod +x chall
$ ls -l chall
-rwxr-xr-x 1 user user 16800 Sep  9 10:00 chall
$ ./chall
Hello, reversing!
```
실행 비트가 없던 첫 번째 시도는 실패했고, `chmod +x`로 `-rwxr-xr-x`가 된 뒤에는 정상 실행됐다. 이 예제처럼 `chmod +x` 한 번으로 해결되지 않는다면 마운트 옵션이나 디렉터리 권한 쪽을 봐야 한다.

## 관련 글
- REV-0089 — ELF 헤더 읽는 법
- REV-0706 — 공유 라이브러리를 못 찾아서 error while loading shared libraries가 뜰 때
- REV-0715 — Docker 컨테이너 안에서 gdb가 ptrace 권한 오류를 낼 때 (예정)

## 출처/검증
- 실행 비트(`x`)와 디렉터리 통과 권한(`x`)의 의미: POSIX 파일 권한 모델 및 Linux `chmod(1)`/`namei(1)` 공식 매뉴얼 기준.
- `noexec` 마운트 옵션이 실행 비트와 무관하게 실행을 차단하는 동작: Linux `mount(8)` 공식 매뉴얼 기준.
- SELinux/AppArmor 거부 로그가 `dmesg`에 `avc: denied`/`apparmor="DENIED"` 형식으로 남는 점: 각 배포판(Ubuntu, RHEL 계열) 공식 문서 및 커널 audit 로그 형식 기준 (2026-09-09 검증).
