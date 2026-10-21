<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>스캔한 PDF에서 손상된 페이지를 새로 다시 스캔한 페이지로 바꿉니다. 일치, 검토, 내보내기까지 모두 내 컴퓨터 안에서 끝납니다.</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

오래된 스캔 PDF에 망가진 페이지가 몇 장 있고, 그 페이지를 다시 스캔한 파일이 순서 없이 있습니다. Darnleaf는 각 재스캔이 어느 페이지를 대신할지 제안하고 근거를 보여 주며, 수정된 PDF와 모든 변경을 기록한 JSON 영수증을 만듭니다.

- **자동 수리가 아닙니다.** 모든 일치는 '확실', '확인 필요', '일치 없음' 중 하나로 표시됩니다. '확인 필요'를 모두 확정해야 내보낼 수 있고, 빈 페이지는 항상 '확인 필요'이고, 2위 점수가 1위에 가까운 경우도 마찬가지입니다.
- **파일을 다시 쓰지 않습니다.** 건드리지 않은 페이지는 원래 페이지 객체 그대로 저장되며 다시 렌더링하지 않습니다. 원본 파일에는 절대 쓰지 않습니다.
- **서비스가 아닙니다.** 127.0.0.1에서 도는 작은 서버일 뿐입니다. 계정도, 업로드도, 원격 측정도 없고 페이지는 원격 글꼴이나 스크립트도 불러오지 않습니다.

## 써 보기

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

'기본 제공 샘플 써 보기'를 누르면 합성한 40쪽 책자로 전체 흐름을 볼 수 있고, 직접 파일을 넣을 수도 있습니다. [리플레이 데모](https://arthur031221.github.io/Darnleaf/)는 그 샘플의 실제 실행 기록을 브라우저에서 재생하며, 파일은 받지 않습니다. `darnleaf serve original.pdf rescans/*.jpg`를 쓰면 파일을 불러오고 일치 찾기까지 바로 시작합니다.

```console
$ darnleaf sample job
wrote job/original.pdf, 7 rescans and truth.json
$ darnleaf match job/original.pdf job/rescans/*.jpg
rescan                        page  status  reason
rescan-01.jpg                   33  check   page 35 scores almost as high (margin 0.02)
rescan-02.jpg                   11  clear   205 consistent features, margin 0.60
rescan-03.jpg                    2  check   blank pages carry no evidence: confirm the position yourself
rescan-04.jpg                   22  clear   428 consistent features, margin 0.94
rescan-05.jpg                   31  check   page 32 scores almost as high (margin 0.05)
rescan-06.jpg                   27  clear   230 consistent features, margin 0.78
rescan-07.jpg                    -  none    no original page shares enough features or text with this rescan
$ darnleaf apply job/original.pdf job/rescans/*.jpg -o job/repaired.pdf
replaced 3 of 40 pages -> job/repaired.pdf
receipt -> job/repaired.receipt.json
```

`apply`는 '확실' 세 건만 사용했습니다. '확인 필요'는 검토 화면에서 확정하거나 `--assign FILE=PAGE`로 지정합니다.

## 벤치마크

공개 도메인 문장(『오만과 편견』)으로 만든 합성 책자에서 측정했습니다. 조정에 쓰지 않은 시드 10개(101~110), 재스캔 90장입니다. 페이지에는 커피 얼룩, 접힌 자국, 번짐을 넣었고 재스캔에는 기울기, 노이즈, 흐림, 무작위 90도 회전을 넣었습니다. 임계값은 시드 1~3에서만 조정했습니다. 재현은 `python scripts/benchmark.py --seeds 101-110`입니다.

| 페이지 종류 | 재스캔 | 확실 | 확인 필요 | 일치 없음 | 잘못된 '확실' | 정답이 후보에 있음 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 본문 | 43 | 42 | 1 | 0 | 0 | 43 |
| 그림 | 3 | 3 | 0 | 0 | 0 | 3 |
| 반복되는 서식 | 24 | 0 | 24 | 0 | 0 | 24 |
| 빈 페이지 | 10 | 0 | 9 | 1 | 0 | 9 |
| 책자에 없음 | 10 | 0 | 0 | 10 | 0 | 10 |
| **전체** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

'확실' 45건 중 틀린 것은 0건입니다. 다만 시도가 45번뿐이라 실제 오류율은 최대 약 6.7%일 수 있습니다(3의 법칙, 신뢰도 95%). 1순위 제안이 맞았거나 '일치 없음'으로 올바르게 나온 비율은 95.6%입니다.

이 숫자는 상한으로 보세요. 원본과 재스캔이 같은 깨끗한 비트맵에서 나왔기 때문에, 실제 평판 스캐너로 닳은 종이를 다시 스캔할 때보다 더 잘 맞습니다. 실제 문서에서는 '확인 필요'와 '일치 없음'이 더 많이 나올 가능성이 큽니다. 또한 '확실' 45건은 모두 내용이 서로 다른 글 페이지와 그림 페이지이고, 양식과 빈 페이지는 모든 시드에서 같은 고정 페이지입니다.

## 설치

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 이상이 필요합니다. 지금까지 Linux에서만 테스트했고 PyPI에는 아직 없습니다.

## 제한

- 암호화된 PDF, 전자 서명이 있는 PDF, 양식 필드가 있는 PDF, `Rotate`가 90의 배수가 아닌 페이지는 거부합니다.
- 원본은 최대 200쪽, 재스캔은 최대 40장, 원본 파일은 400 MB, 재스캔은 장당 60 MB까지입니다.
- 주석이 있는 페이지는 주석을 버려도 된다고 지정하지 않으면 바꾸지 않습니다.
- 거의 같은 두 페이지는 이미지만으로 구분할 수 없어서 2위 점수가 가까우면 '확인 필요'가 됩니다. 빈 페이지에는 단서가 없어 항상 '확인 필요'입니다.
- 화면은 9개 언어로 번역되어 있고 각 일치 아래의 이유 문장도 같습니다. `darnleaf match` 출력은 영어입니다. iPhone의 HEIC 사진은 `pip install "darnleaf[heic]"`가 필요합니다.

자세한 내용은 영어 문서 [docs/usage.md](docs/usage.md)와 [docs/how-it-works.md](docs/how-it-works.md)를 보세요. 기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md), 라이선스는 MIT이며 [LICENSE](LICENSE)에 있습니다.

Assisted by Claude/Codex.
