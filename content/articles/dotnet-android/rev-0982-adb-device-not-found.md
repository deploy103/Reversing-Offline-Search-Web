---
id: REV-0982
title: "adb 기기 연결이 안 될 때(device not found)"
slug: "rev-0982-adb-device-not-found"
category: "dotnet-android"
difficulty: "basic"
platform: [android]
architecture: [ARM, ARM64]
format: [APK]
tools: [adb]
keywords: ["adb devices 빈 목록", "adb no devices/emulators found", "adb unauthorized", "adb offline", "USB 디버깅 안됨"]
aliases: ["adb 기기 인식 안됨", "adb device not found", "adb 연결 안됨", "adb unauthorized 해결"]
symptom_keywords: ["adb devices에 아무것도 안 뜸", "no devices/emulators found 메시지", "unauthorized 상태로 멈춤", "offline 상태로 안 바뀜"]
source_ids: ["SRC-GENERAL-REVERSING"]
last_verified: "2026-09-09"
---

## 한 줄 요약
`adb devices`에 기기가 안 뜨거나 `unauthorized`/`offline` 상태로 멈춰 있다면, 원인은 대부분 USB 디버깅이 꺼져 있거나, 기기 화면의 RSA 키 승인 팝업을 놓쳤거나, PC의 `adb` 서버가 꼬여서 재시작이 필요하거나, USB 드라이버/케이블 문제(Windows에서 특히 흔함) 중 하나다.

## 언제 검색해야 하나
- `adb devices`를 쳤는데 `List of devices attached` 아래 아무 줄도 안 뜰 때
- 기기가 뜨긴 하는데 상태가 `unauthorized`나 `offline`로 계속 남아 있을 때
- 에뮬레이터는 잡히는데 실제 기기만 안 잡힐 때(또는 그 반대)
- 어제까지 잘 되던 연결이 갑자기 안 될 때

## 핵심 개념
`adb`는 PC의 `adb` 클라이언트 → PC에서 백그라운드로 도는 `adb server` → 기기 안의 `adbd` 데몬, 이렇게 세 구성 요소가 USB(또는 TCP/Wi-Fi)로 연결되어야 동작한다. 이 경로 어디서든 끊기면 기기가 안 잡힌다.

가장 흔한 원인 네 가지는 다음과 같다.
- **USB 디버깅이 꺼져 있음**: 안드로이드 기기는 설정에서 개발자 옵션을 활성화하고 그 안의 "USB 디버깅"을 켜야 `adbd`가 USB 연결을 받아들인다.
- **RSA 키 승인 미확인**: 처음 PC에 연결하면 기기 화면에 "이 컴퓨터의 USB 디버깅을 허용하시겠습니까?"라는 팝업이 뜨는데, 이를 놓치거나 거부하면 `unauthorized` 상태로 남는다.
- **`adb server` 상태 꼬임**: 여러 버전의 adb를 오가며 설치했거나, 이전 세션이 비정상 종료된 경우 PC 쪽 서버 프로세스가 꼬여서 새 기기를 못 잡을 수 있다.
- **USB 드라이버/케이블 문제(주로 Windows)**: 데이터 전송을 지원하지 않는 충전 전용 케이블이거나, 기기 제조사 전용 USB 드라이버가 설치되지 않은 경우다.

## 화면/코드에서 보이는 징후
- `adb devices` 결과에 `List of devices attached`만 있고 그 아래가 비어 있다.
- 기기 시리얼 옆에 `unauthorized`라고 표시된다.
- 기기 시리얼 옆에 `offline`이라고 표시된 채 바뀌지 않는다.
- `adb: error: no devices/emulators found`라는 오류가 다른 명령(`adb install` 등) 실행 시 뜬다.

## 가장 먼저 할 것
기기 화면을 직접 확인한다. USB를 연결한 직후 "USB 디버깅을 허용하시겠습니까?" 팝업이 떠 있는지부터 본다. 이 팝업이 안 뜨거나 이미 화면 뒤로 넘어갔다면 케이블을 뽑았다 다시 꽂아 팝업을 다시 띄운다.

