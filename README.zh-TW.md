<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>用新的重掃頁面，換掉掃描版 PDF 裡損壞的頁面。比對、檢視、匯出，全程不離開你的電腦。</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

手上有一份舊的掃描版 PDF，其中幾頁已經毀損，另外有這些頁面的新掃描檔，順序是亂的。Darnleaf 會建議每張重掃檔該取代哪一頁，讓你看到比對依據，最後輸出修復後的 PDF，以及記錄每項變更的 JSON 收據。

- **不是自動修復。** 每筆比對都標成「明確」「需檢查」或「無對應」。所有「需檢查」都由你確認後才能匯出，空白頁一律是「需檢查」，第二高分和最高分很接近的也是。
- **不是重寫整份檔案。** 沒動到的頁面還是原本的頁面物件，不會重新繪製。原始檔案永遠不會被寫入。
- **不是線上服務。** 只是在 127.0.0.1 跑的小型伺服器，不用帳號、不上傳、不回傳任何資料，頁面也不載入遠端字型或腳本。

## 試試看

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

按「試用內建範例」，就能在一份合成的 40 頁小冊子上走完整個流程，也可以放入你自己的檔案。[重播示範](https://arthur031221.github.io/Darnleaf/)會在瀏覽器裡重播一次該範例的真實執行結果，不接受檔案上傳。 用 `darnleaf serve original.pdf rescans/*.jpg` 會直接載入檔案並開始比對。

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

`apply` 只用了三筆「明確」的比對，其餘「需檢查」的留給你在檢視畫面確認，或用 `--assign FILE=PAGE` 指定。

## 基準測試

資料是用公有領域文字（《傲慢與偏見》）合成的小冊子：十組保留種子（101 到 110），共 90 張重掃檔。頁面被加上咖啡漬、摺痕與塗抹，重掃檔則有傾斜、雜訊、模糊和隨機的四分之一轉。門檻只在種子 1 到 3 上調整。重現方式：`python scripts/benchmark.py --seeds 101-110`。

| 頁面類型 | 重掃檔數 | 明確 | 需檢查 | 無對應 | 明確但錯誤 | 正確答案有列出 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 文字頁 | 43 | 42 | 1 | 0 | 0 | 43 |
| 圖表頁 | 3 | 3 | 0 | 0 | 0 | 3 |
| 重複的表單 | 24 | 0 | 24 | 0 | 0 | 24 |
| 空白頁 | 10 | 0 | 9 | 1 | 0 | 9 |
| 不在小冊子裡 | 10 | 0 | 0 | 10 | 0 | 10 |
| **全部** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

45 筆「明確」比對中沒有任何一筆是錯的。但只有 45 次試驗，真實的錯誤率仍可能高到約 6.7%（三法則，95% 信賴度）。排名第一的建議正確（或正確地判為無對應）的比例是 95.6%。

請把這些數字當成上限。原稿與重掃檔取自同一張乾淨的點陣圖，吻合程度比真實平台式掃描器重掃一張磨損的紙還高。真實文件很可能出現更多「需檢查」與「無對應」。另外，45 筆「明確」比對全是內容各不相同的文字頁與圖表頁，表單與空白頁在各組種子中都是同樣固定的頁面。

## 安裝

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

需要 Python 3.10 以上。還沒有上架 PyPI。完整測試在 Linux 上執行，CLI、匯出與影像處理的測試在 CI 裡也會在 macOS 和 Windows 上執行，但比對引擎只在 Linux 上驗證過。

## 限制

- 拒絕加密的 PDF、有數位簽章的 PDF、含表單欄位的 PDF，以及 `Rotate` 不是 90 的倍數的頁面。
- 原稿最多 200 頁、重掃檔最多 40 張，原稿上限 400 MB，每張重掃檔上限 60 MB。
- 有註解的頁面不會被取代，除非你同意捨棄註解。
- 兩個幾乎相同的頁面無法只靠影像分辨，所以第二高分很接近時會標成「需檢查」。空白頁沒有任何線索，一律是「需檢查」。
- 介面有九種語言，每筆比對下方的原因文字也一樣。`darnleaf match` 的輸出是英文。iPhone 的 HEIC 照片需要 `pip install "darnleaf[heic]"`。

更多內容請見英文文件：[docs/usage.md](docs/usage.md) 與 [docs/how-it-works.md](docs/how-it-works.md)。貢獻方式請見 [CONTRIBUTING.md](CONTRIBUTING.md)。MIT 授權，見 [LICENSE](LICENSE)。

Assisted by Claude/Codex.
