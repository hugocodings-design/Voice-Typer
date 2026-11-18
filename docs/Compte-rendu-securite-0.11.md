# Voice Typer 0.11 — Dossier pour le département de sécurité informatique

**Date :** 18 novembre 2026
**Version :** Voice Typer 0.11.0
**Installateur :** `VoiceTyperSetup-0.11.0.exe` (605 Mo), téléchargeable sur
`https://github.com/hugocodings-design/Voice-Typer-Releases/releases/tag/v0.11.0`
**SHA-256 :** `e01b586d6c4e1bb6bfafb4eb6ccec5349f7773feaf360e896705ba68500538c4`

## En bref

Voice Typer est un logiciel de dictée vocale pour Windows 11. On garde un raccourci enfoncé (ou on clique sur
un bouton micro flottant), on parle, et le texte s'écrit dans l'application ouverte (Outlook, Teams, Word…).

- **La voix est transcrite sur le poste**, par un modèle d'intelligence artificielle (Whisper) installé
  localement. Une seconde IA locale, facultative (Qwen 2.5), peut remettre le texte en forme (courriel,
  notes…). **Aucun service infonuagique d'IA n'est utilisé.**
- **Aucune donnée ne quitte le poste** : ni l'audio, ni les textes dictés, ni l'historique, ni les réglages.
  Il n'y a aucune télémétrie.
- **L'application n'ouvre aucun port réseau** et n'accepte aucune connexion entrante.
- Elle s'installe **dans le profil de l'utilisateur, sans droits d'administrateur**.

## Comportements susceptibles de déclencher une alerte

Ces comportements sont nécessaires au fonctionnement. Ils peuvent ressembler à ceux d'un logiciel malveillant
pour un antivirus ou un EDR, d'où cette liste.

