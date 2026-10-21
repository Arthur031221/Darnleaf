<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>用新的重扫页面，替换扫描版 PDF 中损坏的页面。匹配、检查、导出，全程不离开你的电脑。</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

手上有一份旧的扫描版 PDF，其中几页已经损坏，另外有这些页面的新扫描件，顺序是乱的。Darnleaf 会建议每张重扫件该替换哪一页，让你看到匹配依据，最后输出修复后的 PDF，以及记录每项改动的 JSON 回执。

- **不是自动修复。** 每条匹配都标为「明确」「需检查」或「无匹配」。所有「需检查」都要由你确认后才能导出，空白页一律是「需检查」，第二高分和最高分很接近的也是。
- **不是重写整个文件。** 没动过的页面仍是原来的页面对象，不会重新渲染。原始文件永远不会被写入。
- **不是在线服务。** 只是在 127.0.0.1 上运行的小型服务器，无需账号，不上传，不回传任何数据，页面也不加载远程字体或脚本。

## 试一试

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

点「试用内置示例」，就能在一份合成的 40 页小册子上走完整个流程，也可以放入你自己的文件。[回放演示](https://arthur031221.github.io/Darnleaf/)会在浏览器里回放该示例的一次真实运行，不接收文件。

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

`apply` 只用了三条「明确」的匹配，其余「需检查」的留给你在检查界面确认，或用 `--assign FILE=PAGE` 指定。

## 基准测试

数据是用公共领域文本（《傲慢与偏见》）合成的小册子：十组留出种子（101 到 110），共 90 张重扫件。页面被加上咖啡渍、折痕和涂抹，重扫件则带有倾斜、噪点、模糊和随机的四分之一转。阈值只在种子 1 到 3 上调整。复现方式：`python scripts/benchmark.py --seeds 101-110`。

| 页面类型 | 重扫件数 | 明确 | 需检查 | 无匹配 | 明确但错误 | 正确答案已列出 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 文字页 | 43 | 42 | 1 | 0 | 0 | 43 |
| 图表页 | 3 | 3 | 0 | 0 | 0 | 3 |
| 重复的表单 | 24 | 0 | 24 | 0 | 0 | 24 |
| 空白页 | 10 | 0 | 9 | 1 | 0 | 9 |
| 不在小册子里 | 10 | 0 | 0 | 10 | 0 | 10 |
| **全部** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

45 条「明确」匹配中没有一条是错的。但只有 45 次试验，真实的错误率仍可能高达约 6.7%（三法则，95% 置信度）。排名第一的建议正确（或正确判为无匹配）的比例是 95.6%。

请把这些数字当作上限。原稿和重扫件取自同一张干净的位图，吻合程度比真实平板扫描仪重扫一张磨损的纸更高。真实文档很可能出现更多「需检查」和「无匹配」。另外，45 条「明确」匹配全是内容各不相同的文字页和图表页，表单和空白页在各组种子中都是同样固定的页面。

## 安装

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

需要 Python 3.10 或更高版本。目前只在 Linux 上测试过，也还没有发布到 PyPI。

## 限制

- 拒绝加密的 PDF、带数字签名的 PDF、含表单域的 PDF，以及 `Rotate` 不是 90 的倍数的页面。
- 原稿最多 200 页，重扫件最多 40 张，原稿上限 400 MB，每张重扫件上限 60 MB。
- 带批注的页面不会被替换，除非你同意丢弃批注。
- 两个几乎相同的页面无法只靠图像区分，所以第二高分很接近时会标为「需检查」。空白页没有任何线索，一律是「需检查」。
- 界面有九种语言，但匹配引擎给出的原因文字只有英文。

更多内容见英文文档：[docs/usage.md](docs/usage.md) 和 [docs/how-it-works.md](docs/how-it-works.md)。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)。MIT 许可，见 [LICENSE](LICENSE)。

Assisted by Claude/Codex.