## 단계별 절차
1. 기기의 설정 → 개발자 옵션(빌드 번호를 7번 연속 탭하면 활성화) → "USB 디버깅"이 켜져 있는지 확인한다.
2. USB 케이블을 다시 꽂고 기기 화면의 RSA 키 승인 팝업에서 "항상 허용" 후 확인을 누른다.
3. `adb kill-server`로 PC 쪽 adb 서버를 완전히 종료한 뒤 `adb start-server`로 재시작한다.
4. 그래도 안 되면 다른 USB 케이블(데이터 전송 지원 케이블)과 다른 USB 포트로 바꿔본다.
5. Windows라면 장치 관리자에서 기기가 알 수 없는 장치나 경고 아이콘으로 뜨는지 확인하고, 제조사 전용 USB 드라이버를 설치한다.
6. 에뮬레이터라면 `adb devices`에 `emulator-5554` 형태로 별도로 잡히는지 확인하고, 실기기와 동시에 여러 개 연결됐다면 `-s <시리얼>`로 대상을 명시한다.
7. Wi-Fi(TCP) 연결을 쓰는 경우 `adb tcpip 5555` → `adb connect <IP>:5555` 순서를 다시 확인한다.

## 명령어/단축키
```bash
adb devices                          # 연결 상태 확인
adb kill-server && adb start-server   # 서버 재시작
adb devices -l                        # 더 상세한 기기 정보(모델명 등) 포함 확인
adb -s <시리얼> <명령>                 # 여러 기기 중 특정 대상 지정
adb tcpip 5555                        # Wi-Fi adb 준비(USB로 먼저 연결된 상태에서)
adb connect 192.168.0.10:5555         # Wi-Fi로 연결
```

## 출력 해석
- 목록이 아예 비어 있으면 USB 연결/드라이버/디버깅 옵션 자체를 의심해야 한다.
- `unauthorized`는 인증 자체는 진행 중이나 기기에서 아직 승인을 안 한 상태다 — 화면을 확인하라는 신호다.
- `offline`은 한 번은 연결됐지만 현재 통신이 끊긴 상태로, 보통 `adb kill-server`/`start-server` 재시작으로 해결된다.
- `no devices/emulators found`는 adb 서버 입장에서 연결된 대상이 전혀 없다는 뜻이며, 위 목록이 비어 있는 상황과 같은 근본 원인을 갖는다.

## 흔한 실수
- RSA 키 승인 팝업을 놓치고 계속 `adb devices`만 반복 실행하는 것 — 기기 화면을 먼저 봐야 한다.
- 충전 전용 케이블로 연결해놓고 왜 안 되는지 몰라 헤매는 것.
- 여러 에뮬레이터/기기가 동시에 연결된 상태에서 `-s` 옵션 없이 명령을 내려서 엉뚱한 대상에 명령이 가는 것.
- Windows에서 드라이버 문제를 의심하지 않고 adb 설정만 계속 건드리는 것.
- `adb kill-server`를 시도하지 않고 재부팅부터 하는 것 — 대부분 서버 재시작만으로 충분하다.

## 막혔을 때 다음 체크
- 기기는 잡혔는데 앱 데이터 접근이나 로그 확인이 궁금하면 → REV-0255 adb 기본 명령 치트시트
- Frida까지 붙여야 하는데 attach가 안 된다면 → REV-0983 Frida 서버 연결이 안 될 때(attach 실패)
- 재서명한 APK 설치가 실패한다면 → REV-0984 APK 재서명 후 설치가 실패할 때

## 미니 예제
`adb devices`를 실행했더니 `List of devices attached`만 뜨고 아무 기기도 안 보였다. 기기 화면을 확인해보니 화면이 잠겨 있어 팝업을 못 본 상태였다. 잠금을 풀자 "USB 디버깅을 허용하시겠습니까?" 팝업이 나타났고, "이 컴퓨터에서 항상 허용"을 체크한 뒤 확인을 눌렀다. 이후 `adb devices`를 다시 실행하니 다음과 같이 정상적으로 잡혔다.

```
$ adb devices
List of devices attached
R58N1234ABC     device
```

## 관련 글
- REV-0255 — adb 기본 명령 치트시트
- REV-0983 — Frida 서버 연결이 안 될 때(attach 실패)
- REV-0984 — APK 재서명 후 설치가 실패할 때

## 출처/검증
- `adb devices` 상태(`device`/`unauthorized`/`offline`) 및 서버 구조(`adb server`/`adbd`)는 Android 공식 개발자 문서("Android Debug Bridge (adb)")를 기준으로 정리했다(2026-09-09 확인).
- USB 디버깅 활성화 및 RSA 키 승인 절차는 Android 공식 개발자 문서("Configure on-device developer options")의 설명과 일치한다.
