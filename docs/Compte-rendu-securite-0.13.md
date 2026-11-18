# Voice Typer 0.13 — Dossier pour le département de sécurité informatique

**Date :** 18 novembre 2026
**Version :** Voice Typer 0.13.0
**Fichiers :** `VoiceTyperSetup-0.13.0.exe` (installateur) et `VoiceTyper-portable-0.13.0.zip` (version
portable, recommandée si `%TEMP%` est bloqué), sur
`https://github.com/hugocodings-design/Voice-Typer-Releases/releases/tag/v0.13.0`. Leurs empreintes SHA-256
figurent sur cette page et dans le fichier signé `latest.json` publié avec la version.

## En bref

Voice Typer est un logiciel de dictée vocale pour Windows 11. On garde un raccourci enfoncé (ou on clique sur
un bouton micro flottant), on parle, et le texte s'écrit dans l'application ouverte (Outlook, Teams, Word…).

- **La voix est transcrite sur le poste**, par un modèle d'intelligence artificielle (Whisper) installé
  localement. Une seconde IA locale, facultative (Qwen 2.5), peut remettre le texte en forme (courriel,
  notes…). **Aucun service infonuagique d'IA n'est utilisé.**
- **Par défaut, aucune donnée ne quitte le poste** : ni l'audio, ni les textes dictés, ni l'historique, ni les
  réglages. Il n'y a aucune télémétrie. Seule exception, **facultative et désactivée par défaut** : le « PC boost »
  (voir plus bas), qui envoie l'audio des dictées à un autre ordinateur de l'utilisateur.
- **Sur un poste qui utilise le PC boost ou ne l'utilise pas, l'application n'ouvre aucun port réseau** et
  n'accepte aucune connexion entrante. Seul l'ordinateur qui *partage* sa puissance (le PC de la maison) écoute
  sur un port.
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

## PC boost (partage de puissance), version 0.13

**Approuvé par le service informatique** à la demande de l'utilisateur. Désactivé par défaut ; il faut le
configurer volontairement des deux côtés.

But : faire transcrire la voix par un ordinateur plus puissant de l'utilisateur (PC de la maison avec carte
graphique), pour des dictées plus rapides et plus précises.

| | PC de la maison (« Partager ce PC ») | Poste de travail (« Utiliser un autre PC ») |
|---|---|---|
| Rôle | Petit serveur HTTPS sur le port TCP **8765** | Client : **connexions sortantes uniquement** |
| Port ouvert | Oui (8765) ; Windows demande l'autorisation du pare-feu la première fois | **Aucun** |
| Données | Reçoit l'audio, renvoie le texte ; garde le nombre de dictées par appareil (`server_devices.json`) | Envoie l'audio de la dictée (et le texte à mettre en forme si un préréglage IA est utilisé) |

Sécurité de l'échange :

- **Chiffrement TLS**. Le PC de la maison crée son propre certificat ; son empreinte SHA-256 fait partie du code
  de jumelage, et le poste de travail la vérifie à chaque connexion (*certificate pinning*). Un autre ordinateur
  ne peut pas se faire passer pour le PC de la maison.
- **Clé d'accès** aléatoire, envoyée à chaque requête (`Authorization: Bearer`) et comparée en temps constant ;
  10 clés erronées en 5 minutes depuis une même adresse et cette adresse est ignorée un moment.
- Par défaut, le PC de la maison **refuse toute connexion venant d'Internet** : seules les adresses privées
  (réseau de la maison) et **Tailscale** (`100.64.0.0/10`) sont acceptées, avant même l'échange TLS.
- Le jumelage n'est **jamais importé** par un fichier de réglages (test automatique) : on ne peut pas rediriger les
  dictées d'un poste vers un autre ordinateur en lui faisant importer un fichier.
- Si le PC de la maison est éteint ou injoignable, la dictée est **transcrite sur le poste**, comme avant.

Connexion entre les deux ordinateurs : **Tailscale** (réseau privé chiffré, gratuit), installé sur les deux.
**L'installation de Tailscale sur le poste de travail est donc aussi à approuver.** Sans Tailscale, il faudrait
exposer le PC de la maison sur Internet (option « accepter les connexions d'Internet », déconseillée).

Une copie mise à jour directement depuis la version 0.9.2 (avant le retrait du partage) **ne se reconnecte pas**
toute seule à un ancien jumelage : ses anciens réglages sont supprimés au premier démarrage, avant d'être lus.

## Accès réseau

Uniquement des **connexions sortantes HTTPS**, à l'initiative de l'application :

| Usage | Destination | Quand |
|---|---|---|
| Téléchargement des modèles d'IA | `huggingface.co` (et ses serveurs de contenu) | Seulement quand l'utilisateur choisit un modèle absent du poste (0,5 à 3 Go). Un modèle déjà présent se charge sans Internet. Télémétrie Hugging Face désactivée. |
| PC boost (seulement si configuré) | Le PC de la maison de l'utilisateur, port 8765, via son adresse Tailscale (`100.x.x.x`) | À chaque dictée. Connexion chiffrée, certificat épinglé. |
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

## Version 0.12 : dossier temporaire et version portable

À la demande d'un service informatique dont les règles ASR bloquent `%TEMP%` :

- **Voice Typer n'utilise plus jamais le dossier temporaire de Windows** (`%TEMP%`,
  `AppData\Local\Temp`). Dès le démarrage, il utilise son propre dossier : `C:\Dev\VoiceTyper\tmp` pour la
  version portable, `%LOCALAPPDATA%\VoiceTyper\tmp` pour la version installée. Les bibliothèques et
  l'installateur lancé par une mise à jour utilisent aussi ce dossier.
- **Version portable** `VoiceTyper-portable-0.12.0.zip`, publiée à côté de l'installateur : on l'extrait dans
  `C:\Dev\VoiceTyper\` et on lance `Voice Typer.exe`. Pas d'installateur, et rien n'est décompressé au
  démarrage : l'application est un dossier de fichiers (PyInstaller en mode « dossier », jamais « fichier
  unique »).
- **Mises à jour de la version portable** : le zip signé est téléchargé dans `C:\Dev\VoiceTyper\tmp`, son
  empreinte SHA-256 vérifiée (elle est couverte par la signature ed25519), puis il est décompressé dans ce même
  dossier. Une fois l'application fermée, `robocopy` copie les nouveaux fichiers dans `C:\Dev\VoiceTyper\`,
  puis l'application redémarre.
- Désinstallation de la version portable : supprimer le dossier `C:\Dev\VoiceTyper\` (et, si souhaité,
  `%APPDATA%\VoiceTyper` et les modèles dans `%USERPROFILE%\.cache\huggingface\hub`).

## Différences depuis la version 0.9.3

- Bouton micro flottant (clic pour dicter), retrait des hésitations (« euh »), ouverture et fermeture fiabilisées.
- Bouton « Signaler un problème » (courriel préparé par la messagerie de l'utilisateur).
- Version portable et dossier temporaire propre à l'application (0.12, voir plus haut).
- Retour du PC boost (0.13), désactivé par défaut.
- Mises à jour obligatoires possibles (champ signé).
- Publication des versions par GitHub Actions au lieu du poste du développeur.
- PC boost (0.13) : facultatif, approuvé par le service informatique, voir plus haut. Sans lui : aucun port réseau,
  aucune télémétrie, aucune donnée transmise.

Le compte rendu de la version 0.9.3 (retrait du partage de puissance) reste disponible :
`docs/Compte-rendu-securite-0.9.3.md`.