| Comportement | Pourquoi | Détail technique |
|---|---|---|
| **Crochet clavier global** | Détecter le raccourci de dictée dans n'importe quelle application. Les frappes ne sont **ni enregistrées ni transmises**. Seul le raccourci est intercepté pour ne pas être tapé dans l'application. | `SetWindowsHookEx(WH_KEYBOARD_LL)` (bibliothèque Python `keyboard`) |
| **Crochet souris global** | Savoir si l'utilisateur a cliqué depuis la dernière dictée. La commande vocale « efface ça » n'efface alors rien, par sécurité. Les clics ne sont ni enregistrés ni transmis. | `SetWindowsHookEx(WH_MOUSE_LL)` |
| **Saisie simulée et presse-papiers** | Écrire le texte dicté dans la fenêtre active. Le contenu précédent du presse-papiers est **restauré** ensuite. La dictée est marquée pour ne pas aller dans l'historique Win+V ni dans la synchronisation cloud de Windows. | `SendInput`, API presse-papiers Win32 |
| **Lecture du nom de l'application active** | Appliquer un préréglage par application (ex. Outlook → courriel). Seul le nom du programme est lu (ex. `outlook.exe`). | `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` + `QueryFullProcessImageNameW` |
| **Microphone** | Capter la voix, **seulement pendant une dictée** (raccourci ou bouton). | PortAudio (DirectSound) |
| **Démarrage avec Windows** (case proposée à l'installation, cochée par défaut ; désactivable dans Réglages) | Lancer Voice Typer à l'ouverture de session, réduit près de l'horloge. | Valeur `VoiceTyper` sous `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` |
| **Mises à jour automatiques** | Télécharge un installateur signé puis le lance en mode silencieux (voir plus bas). | `VoiceTyperSetup-x.y.z.exe /VERYSILENT /UPDATE=1` |
| **Fermeture d'une ancienne copie bloquée** | Si une copie de Voice Typer ne répond plus, une nouvelle copie propose à l'utilisateur de la fermer. Le processus n'est fermé **que si c'est Voice Typer lui-même**, après accord de l'utilisateur. | `TerminateProcess` sur le PID écrit dans `%APPDATA%\VoiceTyper\instance.pid` |
| **Programme non signé** | Pas encore de certificat de signature de code : Windows affiche « éditeur inconnu ». L'exécutable est produit par PyInstaller, que certains antivirus surveillent de près. | Vérification possible par l'empreinte SHA-256 ci-dessus |

Communication entre deux copies de Voice Typer (pour afficher la fenêtre déjà ouverte) : **événements Windows
nommés** (`VoiceTyper.ShowWindow`), sans aucun réseau.

## Accès réseau

Uniquement des **connexions sortantes HTTPS**, à l'initiative de l'application :

| Usage | Destination | Quand |
|---|---|---|
| Téléchargement des modèles d'IA | `huggingface.co` (et ses serveurs de contenu) | Seulement quand l'utilisateur choisit un modèle absent du poste (0,5 à 3 Go). Un modèle déjà présent se charge sans Internet. Télémétrie Hugging Face désactivée. |
| Mises à jour | `github.com/hugocodings-design/Voice-Typer-Releases` (le téléchargement est redirigé vers les serveurs de fichiers de GitHub, `*.githubusercontent.com`) | Vérification au démarrage puis toutes les 6 heures. |

Le bouton « Signaler un problème » ne se connecte à rien lui-même. Il prépare un courriel dans le logiciel de
messagerie de l'utilisateur, adressé au développeur (`hugocodings@gmail.com`), avec un fichier de diagnostic
joint. L'utilisateur voit le courriel avant de l'envoyer. Ce fichier contient le journal, les réglages et des
informations système. Il **ne contient pas** l'historique des dictées, l'audio, le presse-papiers, le
dictionnaire ni la signature.

## Mises à jour : comment elles sont protégées

1. Le fichier `latest.json` publié avec chaque version est **signé (ed25519)**. La clé publique est intégrée à
   l'application, qui **refuse toute mise à jour sans signature valide**.
2. L'application n'accepte que des adresses de téléchargement de ce dépôt GitHub précis.
3. L'empreinte **SHA-256** de l'installateur est vérifiée avant son lancement.
4. Les versions sont construites et publiées par GitHub Actions, à partir du code source (dépôt privé) et de
   paquets Python **épinglés avec empreintes** (`requirements.lock`, `--require-hashes`). La clé de signature est
   conservée dans les secrets chiffrés de GitHub ; le compte du développeur doit être protégé par
   l'authentification à deux facteurs.

**À savoir :** le développeur peut marquer une mise à jour comme **obligatoire** (correctif important). Elle
s'installe alors dès qu'aucune dictée n'est en cours, **même si l'utilisateur a désactivé la vérification
automatique**. Si votre service préfère contrôler les mises à jour, bloquez l'accès à
`github.com/hugocodings-design/Voice-Typer-Releases` : l'application continue de fonctionner normalement sans
mises à jour.

## Données enregistrées sur le poste

Tout est dans le profil de l'utilisateur, en clair, et n'est jamais transmis :

| Emplacement | Contenu |
|---|---|
| `%LOCALAPPDATA%\Programs\Voice Typer` | L'application |
| `%APPDATA%\VoiceTyper\settings.json` | Réglages (raccourcis, dictionnaire, préréglages, signature de courriel) |
| `%APPDATA%\VoiceTyper\history.json` | Historique des 200 dernières dictées (**désactivable** dans Réglages, avec un bouton pour l'effacer) |
| `%APPDATA%\VoiceTyper\voice_typer.log` | Journal technique (erreurs), sans texte dicté |
| `%USERPROFILE%\.cache\huggingface\hub` | Modèles d'IA téléchargés |

La désinstallation (Paramètres Windows → Applications) propose de supprimer aussi les réglages et les modèles.

## Recommandations pour un déploiement en entreprise

- **Autoriser l'exécutable** par son empreinte ou son chemin si une liste blanche est en place (AppLocker,
  WDAC, Intune). Sinon, l'application installée dans le profil utilisateur risque d'être bloquée.
- **Créer une exclusion EDR** pour `Voice Typer.exe` si le crochet clavier déclenche une alerte.
- **Autoriser** `huggingface.co` pour le premier téléchargement des modèles. Les modèles peuvent aussi être
  copiés manuellement dans le dossier ci-dessus, puis importés depuis un dossier local.
- **Désactiver l'historique** si la politique de conservation des données l'exige (Réglages → Démarrage et
  historique).
- **Mises à jour** : les laisser actives (correctifs signés) ou les bloquer au pare-feu (voir plus haut).

## Vérifications faites

- Plus de 120 tests automatiques exécutés sous Windows avant chaque version, dont :
  - un test qui échoue si le code contient un serveur réseau (`listen`, `bind`, serveur HTTP) ou si
    l'application démarrée ouvre un port en écoute ;
  - des tests sur la signature des mises à jour : un fichier modifié, non signé ou signé par une autre clé est
    refusé, et l'option « obligatoire » ne peut être ni ajoutée ni retirée sans la clé ;
  - un test qui vérifie que le fichier de diagnostic ne contient ni dictionnaire ni signature.
- L'application compilée passe un auto-test au moment de la création de l'installateur.

## Différences depuis la version 0.9.3

- Bouton micro flottant (clic pour dicter), retrait des hésitations (« euh »), ouverture et fermeture fiabilisées.
- Bouton « Signaler un problème » (courriel préparé par la messagerie de l'utilisateur).
- Mises à jour obligatoires possibles (champ signé).
- Publication des versions par GitHub Actions au lieu du poste du développeur.
- Toujours aucun port réseau, aucune télémétrie, aucune donnée transmise.

Le compte rendu de la version 0.9.3 (retrait du partage de puissance) reste disponible :
`docs/Compte-rendu-securite-0.9.3.md`.
