---
id: REV-0983
title: "Frida 서버 연결이 안 될 때(attach 실패)"
slug: "rev-0983-frida-attach-fails"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [Frida]
keywords: ["Frida attach 실패", "unable to connect to remote frida-server", "frida-server 버전 불일치", "frida.ProcessNotFoundError", "frida-server 권한 오류"]
aliases: ["Frida 연결 안됨", "frida attach 오류", "frida-server 실행 안됨", "frida 버전 안맞음"]
symptom_keywords: ["Failed to spawn 메시지가 뜸", "unable to connect to remote frida-server", "frida-server 실행이 안됨", "frida.ProcessNotFoundError가 뜸"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
Frida attach/spawn이 실패하는 원인은 거의 항상 PC의 `frida` 클라이언트 버전과 기기의 `frida-server` 버전이 서로 다르거나, `frida-server`가 애초에 실행되고 있지 않거나(권한 부족 포함), 대상 프로세스 이름/PID를 잘못 지정했기 때문이다.

## 언제 검색해야 하나
- `frida -U -f com.example.app -l script.js`를 실행했는데 `Failed to spawn: unable to connect to remote frida-server`가 뜰 때
- `frida-ps -U`부터 아무 프로세스 목록도 안 뜰 때
- `frida.ProcessNotFoundError`가 발생할 때
- `frida-server`를 실행했는데 곧바로 종료되거나 권한 오류가 날 때

## 핵심 개념
Frida는 PC의 `frida` 클라이언트와 기기 안에서 실행되는 `frida-server` 두 부분이 정확히 같은 버전이어야 정상 통신한다. 버전이 하나라도 다르면 프로토콜 불일치로 연결 자체가 거부된다. 이 문제는 Frida를 pip으로 업데이트했는데 기기의 `frida-server`는 예전 버전 그대로 두거나, 반대로 `frida-server`만 새로 받아 넣었을 때 흔히 생긴다.

또한 `frida-server`는 대상 프로세스에 코드를 주입하기 위해 강한 권한(대부분 root)이 필요하다. 루팅되지 않은 실기기에서 일반 사용자 권한으로 `frida-server`를 실행하면 조용히 실패하거나 접근 거부 오류가 난다. 마지막으로, attach 대상 프로세스 이름이나 PID를 잘못 지정하면(오탈자, 아직 실행 안 된 상태) `ProcessNotFoundError`가 발생한다.

## 화면/코드에서 보이는 징후
- `Failed to spawn: unable to connect to remote frida-server: closed`
- `frida-ps -U`가 아무 목록도 출력하지 않고 오류로 끝난다.
- 기기에서 `./frida-server`를 실행했더니 `Permission denied`가 뜬다.
- `frida.ProcessNotFoundError: unable to find process with name 'com.example.app'`

## 가장 먼저 할 것
`frida --version`(PC)과 기기에 올려둔 `frida-server`의 버전을 나란히 비교한다. 둘이 다르면 다른 원인을 볼 필요 없이 이것부터 맞춘다.

## 단계별 절차
1. `frida --version`으로 PC 클라이언트 버전을 확인한다.
2. 정확히 같은 버전의 `frida-server`를 기기 아키텍처(`arm64`, `arm` 등)에 맞게 공식 GitHub 릴리스에서 받는다.
3. 기존에 올려둔 `frida-server`를 지우고 새 버전을 `/data/local/tmp/`에 다시 push한다.
4. `adb shell chmod 755 /data/local/tmp/frida-server`로 실행 권한을 부여한다.
5. 루팅된 기기/에뮬레이터에서 `adb shell "su -c /data/local/tmp/frida-server &"`로 root 권한으로 백그라운드 실행한다.
6. `frida-ps -U`로 프로세스 목록이 정상 출력되는지 확인한다.
7. 여전히 attach가 안 되면 대상 프로세스 이름을 `frida-ps -U`에서 나온 실제 이름과 정확히 대조한다.
8. 방화벽/USB 포트 포워딩 문제가 의심되면 `adb forward` 설정을 확인한다(원격 연결을 쓰는 경우).

## 명령어/단축키
```bash
frida --version                                   # 클라이언트 버전 확인
adb push frida-server-X.Y.Z-android-arm64 /data/local/tmp/frida-server
adb shell chmod 755 /data/local/tmp/frida-server
adb shell "su -c /data/local/tmp/frida-server &"   # root로 백그라운드 실행
frida-ps -U                                        # 연결 확인 겸 프로세스 목록
frida -U -f com.example.app -l script.js --no-pause
```

## 출력 해석
- `frida-ps -U`가 프로세스 목록을 정상 출력하면 클라이언트-서버 연결 자체는 문제없는 것이다 — 이후 오류는 대상 프로세스 지정 문제일 가능성이 크다.
- `unable to connect to remote frida-server: closed`는 버전 불일치이거나 `frida-server`가 실제로 실행되고 있지 않다는 신호다.
- `Permission denied`는 root 권한 없이 `frida-server`를 실행하려 했다는 뜻이다.
- `ProcessNotFoundError`는 이름/PID 오타이거나 attach 시점에 그 프로세스가 아직 안 떠 있다는 뜻이며, spawn 방식(`-f`)으로 바꾸면 해결되는 경우가 많다.

## 흔한 실수
- PC의 `frida`를 pip으로 최신화했는데 기기의 `frida-server`는 예전 버전 그대로 두는 것.
- 루팅되지 않은 실기기에서 `frida-server`를 그냥 실행하려는 것 — 에뮬레이터나 루팅 기기에서 먼저 연습해야 한다.
- attach 대상 이름에 패키지명이 아니라 앱 표시 이름(런처 아이콘 이름)을 쓰는 것 — `frida-ps -U`에 나온 정확한 프로세스명을 써야 한다.
- `frida-server`를 백그라운드로 안 띄우고 포그라운드로 실행해서 같은 shell 세션이 막히는 것.
- 여러 기기/에뮬레이터가 동시에 연결된 상태에서 `-U` 대신 특정 기기를 지정하지 않아 엉뚱한 기기에 연결을 시도하는 것.

## 막혔을 때 다음 체크
- adb 연결 자체가 안 된다면 → REV-0982 adb 기기 연결이 안 될 때(device not found)
- 연결은 됐는데 후킹 스크립트 작성법이 궁금하면 → REV-0256 Frida로 함수 관찰하는 기본 흐름
- 네이티브 함수 오프셋을 못 찾겠으면 → REV-0254 Native Library lib*.so가 있을 때

## 미니 예제
`frida -U -f com.example.ctf -l hook.js --no-pause`를 실행했더니 `Failed to spawn: unable to connect to remote frida-server: closed`가 떴다. `frida --version`을 확인하니 `16.4.1`이었는데, 기기에 올려둔 `frida-server`는 예전에 받아둔 `16.1.0`이었다. 공식 GitHub 릴리스에서 `frida-server-16.4.1-android-arm64`를 새로 받아 `/data/local/tmp/frida-server`로 교체하고 `chmod 755` 후 `su -c` 로 재실행하니 `frida-ps -U`가 정상적으로 프로세스 목록을 출력했고, 이후 spawn 명령도 정상 동작했다.

## 관련 글
- REV-0256 — Frida로 함수 관찰하는 기본 흐름
- REV-0982 — adb 기기 연결이 안 될 때(device not found)
- REV-0254 — Native Library lib*.so가 있을 때

## 출처/검증
- frida-server와 클라이언트의 버전 일치 요구사항 및 root 권한 요건은 Frida 공식 문서(frida.re, "Getting started with Frida on Android")를 기준으로 정리했다(2026-09-09 확인).
- attach/spawn 오류 메시지(`ProcessNotFoundError`, `Failed to spawn`)는 Frida 공식 GitHub 저장소(frida/frida) 이슈 사례 기준.
