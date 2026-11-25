# PC à la maison — guide d'installation

Votre PC du travail envoie la dictée à votre ordinateur de la maison (carte graphique NVIDIA), qui fait la
transcription et l'écriture IA, puis renvoie le texte : 2 à 3 secondes au lieu de 10 à 15.

- **Au travail : rien à installer.** Voice Typer fait seulement des requêtes HTTPS sortantes, comme pour les
  mises à jour. Aucun port n'est ouvert, aucun serveur ne tourne sur ce PC.
- **À la maison :** Tailscale (pour l'adresse publique) et **Home Connections**, l'application qui reçoit les
  demandes de toutes vos applications (Voice Typer, Voice Typer Mobile, Flashcards, TalkTome). Elle a remplacé
  Voice Typer Home (novembre 2026) et vit dans son propre dépôt : `Desktop\PROJETS CLAUDE\HOME CONNECTIONS`.
- Si la maison ne répond pas (PC éteint, en veille, pas d'internet), la dictée est faite au travail comme
  avant, et un court message le signale.

## 1. Tailscale Funnel (PC de la maison)

1. Installez Tailscale : https://tailscale.com/download/windows, puis connectez-vous (le plan gratuit suffit).
2. Dans PowerShell :

   ```
   tailscale funnel --bg 8765
   ```

   La première fois, un lien s'affiche : ouvrez-le pour autoriser Funnel sur votre compte, puis relancez la
   commande. Elle affiche votre adresse, par exemple `https://maison.tail1234.ts.net`.
3. Paramètres Windows → Système → Alimentation → Mise en veille sur secteur : **Jamais**.

## 2. Home Connections (PC de la maison)

Double-cliquez sur **`Start Home Connections.bat`** dans son dossier. Une **icône bleue** apparaît près de
l'horloge ; un clic ouvre la fenêtre :
- **Modèles** : Whisper, IA des courriels, IA TalkTome / Flashcards, voix TalkTome — état, mémoire graphique,
  délai de **mise en veille** propre à chacun (30 s à 15 min, ou jamais), « Libérer maintenant ».
- **Connexion** : l'adresse et **Copier la clé** (la même pour toutes les applications), « Nouvelle clé… ».
- **Activité** : les dernières demandes de chaque application (jamais leur contenu).

Il utilise **les modèles choisis sur l'ordinateur qui dicte**. Dès que vous commencez une dictée, Voice Typer
lui demande de charger les modèles (`/v1/wake`) : un modèle en veille est prêt quand vous avez fini de parler.

Voice Typer sur ce même PC le détecte tout seul (clé dans `%APPDATA%\HomeConnections\key.txt`) et utilise ses
modèles : pas de double chargement sur la carte graphique.

## 3. Au travail

Réglages → **PC à la maison** : collez l'adresse et la clé, cliquez sur **Tester la connexion**, puis activez
« Utiliser mon PC à la maison ». L'accueil affiche « PC à la maison : connecté — la carte graphique » ou
« injoignable », et après chaque dictée « transcription 0,6 s (maison) · IA 1,8 s (maison) ».

## Sécurité

- Home Connections n'écoute que sur 127.0.0.1 : seul Tailscale Funnel peut le joindre. Le chiffrement HTTPS se
  termine sur votre PC : Tailscale ne peut pas lire les dictées.
- Chaque requête doit porter la clé (256 bits aléatoires). Après 10 mauvaises clés en une minute, tout est
  refusé pendant une minute.
- Rien n'est écrit sur le disque : ni audio, ni texte.
- Aucun code serveur dans ce dépôt : l'application installée au travail n'en contient pas
  (`tests/test_no_network_server.py`, `tests/test_home.py`).
- **Données de l'entreprise :** vos dictées (courriels de clients) quittent le PC du travail pour votre PC
  personnel. Vérifiez que c'est permis avant de l'activer.
