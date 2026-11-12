# Voice Typer 0.9.3 — Compte rendu pour le département de sécurité informatique

**Date :** 12 novembre 2026
**Version :** Voice Typer 0.9.3 (publiée le 12 novembre 2026)
**Installateur :** `VoiceTyperSetup-0.9.3.exe` — SHA-256 :
`bf8a3bde54612bce32dfa1bb26080edef563383568172d89de690b2e6d301639`

## En bref

Voice Typer est un logiciel de dictée vocale qui fonctionne **entièrement sur le poste** : la voix est
transcrite par un modèle d'intelligence artificielle installé localement. Depuis la version 0.9.3,
**l'application n'ouvre plus aucun port réseau et ne se connecte plus à aucun autre ordinateur.**

## Ce qui a été retiré

La fonction « partage de puissance » (aussi appelée « Voice Typer Boost ») a été **supprimée du code**.
Cette fonction permettait à un ordinateur personnel de transcrire la voix pour un autre ordinateur
(par exemple le poste de travail) :

- le petit serveur HTTPS qui écoutait sur le port TCP 8765 ;
- le client qui envoyait l'audio à cet autre ordinateur ;
- la page « Partage de puissance », ses réglages (clé d'accès, adresse, empreinte du certificat) et ses
  textes d'aide.

## Nettoyage automatique lors de la mise à jour

Au premier démarrage de la version 0.9.3, l'application :

1. supprime les anciens réglages du partage dans `%APPDATA%\VoiceTyper\settings.json` ;
2. supprime les fichiers du partage : le certificat TLS et sa clé (`host_certificate.pem`,
   `host_certificate_key.pem`) et les statistiques des appareils (`server_devices.json`) ;
3. recherche les règles du Pare-feu Windows qui autorisaient `Voice Typer.exe`. Windows crée ce type de
   règle si l'utilisateur a accepté l'invite « autoriser sur le réseau ». Supprimer ces règles exige des
   droits d'administrateur : si des règles restent, l'application propose de les supprimer et Windows
   demande alors l'autorisation administrateur.

Si le poste était réglé sur « Utiliser un autre PC », il repasse simplement en transcription locale.

## Ce que l'application fait encore sur le réseau

Uniquement des **connexions sortantes en HTTPS**, à l'initiative de l'application. Aucune connexion
entrante n'est acceptée.

| Usage | Destination | Quand |
|---|---|---|
| Téléchargement des modèles d'IA (reconnaissance vocale, rédaction) | `huggingface.co` | Seulement quand l'utilisateur choisit un modèle qui n'est pas encore sur le poste. Un modèle déjà téléchargé se charge sans rien demander à Internet. La télémétrie de la bibliothèque Hugging Face est désactivée. |
| Vérification et téléchargement des mises à jour | `github.com/hugocodings-design/Voice-Typer-Releases` (dépôt public) | Vérification périodique. On peut la désactiver dans Réglages → Mises à jour. Le fichier de mise à jour est signé (ed25519), son empreinte SHA-256 est contrôlée avant l'installation, et seules les adresses de ce dépôt sont acceptées. |

**Aucune donnée ne quitte le poste** : ni l'audio, ni les textes dictés, ni l'historique, ni les réglages.
L'application ne contient aucune télémétrie.

## Vérifications faites

- Un test automatique vérifie que le code ne contient aucun serveur réseau (`listen`, `bind`, serveur
  HTTP), et qu'une application démarrée n'ouvre aucun socket en écoute. Ce test fait partie de la suite
  exécutée avant chaque version (108 tests réussis pour la 0.9.3).
- Un test vérifie que la mise à jour d'une copie réglée sur le partage supprime ses réglages et ses
  fichiers, et que la dictée repasse en local.
- Avec Hugging Face rendu injoignable, les modèles déjà téléchargés se chargent normalement.
- L'application compilée passe son auto-test au moment de la création de l'installateur.

## Points à connaître

- L'installateur n'est pas signé numériquement (pas de certificat de signature de code). Windows peut donc
  afficher l'avertissement SmartScreen « éditeur inconnu ». L'empreinte SHA-256 ci-dessus permet de
  vérifier le fichier.
- L'application s'installe dans le profil de l'utilisateur (`%LOCALAPPDATA%\Programs\Voice Typer`) et ne
  demande pas de droits d'administrateur. Seule la suppression d'anciennes règles de pare-feu, décrite
  plus haut, peut les demander.
- Pour capter le raccourci de dictée, l'application installe un crochet clavier global
  (`SetWindowsHookEx`, bibliothèque `keyboard`). Elle écrit le texte dans la fenêtre active par saisie
  simulée ou par le presse-papiers (qu'elle restaure ensuite). C'est ce comportement qui peut faire
  réagir certains antivirus.
