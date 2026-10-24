# eliza-python

Un portage Python **fidèle** de l'ELIZA de Joseph Weizenbaum (1966) : pour
une même entrée et un même script, il donne la même réponse que l'original.

- Il reproduit mot pour mot la conversation publiée dans *CACM* en 1966.
- Il reproduit, en version 1965, les exécutions du code MAD-SLIP d'origine sur un
  IBM 7094 émulé (CTSS), jusqu'à l'espacement de la ponctuation et au « = DIT ».
- Il rejoue onze conversations historiques (1965-1978), soit 278 échanges.
- Il donne les mêmes réponses que la reconstruction C++ d'Anthony Hay (`eliza.cpp`), qui sert d'oracle aux tests.
- Il n'utilise que la bibliothèque standard de Python ≥ 3.9, et fonctionne sous Pyodide.

## Utilisation

```bash
python -m eliza                       # DOCTOR, script de mars 1965 (domaine public)
python -m eliza --lang fr             # le même DOCTOR, traduit en français
python -m eliza --lang auto           # suit la langue de chaque phrase (anglais / français)
python -m eliza --version 1965        # le programme du listing de 1965, tel quel
python -m eliza mon_script.txt --lang fr
```

Ligne vide pour quitter. `*` seul affiche la façon dont la dernière réponse a été construite.

## Deux versions historiques

- **`1966`** (par défaut) : le programme décrit dans l'article de *CACM*. Il gère une pile
  de mots-clés, `NEWKEY`, `PRE` et les liens `=MOT`.
- **`1965`** : le programme du listing retrouvé au MIT. Un seul mot-clé est retenu, il n'y a
  ni `NEWKEY` ni `PRE`, et un lien placé dans une réponse est imprimé tel quel
  (« = DIT »). Les mots sont comparés sur leurs 6 premiers caractères, et la ponctuation est
  imprimée détachée. Ce mode est validé contre l'exécution du code d'origine sur CTSS.

## ELIZA apprend en cours de conversation

C'était prévu dès 1965 (d'où le nom d'ELIZA), puis perdu dans tous les clones :

- **`* MOT ((motif) (réponse) ...)`** ajoute une règle. Exemple :
  `* HI ((HI 0) (HELLO FROM 2))`, puis « hi freddy » donne « HELLO FROM FREDDY ».
- **`+`** ouvre l'éditeur, qui répond `PLEASE INSTRUCT ME` :
  - `TYPE MOT` affiche une règle ;
  - `SUBST MOT (ancienne) (nouvelle)` remplace une réponse ;
  - `APPEND MOT (existante) (nouvelle)` ajoute une réponse ;
  - `ADD MOT ((motif) (réponse))` ajoute une décomposition ;
  - `RANK MOT n` change le rang d'un mot-clé ;
  - `DISPLA` affiche tout le script ;
  - `START` revient à la conversation.
- **Sauvegarde** : en fin de séance, le script modifié peut être enregistré (`Eliza.script_text()`).

```python
from eliza import doctor
eliza = doctor()                                # ou doctor("fr"), doctor("auto")
print(eliza.hello())
print(eliza.response("Men are all alike."))   # DID YOU THINK THEY MIGHT NOT BE ALL ALIKE
```

## Scripts

Le paquet n'embarque que des scripts du domaine public :
- `doctor` : TAPE 100, retrouvé avec le code au MIT ;
- `doctor-fr` : sa traduction française, écrite pour ce projet (CC0) ;
- deux machines de Turing d'Anthony Hay.

En mode `auto`, chaque phrase est envoyée au DOCTOR de sa langue. La langue
est reconnue par les mots fréquents, les mots-clés du script et les lettres
accentuées ; sans indice, la conversation reste dans la langue courante.

Le DOCTOR de l'article de 1966 et sa traduction française restent
utilisables, mais ne sont pas fournis (© ACM) :

```bash
python tools/references.py fetch
python -m eliza references/doctor_1966_cacm.txt
python -m eliza references/doctor_fr_jeu_de_paume.txt --lang fr
```

## Tests

```bash
python tools/references.py oracle     # références + compilation de eliza.cpp (g++)
python -m pytest
```

### Sous Pyodide (WebAssembly)

La même suite de tests tourne dans Pyodide 314.0.7 (Python 3.14) sous Node.js.
Pyodide ne peut pas lancer l'oracle C++ : les réponses attendues sont donc
enregistrées au préalable sur la machine hôte.

```bash
python tools/references.py golden     # enregistre references/golden.json
cd tools/pyodide && npm install && npm test
```

### Dans le navigateur

`web/index.html` charge Pyodide depuis jsDelivr et lit le paquet `eliza/` à
côté. Il faut donc servir la racine du dépôt en HTTP :

```bash
python -m http.server 8765
```

puis ouvrir <http://localhost:8765/web/>. La page propose :

- le choix du script, de la langue (ou détection automatique) et de la version (1965 ou 1966) ;
- le panneau **fonctionnement**, qui montre pas à pas la lecture et le compteur `LIMIT`,
  les mots-clés et substitutions, la décomposition numérotée, le réassemblage et la file
  de mémoire ;
- une présentation **télétype** : papier en continu, 80 colonnes et invite `INPUT` comme
  sur CTSS, impression à 14,8 caractères par seconde comme l'IBM 2741 ;
- l'apprentissage (`*`, `+`) et le téléchargement du script modifié ;
- l'onglet **Archives**, qui rejoue les conversations historiques. Leurs textes sont
  téléchargés à la demande depuis les dépôts d'Anthony Hay et de Rupert Lane, sans être
  redistribués.

## Licence

- Le code est sous [MIT](LICENSE).
- Les scripts de `eliza/scripts/` sont dans le domaine public (CC0 1.0) : TAPE 100 vient du listing
  MIT de Weizenbaum (CC0, succession Weizenbaum), sa traduction française a été écrite pour ce projet,
  et les machines de Turing sont d'Anthony Hay (CC0).
