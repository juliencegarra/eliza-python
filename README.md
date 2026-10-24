# eliza-python

Un portage Python **fidèle** de l'ELIZA de Joseph Weizenbaum (1966) : pour
une même entrée et un même script, il donne la même réponse que l'original.

- Il reproduit mot pour mot la conversation publiée dans *CACM* en 1966.
- Il reproduit une exécution du code MAD-SLIP d'origine sur un IBM 7094 émulé (CTSS).
- Il donne les mêmes réponses que la reconstruction C++ d'Anthony Hay (`eliza.cpp`), qui sert d'oracle aux tests.
- Il n'utilise que la bibliothèque standard de Python ≥ 3.9.

## Utilisation

```bash
python -m eliza                       # DOCTOR, script de mars 1965 (domaine public)
python -m eliza --lang fr             # le même DOCTOR, traduit en français
python -m eliza --lang auto           # suit la langue de chaque phrase (anglais / français)
python -m eliza mon_script.txt --lang fr
```

Ligne vide pour quitter. `*` affiche la façon dont la dernière réponse a été construite.

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

puis ouvrir <http://localhost:8765/web/>.

## Licence

- Le code est sous [MIT](LICENSE).
- Les scripts de `eliza/scripts/` sont dans le domaine public (CC0 1.0) : TAPE 100 vient du listing
  MIT de Weizenbaum (CC0, succession Weizenbaum), sa traduction française a été écrite pour ce projet,
  et les machines de Turing sont d'Anthony Hay (CC0).
