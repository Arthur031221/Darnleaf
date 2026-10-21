<p align="center"><img src="src/darnleaf/web/logo.svg" width="72" alt="Darnleaf"></p>

<h1 align="center">Darnleaf</h1>

<p align="center"><b>Remplacez les pages abîmées d'un PDF numérisé par de nouvelles numérisations. Appariement, vérification, export. Rien ne quitte votre ordinateur.</b></p>

<p align="center"><img src="assets/demo.gif" width="860" alt="Darnleaf demo"></p>

[English](README.md) · [繁體中文](README.zh-TW.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Español](README.es.md) · [Français](README.fr.md) · [Deutsch](README.de.md) · [Português (Brasil)](README.pt-BR.md)

Vous avez un vieux PDF numérisé dont quelques pages sont abîmées, et de nouvelles numérisations de ces pages dans le désordre. Darnleaf propose la page que chaque nouvelle numérisation remplace, vous montre les preuves, puis écrit un PDF réparé et un reçu JSON de chaque changement.

- **Ce n'est pas une réparation automatique.** Chaque correspondance est notée Sûre, À vérifier ou Aucune correspondance. L'export reste verrouillé tant que vous n'avez pas confirmé chaque À vérifier, et les pages blanches sont toujours À vérifier, tout comme celles dont le deuxième candidat obtient un score proche.
- **Ce n'est pas une réécriture.** Les pages que vous n'avez pas touchées sont les objets de page d'origine, enregistrés sans nouveau rendu. Le fichier d'origine n'est jamais modifié.
- **Ce n'est pas un service.** Un petit serveur sur 127.0.0.1, sans compte, sans envoi de fichiers, sans télémétrie. La page ne charge aucune police ni aucun script distant.

## Essayer

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf serve
```

Cliquez sur **Essayer l'exemple fourni** pour parcourir tout le flux avec un livret synthétique de 40 pages, ou déposez vos propres fichiers. La [démo en rediffusion](https://arthur031221.github.io/Darnleaf/) rejoue dans le navigateur une exécution réelle de cet exemple. Elle n'accepte pas de fichiers. Avec `darnleaf serve original.pdf rescans/*.jpg`, les fichiers sont chargés et la recherche de correspondances démarre seule.

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

`apply` n'a utilisé que les trois correspondances Sûres. Les À vérifier attendent dans l'écran de vérification, ou dans `--assign FILE=PAGE`.

## Mesures

Mesuré sur des livrets synthétiques faits à partir d'un texte du domaine public (*Orgueil et Préjugés*) : 90 nouvelles numérisations sur dix graines réservées (101 à 110). Les pages reçoivent une tache de café, un pli et une bavure. Les nouvelles numérisations reçoivent inclinaison, bruit, flou et quarts de tour aléatoires. Les seuils n'ont été réglés que sur les graines 1 à 3. Pour reproduire : `python scripts/benchmark.py --seeds 101-110`.

| Type de page | Numérisations | Sûre | À vérifier | Aucune | Sûre à tort | Bonne réponse listée |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Texte | 43 | 42 | 1 | 0 | 0 | 43 |
| Figure | 3 | 3 | 0 | 0 | 0 | 3 |
| Formulaire répété | 24 | 0 | 24 | 0 | 0 | 24 |
| Page blanche | 10 | 0 | 9 | 1 | 0 | 9 |
| Absente du livret | 10 | 0 | 0 | 10 | 0 | 10 |
| **Toutes** | **90** | **45** | **34** | **11** | **0** | **89 / 90** |

Sur 45 correspondances Sûres, aucune n'était fausse. Avec seulement 45 essais, le vrai taux d'erreur pourrait encore atteindre environ 6,7 % (règle de trois, confiance de 95 %). La première suggestion était juste (ou à juste titre Aucune correspondance) pour 95,6 % des numérisations.

Lisez ces chiffres comme une borne supérieure. L'original et la nouvelle numérisation viennent du même bitmap propre, donc ils concordent mieux qu'une vraie numérisation à plat d'une page usée. Sur des documents réels, attendez-vous à plus de À vérifier et d'Aucune correspondance. De plus, les 45 correspondances Sûres sont toutes des pages de texte ou de figures au contenu distinct, et les formulaires et pages blanches sont les mêmes pages fixes pour toutes les graines.

Les photos prises au téléphone sont rarement parallèles à la page. Avec `--tilt 0.04`, chaque nouvelle numérisation des mêmes dix graines est déformée comme si elle avait été photographiée en biais, chaque coin étant déplacé jusqu'à 4 % de la page. La version 0.4.0 donne 46 Sûre et aucune erreur, et la première suggestion est bonne (ou correctement Aucune) pour 77 sur 90. La 0.3.0 donnait 31 Sûre et 46 sur 90, car elle ne modélisait qu'une numérisation à plat. Les pages blanches passent à Aucune en biais, parce que le bord de la table ressemble à de l'encre : placez-les à la main. L'essai est dans `docs/benchmark-tilted.json`.

## Installation

```sh
pipx install git+https://github.com/Arthur031221/Darnleaf
darnleaf --version
```

Python 3.10 ou plus récent. Pas encore sur PyPI. La suite complète tourne sous Linux. Les tests de la CLI, de l'export et des images tournent aussi en CI sous macOS et Windows, mais le moteur de correspondance n'a été éprouvé que sous Linux.

## Limites

- Refuse les PDF chiffrés, les PDF signés numériquement, les PDF avec champs de formulaire et les pages dont `Rotate` n'est pas un multiple de 90.
- Jusqu'à 200 pages dans l'original, 40 nouvelles numérisations, 400 Mo pour l'original et 60 Mo par numérisation.
- Les pages avec annotations ne sont pas remplacées, sauf si vous acceptez de perdre les annotations.
- Deux pages presque identiques ne se distinguent pas par l'image, elles passent donc en À vérifier quand le deuxième candidat obtient un score proche. Une page blanche ne donne aucun indice et reste toujours À vérifier.
- L'interface est traduite en neuf langues, y compris la raison affichée sous chaque correspondance. La sortie de `darnleaf match` est en anglais. Les photos HEIC de l'iPhone demandent `pip install "darnleaf[heic]"`.

Plus de détails dans la documentation en anglais : [docs/usage.md](docs/usage.md) et [docs/how-it-works.md](docs/how-it-works.md). Pour contribuer, voir [CONTRIBUTING.md](CONTRIBUTING.md). Licence MIT, voir [LICENSE](LICENSE).

Assisted by Claude/Codex.
