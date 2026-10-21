<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>スキャンした PDF の傷んだページを、撮り直したページに置き換えます。照合、確認、書き出し。すべてあなたのコンピュータの中で完結します。</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

古いスキャン PDF のページが何枚か傷んでいて、そのページを撮り直したファイルが順不同で手元にある。そんなときに、Darnleaf はどのスキャンがどのページに当たるかを提案し、その根拠を見せ、修復した PDF と、変更内容をすべて記録した JSON レシートを書き出します。

- **全自動の修復ではありません。** 照合結果は「確実」「要確認」「一致なし」のどれかです。「要確認」をすべて確定するまで書き出せず、白紙ページは常に「要確認」で、2 位の得点が 1 位に近いページも同じです。
- **ファイルの作り直しではありません。** 触れていないページは元のページオブジェクトのまま保存され、再描画されません。元のファイルには一切書き込みません。
- **サービスではありません。** 127.0.0.1 で動く小さなサーバーだけです。アカウントも、アップロードも、テレメトリもありません。ページはリモートのフォントやスクリプトも読み込みません。

## 試してみる

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

「同梱のサンプルを試す」を押すと、合成した 40 ページの冊子で一連の流れを確かめられます。自分のファイルを入れることもできます。[リプレイデモ](https://arthur031221.github.io/Darnleaf/)では、そのサンプルを実際に動かした記録をブラウザで再生します。ファイルは受け付けません。 `darnleaf serve original.pdf rescans/*.jpg` なら、ファイルを読み込んで照合まで自動で始めます。

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

`apply` が使ったのは「確実」の 3 件だけです。「要確認」は確認画面で確定するか、`--assign FILE=PAGE` で指定します。

## ベンチマーク

パブリックドメインの文章（『高慢と偏見』）から作った合成の冊子で測定しました。未調整のシード 10 個（101 から 110）、撮り直し 90 枚です。ページにはコーヒーのしみ、折り目、かすれを加え、撮り直しには傾き、ノイズ、ぼかし、ランダムな 90 度回転を加えています。しきい値の調整はシード 1 から 3 だけで行いました。再現は `python scripts/benchmark.py --seeds 101-110` です。

| ページの種類 | 撮り直し | 確実 | 要確認 | 一致なし | 誤った「確実」 | 正解が候補にある |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 文章 | 43 | 42 | 1 | 0 | 0 | 43 |
| 図 | 3 | 3 | 0 | 0 | 0 | 3 |
| 繰り返しのフォーム | 24 | 0 | 24 | 0 | 0 | 24 |
| 白紙 | 10 | 0 | 9 | 1 | 0 | 9 |
| 冊子にないページ | 10 | 0 | 0 | 10 | 0 | 10 |
| **合計** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

「確実」45 件のうち、誤りは 0 件でした。ただし試行が 45 回しかないため、実際の誤り率は最大で約 6.7% あり得ます（3 の法則、信頼度 95%）。1 位の提案が正しかった（または正しく「一致なし」になった）のは 95.6% です。

これは上限と考えてください。元のページと撮り直しは同じきれいなビットマップから作っているため、実物のフラットベッドで傷んだ紙を撮り直した場合より一致しやすくなっています。実際の文書では「要確認」と「一致なし」が増えるでしょう。また、「確実」45 件はすべて内容の異なる文字ページと図のページで、フォームと白紙は全シードで同じ固定のページです。

スマートフォンで撮った写真は、ページと正対していることがほとんどありません。`--tilt 0.04` を付けると、同じ 10 個のシードで撮り直し全部を斜めから撮ったように歪めます（各隅を最大でページの 4% 動かします）。0.4.0 では「確実」が 46 件で誤りは 0 件、先頭の候補が正しい（または正しく「一致なし」）のは 90 件中 77 件でした。0.3.0 は平らなスキャンしか想定しておらず、「確実」は 31 件、正解は 90 件中 46 件でした。斜めから撮ると白紙ページは「一致なし」になります。机の縁が墨に見えるためで、位置は手で指定してください。結果は `docs/benchmark-tilted.json` にあります。

## インストール

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 以上が必要です。PyPI にはまだありません。テスト一式は Linux で動かしています。CLI、書き出し、画像処理のテストは CI で macOS と Windows でも動きますが、照合エンジンを確かめたのは Linux だけです。

## 制限

- 暗号化された PDF、電子署名付きの PDF、フォームフィールドのある PDF、`Rotate` が 90 の倍数でないページは受け付けません。
- 元の PDF は最大 200 ページ、撮り直しは最大 40 枚、元ファイルは 400 MB まで、撮り直しは 1 枚 60 MB までです。
- 注釈のあるページは、注釈を捨ててよいと指定しない限り置き換えません。
- ほぼ同じ 2 ページは画像だけでは区別できないため、2 位の得点が近いと「要確認」になります。白紙ページには手がかりがなく、常に「要確認」です。
- 画面は 9 言語に翻訳されており、各照合の下に出る理由も同じです。`darnleaf match` の出力は英語です。iPhone の HEIC 写真には `pip install "darnleaf[heic]"` が必要です。

詳しくは英語のドキュメント [docs/usage.md](docs/usage.md) と [docs/how-it-works.md](docs/how-it-works.md) を参照してください。参加方法は [CONTRIBUTING.md](CONTRIBUTING.md)、ライセンスは MIT で [LICENSE](LICENSE) にあります。

Assisted by Claude/Codex.
