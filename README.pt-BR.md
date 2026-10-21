<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>Troque as páginas danificadas de um PDF digitalizado por novas digitalizações. Combinar, revisar, exportar. Nada sai do seu computador.</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

Você tem um PDF digitalizado antigo com algumas páginas estragadas e digitalizações novas dessas páginas, sem ordem nenhuma. O Darnleaf sugere qual página cada nova digitalização substitui, mostra as evidências e grava um PDF reparado e um recibo JSON de cada alteração.

- **Não é um reparo automático.** Cada correspondência é marcada como Segura, Verificar ou Sem correspondência. A exportação fica bloqueada até você confirmar cada Verificar, e páginas em branco são sempre Verificar, assim como qualquer página cujo segundo candidato pontue perto.
- **Não reescreve o arquivo.** As páginas que você não tocou são os objetos de página originais, salvos sem renderizar de novo. O arquivo original nunca é modificado.
- **Não é um serviço.** É um pequeno servidor em 127.0.0.1, sem conta, sem envio de arquivos e sem telemetria. A página não carrega fontes nem scripts remotos.

## Experimente

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

Clique em **Experimentar o exemplo incluído** para ver todo o fluxo com um caderno sintético de 40 páginas, ou solte seus próprios arquivos. A [demonstração em replay](https://arthur031221.github.io/Darnleaf/) reproduz no navegador uma execução real desse exemplo. Ela não aceita arquivos. Com `darnleaf serve original.pdf rescans/*.jpg` os arquivos são carregados e a busca de correspondências começa sozinha.

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

O `apply` usou apenas as três correspondências Seguras. As Verificar esperam na tela de revisão ou em `--assign FILE=PAGE`.

## Medições

Medido em cadernos sintéticos feitos com texto de domínio público (*Orgulho e Preconceito*): 90 novas digitalizações em dez sementes reservadas (101 a 110). As páginas recebem mancha de café, dobra e borrão. As novas digitalizações recebem inclinação, ruído, desfoque e giros de um quarto de volta aleatórios. Os limiares foram ajustados só com as sementes 1 a 3. Para reproduzir: `python scripts/benchmark.py --seeds 101-110`.

| Tipo de página | Digitalizações | Segura | Verificar | Sem correspondência | Segura errada | Resposta certa listada |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Texto | 43 | 42 | 1 | 0 | 0 | 43 |
| Figura | 3 | 3 | 0 | 0 | 0 | 3 |
| Formulário repetido | 24 | 0 | 24 | 0 | 0 | 24 |
| Página em branco | 10 | 0 | 9 | 1 | 0 | 9 |
| Fora do caderno | 10 | 0 | 0 | 10 | 0 | 10 |
| **Todas** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

De 45 correspondências Seguras, nenhuma estava errada. Com apenas 45 tentativas, a taxa real de erro ainda poderia chegar a cerca de 6,7% (regra de três, 95% de confiança). A primeira sugestão estava certa (ou corretamente Sem correspondência) em 95,6% das digitalizações.

Leia como um limite superior. O original e a nova digitalização saem do mesmo bitmap limpo, então combinam melhor do que uma digitalização real em scanner de mesa de uma página gasta. Em documentos reais, espere mais Verificar e Sem correspondência. Além disso, as 45 correspondências Seguras são todas páginas de texto e figuras com conteúdo distinto, e os formulários e as páginas em branco são as mesmas páginas fixas em todas as sementes.

## Instalação

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 ou mais recente. Testado só no Linux até agora e ainda não está no PyPI.

## Limites

- Recusa PDFs criptografados, PDFs com assinatura digital, PDFs com campos de formulário e páginas com `Rotate` que não seja múltiplo de 90.
- Até 200 páginas no original, 40 novas digitalizações, 400 MB para o original e 60 MB por digitalização.
- Páginas com anotações não são substituídas, a menos que você permita descartar as anotações.
- Duas páginas quase idênticas não se distinguem só pela imagem, então viram Verificar quando o segundo candidato pontua perto. Uma página em branco não traz evidência e é sempre Verificar.
- A interface está traduzida em nove idiomas, inclusive o motivo sob cada correspondência. A saída de `darnleaf match` está em inglês. Fotos HEIC do iPhone precisam de `pip install "darnleaf[heic]"`.

Mais detalhes na documentação em inglês: [docs/usage.md](docs/usage.md) e [docs/how-it-works.md](docs/how-it-works.md). Para contribuir, veja [CONTRIBUTING.md](CONTRIBUTING.md). Licença MIT, veja [LICENSE](LICENSE).

Assisted by Claude/Codex.
