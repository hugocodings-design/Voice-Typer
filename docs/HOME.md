# PC à la maison — guide d'installation

Votre PC du travail envoie la dictée à votre ordinateur de la maison (carte graphique NVIDIA), qui fait la
transcription et l'écriture IA, puis renvoie le texte : 2 à 3 secondes au lieu de 10 à 15.

- **Au travail : rien à installer.** Voice Typer fait seulement des requêtes HTTPS sortantes, comme pour les
  mises à jour. Aucun port n'est ouvert, aucun serveur ne tourne sur ce PC.
- **À la maison :** Tailscale (pour l'adresse publique) et Voice Typer Home (dans le dossier du projet).
- Si la maison ne répond pas (PC éteint, en veille, pas d'internet), la dictée est faite au travail comme
  avant, et un court message le signale.

## 1. Tailscale Funnel (PC de la maison)

1. Installez Tailscale : https://tailscale.com/download/windows, puis connectez-vous (le plan gratuit suffit).
2. Dans PowerShell :

   ```
   tailscale funnel --bg 8765
   ```

   La première fois, un lien s'affiche : ouvrez-le pour autoriser Funnel sur votre compte, puis relancez la
   commande. Elle affiche votre adresse, par exemple `https://maison.tail1234.ts.net`. Notez-la.
3. Paramètres Windows → Système → Alimentation → Mise en veille sur secteur : **Jamais**.

`tailscale funnel status` montre l'adresse; `tailscale funnel reset` arrête tout.

## 2. Voice Typer Home (PC de la maison)

1. Dans le dossier du projet (là où se trouve `Start Voice Typer.bat`), récupérez la dernière version
   (`git pull`).
2. Double-cliquez sur **`Start Voice Typer Home.bat`**. La fenêtre affiche la **clé**. Laissez-la ouverte.
3. Il utilise **les modèles choisis sur l'ordinateur qui dicte** (Whisper et IA d'écriture) : la première fois
   qu'un modèle est demandé, il le télécharge et le charge (la dictée est alors faite sur l'autre PC), ensuite
   il le garde en mémoire. Un modèle qui n'est pas dans les listes de Voice Typer (ex. un dossier importé sur
   l'autre PC) est remplacé par celui choisi sur ce PC.
4. La fenêtre affiche une ligne par dictée : « dictée … 0,4 s », « écriture IA … 1,8 s ». Une ligne
   « modèle en chargement → fait sur l'autre PC » veut dire que l'autre PC l'a faite lui-même.

La clé est gardée dans `%APPDATA%\VoiceTyperHome\key.txt`. Pour en créer une nouvelle (si elle a fuité) :
`Start Voice Typer Home.bat --new-key`, puis mettez la nouvelle clé au travail.

## 3. Au travail

Réglages → **PC à la maison** : collez l'adresse et la clé, cliquez sur **Tester la connexion**, puis activez
« Utiliser mon PC à la maison ». Après chaque dictée, l'accueil indique « PC à la maison » quand elle y a été
faite : « transcription 0,6 s (maison) · IA 1,8 s (maison) » — chaque étape faite à la maison est marquée.

## Sécurité

- Voice Typer Home n'écoute que sur 127.0.0.1 : seul Tailscale Funnel peut le joindre. Le chiffrement HTTPS se
  termine sur votre PC : Tailscale ne peut pas lire les dictées.
- Chaque requête doit porter la clé (256 bits aléatoires). Après 10 mauvaises clés en une minute, tout est
  refusé pendant une minute.
- Rien n'est écrit sur le disque : ni audio, ni texte. La fenêtre affiche seulement l'heure et le type de
  requête.
- Le code serveur (`home_server/`) est hors du paquet `voice_typer` : l'application installée au travail n'en
  contient pas (`tests/test_no_network_server.py`, `tests/test_home.py`).
- **Données de l'entreprise :** vos dictées (courriels de clients) quittent le PC du travail pour votre PC
  personnel. Vérifiez que c'est permis avant de l'activer.
