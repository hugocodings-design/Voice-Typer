# Voice Typer

Local, offline voice-to-text dictation for Windows 11 — in the spirit of [Handy](https://github.com/cjpais/Handy).

Hold a global hotkey, speak, release: your speech is transcribed **on your own machine** with Whisper
(via [faster-whisper](https://github.com/SYSTRAN/faster-whisper)) and typed into whatever app has focus.
No cloud API, no account, nothing leaves your PC.

## Features (MVP)

- [x] Push-to-talk global hotkey (default: `ctrl+alt+space`, hold to record)
- [x] Microphone capture at 16 kHz mono
- [x] Local transcription with faster-whisper (CPU int8 by default, CUDA optional)
- [x] Types the text into the focused window (or pastes it via the clipboard)
- [x] Desktop window with live status (ready / recording / transcribing)
- [x] French and English (plus auto-detect when you mix both)
- [x] Model manager: pick a model by speed vs. accuracy, download it in one click, switch without restarting
- [x] Import your own models: a local faster-whisper folder or a Hugging Face repo id
- [x] Settings saved between launches (`%APPDATA%\VoiceTyper\settings.json`)
- [x] Voice-activity detection to trim silences
- [x] Custom shortcut (record any combo, or pick F9 / Right Ctrl / Ctrl+Win…); its keys are swallowed so nothing leaks into the app
- [x] Three modes: hold to talk; press once to start / once to stop; or automatic (a quick tap keeps
  listening until the next press, holding the key stops at release)
- [x] Floating indicator with a live mic level while dictating (never steals focus)
- [x] Icon next to the clock: closing the window keeps it running; option to start with Windows
- [x] Interface in French or English
- [x] Windows 11 look in bright green and gray (recoloured sv-ttk), light / dark / follow Windows, sidebar navigation, themed pop-ups
- [x] Personal dictionary: words passed to Whisper as `hotwords` + automatic replacements ("chat GPT" → "ChatGPT")
- [x] One-click French / English / auto switch on Home, in the tray menu and with a shortcut
- [x] Optional live typing: words appear at the cursor while you speak, the end is corrected on release
- [x] Right-click menus: models (use, download, delete from disk, open folder), history, dictionary
- [x] Dictation history (local, last 200), microphone choice + level test, start/stop sounds, optional trailing space
- [x] NVIDIA GPU acceleration, automatic with CPU fallback (RTX 2080 Super: ~0.25 s instead of ~5.5 s per sentence with large models)
- [x] **AI writing presets** — a local LLM rewrites the dictation before typing it (email with greeting,
      short paragraphs and signature; quick message; bullet notes; fix only; or your own), each preset with
      its own shortcut (F2, F3, F4…). Embedded in the app: no Ollama / LM Studio to install
- [x] Last dictation stays on the clipboard (Ctrl+V pastes it again) + optional shortcut to re-type it
      after a stray click (Home → "Recoller la dernière dictée")
- [x] **Esc cancels** a recording (nothing is typed), in both modes
- [x] **Voice commands** ("à la ligne", "nouveau paragraphe", "virgule", "ouvrir les guillemets"…),
      can be turned off; full list on the **Aide & commandes** page
- [x] Optional **live transcription** under the indicator while you speak (Réglages)
- [x] **Rewrite the selected text** with a preset via a shortcut, and **per-app presets**
      (e.g. Outlook → Courriel automatically)
- [x] Clipboard privacy: dictations are kept out of Windows clipboard history (Win+V) and cloud sync
- [x] Clipboard fully restored after a dictation: every format (image, Excel cells, rich text, copied
      files…), and only once the target app has really read the dictation (slow Outlook / Teams included)
- [x] **Undo the last dictation**: a shortcut (Home) or say « efface ça » / “delete that” on its own —
      deletes exactly what was typed, only when that is certainly safe (same window, nothing typed or
      clicked since, less than 10 min)
- [x] **Per-application dictionary** (Dictionnaire → Ajouter une application): extra words and
      replacements used only in Outlook, Teams…
- [x] Remembered microphone: if it is unplugged the Windows default takes over, and Voice Typer switches
      back to it by itself once it is reconnected (with a short notice both times)
- [x] **Move to another PC** (Réglages): export your settings to one file (dictionary, per-app
      dictionaries, AI presets, signature, shortcuts…) and import it on the other PC. The microphone,
      history and models stay with each PC
- [x] Welcome assistant on first launch (language, model suited to the PC, mic test, shortcut)
- [x] Diagnostic export (zip without your personal texts) for troubleshooting
- [x] **Speed settings** (Réglages → Vitesse): automatic / fast / accurate transcription, all processor cores
      for transcription and the AI; after each dictation Home shows where the time went (audio, transcription,
      AI, subject). Cleaner dictation pill: the wave has its own zone and the text never runs under it
- [x] **AI presets: signature and subject handled reliably** — per preset, « Ajouter ma signature » (added after
      the closing unless you dictated your own) and « Générer un objet » (first line « Objet : … »); a tall,
      scrollable instructions editor with an « Ouvrir en grand » window
- [x] **Floating mic button** (from Voice Typer Mobile): a green circle you can drag anywhere — click to
      dictate, click again to finish, whatever the shortcut mode; right-click for a menu (dictate with another
      preset, « Toujours dans <app> », language, re-paste / undo the last dictation, hide). It never takes focus,
      so the text lands in the app you were typing in. Can be turned off in Réglages
- [x] Hesitations (euh, hum, um…) and repeated words ("le le") removed without the AI (Réglages, on by default);
      captions Whisper invents on silence ("Sous-titrage Société Radio-Canada") are dropped
- [x] One-click suggested per-app presets (Outlook → Courriel, Teams/Slack → Message rapide, OneNote → Notes)
- [x] **Opening it again just shows it**: launching Voice Typer while it runs (Start menu, shortcut) brings
      its window to the front instead of "already open"; if the running copy is frozen or stuck in the background,
      it offers to close it and start fresh. Closing the window asks once: keep running next to the clock, or
      quit (changeable in Réglages). Quitting really ends the process
- [x] **« Signaler un problème »** (Réglages, menu près de l'horloge): a short description, then an e-mail to the
      developer with a diagnostic attached (classic Outlook attaches it by itself; otherwise the default mail app
      opens and the file's folder is shown). Nothing is sent without the user seeing it
- [x] **Required updates** (`publish.ps1 -Required`): installed copies install it by themselves as soon as nothing
      is being dictated, even with automatic updates turned off, and "Plus tard / Ignorer" are hidden
- [x] **Portable version** (`VoiceTyper-portable-x.y.z.zip`, for PCs whose security rules — Defender ASR —
      block %TEMP%): extract it to e.g. `C:\Dev\VoiceTyper\` and run `Voice Typer.exe`; no installer, nothing
      unpacked at startup, updates applied in that same folder. No copy uses %TEMP% anymore: the app and the
      update installer use `<app>\tmp` (portable) or `%LOCALAPPDATA%\VoiceTyper\tmp` (installed)
- [x] **Windows installer** (`VoiceTyperSetup-x.y.z.exe`, no admin rights) — see *Build the installer*

## Requirements

- Windows 11
- Python **3.12** recommended (faster-whisper's native dependencies may not ship wheels for the newest Python yet)
- A microphone
- Optional: an NVIDIA GPU (recent driver). No CUDA install needed: CTranslate2 bundles cuDNN and
  `requirements.txt` installs cuBLAS 12 inside the venv.

## Run it

```powershell
cd "C:\Users\Hdasi\Desktop\PROJETS CLAUDE\VOICE TYPER"
py -3.12 -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python -m voice_typer
```

A window opens. The first run downloads the default model (`small`, ~480 MB) into the Hugging Face cache;
after that, everything works offline.

Hold `ctrl+alt+space` (or your own shortcut), talk, release. Closing the window keeps Voice Typer
running next to the clock; quit from the tray icon's menu or **Réglages → Quitter**.

Once the venv is set up, you can simply double-click **`Start Voice Typer.bat`** (no console window).

## Install (for colleagues)

Run `VoiceTyperSetup-x.y.z.exe`: no administrator rights, no Python, nothing else to install.
It installs into `%LOCALAPPDATA%\Programs\Voice Typer`, adds a Start-menu entry (optional desktop
shortcut and "start with Windows"), and the welcome assistant downloads the right models on first launch.
Uninstall from Windows Settings → Apps; it asks whether to also delete settings and downloaded models.
Windows SmartScreen may warn the first time ("unknown publisher", the installer isn't code-signed):
*More info → Run anyway*.

On another PC of your own: download the latest installer from
[Voice-Typer-Releases](https://github.com/hugocodings-design/Voice-Typer-Releases/releases/latest)
(or copy the `.exe` on a USB key), install, then on the first PC **Réglages → Transférer vers un autre
PC → Exporter mes réglages**, and on the new one **Importer des réglages** (Voice Typer restarts).

## Build the installer

One command, ~2–4 minutes (tests → PyInstaller → self-test of the built app → Inno Setup):

```powershell
powershell -ExecutionPolicy Bypass -File installer\build.ps1          # add -SkipTests to go faster
```

Output: `dist\VoiceTyperSetup-<version>.exe` (version from `voice_typer/__init__.py`).
One-time setup: `venv\Scripts\python.exe -m pip install pyinstaller` and
`winget install --id JRSoftware.InnoSetup -e --scope user`.
Models are not bundled (the installer stays ~0.5 GB, mostly NVIDIA cuBLAS for GPU acceleration).

## Publishing an update

Installed copies check `latest.json` on the public repository
[Voice-Typer-Releases](https://github.com/hugocodings-design/Voice-Typer-Releases) (installers only, no
source code) 20 s after start and every 6 h. When a newer version exists, a banner offers
**Installer maintenant / Plus tard / Ignorer cette version**. The installer is downloaded, its SHA-256
checked, then run silently with `/UPDATE=1`: settings, history and models are kept and the new version
restarts by itself. **Réglages → Mises à jour** can turn the check off or run it by hand.

To ship a change:

```powershell
# 1. bump __version__ in voice_typer/__init__.py
powershell -ExecutionPolicy Bypass -File installer\build.ps1
powershell -ExecutionPolicy Bypass -File installer\publish.ps1 -Notes "Ce qui change" -NotesEn "What changed"
# add -Required for an important fix: copies from 0.11 on install it without asking
```

**From GitHub instead of the PC** (`.github/workflows/release.yml`): when a new `__version__` lands on `master`,
GitHub builds the installer on Windows and publishes it, with the notes and the *required* flag of
`installer/release-notes.json` (its `version` must match, a test checks it). It needs two repository secrets,
added once from the publishing PC: `VT_UPDATE_SIGNING_KEY` (content of the `.pem` update key) and `RELEASES_TOKEN`
(fine-grained token: repository Voice-Typer-Releases, Contents read and write). Without them it publishes nothing.
Keep two-factor authentication on the GitHub account: with the key in its secrets, the account protects the updates.

`publish.ps1` needs the GitHub CLI logged in to the owner account. Protect that account with two-factor
authentication.

### Update signing key

Since 0.9.0 every `latest.json` is signed (ed25519) and the app **refuses any update that is not signed
with the publisher's key** (wrong or missing signature = no install), so even someone who took over the
GitHub account could not push code to installed copies.

- The **private key** lives on the publishing PC only, outside the repository:
  `%USERPROFILE%\.voice-typer\update-signing-key.pem` (`*.pem` is git-ignored). `publish.ps1` uses it
  through `installer\sign.py`. The public half is in `voice_typer/update_key.py` (not a secret).
- **Back it up now**: copy the `.pem` file to a USB key kept at home and/or paste its content into a
  password manager (Bitwarden, 1Password… as a secure note). **If it is lost, no update can ever be
  published again for the installed copies**: everyone would have to download and reinstall by hand.
- Never send it by e-mail or put it in a cloud folder that syncs in clear. To publish from another PC,
  copy the file to the same place there (or set `VT_SIGNING_DIR` to the folder that holds it).
- `installer\sign.py keygen` creates a key only if none exists (it never overwrites one).

## Reproducible install (pinned + hashed packages)

`requirements.lock` pins the exact version of every package (35) with its SHA-256 hashes: pip refuses
any file that differs from the one tested here (protects against a tampered or swapped package).

```powershell
python -m pip install --require-hashes --no-deps -r requirements.lock
```

## Using the window

- **Shortcut:** *Changer le raccourci…* records any combination (Esc cancels) or offers presets.
  Plain letters / Space alone are refused because they'd block normal typing.
- **Mode:** hold the keys while speaking, or press once to start and once to stop (auto-stops after 5 min).
- **Language you speak:** pick your language (faster and more accurate than Auto-detect). Takes effect immediately.
- **AI model:** select a model and click **Use this model** (or double-click). If it isn't on the PC yet,
  it asks before downloading. The current model keeps working until the new one is ready.

| Group | Model | Size | Best for |
|---|---|---|---|
| French | Français Distil (rapide) — `bofenghuang/whisper-large-v3-french-distil-dec2` | 1.5 GB | Fastest French-trained model |
| French | **Français Distil (précis)** — `…-french-distil-dec16` | 2.2 GB | Recommended for French |
| French | Français Large v3 — `bofenghuang/whisper-large-v3-french` | 3.1 GB | Most accurate French, slow on CPU |
| Multi | Tiny / Base / Small / Medium | 75 MB–1.5 GB | From instant to accurate |
| Multi | **Large v3 Turbo (compact)** — `Zoont/faster-whisper-large-v3-turbo-int8-ct2` | 810 MB | Recommended for French + English |
| Multi | Large v3 Turbo / Large v3 | 1.6 / 3.1 GB | Near-best / best multilingual |
| English | English Distil Small / Medium | 330 / 790 MB | Very fast English |
| English | **English Distil Large v3.5** | 1.5 GB | Recommended for English |

The French models are Whisper Large v3 fine-tuned on French by bofenghuang (MIT license); their
CTranslate2 files live in a `ctranslate2/` subfolder, written `repo#ctranslate2` in the catalog.

- **Import model folder…:** add a model already on disk. It must be in CTranslate2 format
  (folder containing `model.bin` + `config.json`, as published in `faster-whisper-…` repos).
- **Add from Hugging Face…:** add any CTranslate2 Whisper repo by id, e.g. `Systran/faster-whisper-large-v3`.
- **Remove:** removes an imported model from the list (files on disk are kept).

## AI writing (Écriture IA)

Hold a **preset shortcut** instead of the dictation shortcut: Whisper transcribes, then a small local
LLM rewrites the text following the preset's instructions, and the result is typed.

| Preset (default) | Shortcut | Result |
|---|---|---|
| Courriel / Email | F2 | "Bonjour Monsieur X," + 1–2 sentence paragraphs + closing + your signature |
| Message rapide / Quick message | F3 | Short, friendly chat message |
| Notes en points / Bullet notes | F4 | Bulleted list, one idea per line |
| Correction seule / Fix only | — | Grammar and punctuation only |

Edit, add, duplicate or delete presets (name, shortcut, free-text instructions; `{signature}` is
replaced by your signature) and try them without a microphone on the **Écriture IA** page.
Shortcuts of the same key can't be assigned twice; an assigned key (e.g. F2) is reserved for Voice Typer.

The LLM runs **inside** the app with CTranslate2 (the engine faster-whisper already uses): nothing else
to install, which is why it also works on locked-down work PCs. Models (downloaded once, then offline):

| Model | Size | Notes |
|---|---|---|
| `jncraton/Qwen2.5-1.5B-Instruct-ct2-int8` | 1.5 GB | Fast, fine for fixing / formatting (Apache 2.0) |
| **`jncraton/Qwen2.5-3B-Instruct-ct2-int8`** | 3.1 GB | Recommended — ~1 s per email on an RTX 2080 Super (Qwen research licence) |
| `jncraton/Qwen2.5-7B-Instruct-ct2-int8` | 7.6 GB | Smartest, needs a strong PC (Apache 2.0) |

On CPU only, expect several seconds per rewrite (1.5B is the best choice there).
If the rewrite fails, the raw transcript is typed so nothing is lost; the history keeps both versions.

## Network use

Voice Typer never opens a network port and never contacts another computer. Its only network
access is outgoing HTTPS to download:
- speech and writing models from Hugging Face (only when you pick a model that isn't on the PC yet);
- updates from the public GitHub repository `hugocodings-design/Voice-Typer-Releases`
  (`latest.json` + installer, signature checked; can be turned off in Réglages).

Audio, transcripts and history stay on the PC. The "power sharing" feature (one PC transcribing for
another, HTTPS server on port 8765) was removed in 0.9.3. On the first start after the update,
`legacy.py` deletes its settings, its certificate / key / device-statistics files, and offers to
delete any Windows Firewall rule that allowed Voice Typer (needs administrator rights).

## Code signing (optional)

Without a code-signing certificate Windows shows "Unknown publisher" and SmartScreen may warn on the
first downloads. `installer\build.ps1` signs the app and the installer **only if** a certificate is
configured (otherwise the step is skipped):

```powershell
$env:VT_SIGN_PFX = "C:\chemin\certificat.pfx"; $env:VT_SIGN_PASSWORD = "…"   # certificate file
$env:VT_SIGN_THUMBPRINT = "AB12…"   # or a certificate in the Windows store / on a USB token
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

It uses `signtool.exe` from the Windows SDK with an RFC 3161 timestamp (signatures stay valid after
the certificate expires). Options, roughly (prices change, check before buying):

| Option | Approx. price | Notes |
| --- | --- | --- |
| Microsoft Azure Trusted Signing (Artifact Signing) | ~10 USD / month | Cheapest trusted option; individuals in Canada / US can be verified; signs from the cloud (needs a small signtool plug-in setup) |
| OV certificate (Certum, Sectigo, SSL.com…) | ~100–300 USD / year + USB token | Key must be on a hardware token since 2023; SmartScreen trust builds up over downloads |
| EV certificate | ~300–600 USD / year | No longer gives instant SmartScreen trust (Microsoft changed this in 2024): rarely worth it here |
| Self-signed | free | Only trusted on PCs where you install it yourself (e.g. your own PCs); useless for colleagues |

Update integrity does not depend on this: updates are already verified by their ed25519 signature.

### Microsoft Trusted Signing, step by step

1. Azure account (portal.azure.com) → create a **Trusted Signing account** (Basic plan, ~10 USD / month)
   → **Identity validation** for an individual (photo ID; can take a few days) → create a **certificate
   profile** (Public Trust). Give your Microsoft account the role *Trusted Signing Certificate Profile Signer*.
2. On the publishing PC: `winget install -e --id Microsoft.Azure.TrustedSigningClientTools`, the Windows SDK
   (for `signtool.exe`) and the Azure CLI (`winget install -e --id Microsoft.AzureCLI`), then `az login` once.
3. Create `%USERPROFILE%\.voice-typer\trusted-signing.json` (next to the update signing key, never in the repo):

   ```json
   {"Endpoint": "https://eus.codesigning.azure.net", "CodeSigningAccountName": "<account>",
    "CertificateProfileName": "<profile>"}
   ```

   (Endpoint = the region of your account.) `installer\build.ps1` then signs the app and the installer by itself.

The installer then shows your verified name instead of "Unknown publisher". SmartScreen may still warn on
the very first downloads until the signature has built some reputation.

## Advanced settings

**Réglages → Accélération** chooses Automatic (GPU if available), always GPU, or CPU only.
`%APPDATA%\VoiceTyper\settings.json` also holds `compute_type` (CPU, default `int8`) and
`gpu_compute_type` (GPU, default `float16`). Edit it while the app is closed.
"Start with Windows" writes a `VoiceTyper` value under `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

## Project layout

```
VOICE TYPER/
├── voice_typer/
│   ├── __main__.py     # entry point: python -m voice_typer
│   ├── app.py          # engine: hotkey → recorder → transcriber → output, events to the UI
│   ├── engine_*.py     # engine parts: writer (AI presets), hotkeys
│   ├── undo.py         # « annuler la dernière dictée » with its safety checks
│   ├── transfer.py     # settings export / import to another PC (portable settings only)
│   ├── gui/            # tkinter window: window.py + pages/ (home, dictionary, models, writing,
│   │                   #   help, settings), wizard.py (first run), shortcuts.py
│   ├── writer.py       # embedded LLM for AI-writing presets
│   ├── commands.py     # voice commands ("à la ligne", "virgule"…)
│   ├── clipboard.py    # Win32 clipboard: privacy flags, full save/restore, delayed rendering
│   ├── winapp.py       # foreground app detection (per-app presets)
│   ├── legacy.py       # one-time cleanup of the removed power sharing (files, settings, firewall rules)
│   ├── updater.py      # automatic updates from the public releases repository (ed25519-signed)
│   ├── update_key.py   # public key updates must be signed with (installer/sign.py)
│   ├── diagnostic.py   # diagnostic zip export
│   ├── overlay.py      # floating "listening" pill (click-through, no focus)
│   ├── tray.py         # icon next to the clock (pystray)
│   ├── autostart.py    # start with Windows (HKCU Run key)
│   ├── i18n.py         # French / English interface texts
│   ├── models.py       # model catalog, download / import helpers, language list
│   ├── config.py       # settings saved as JSON in %APPDATA%\VoiceTyper
│   ├── recorder.py     # microphone capture (sounddevice)
│   ├── transcriber.py  # faster-whisper wrapper
│   ├── output.py       # types / pastes text into the focused app
│   └── hotkey.py       # global push-to-talk hotkey
├── installer/          # build.ps1, publish.ps1, sign.py (update signatures), voice_typer.spec (PyInstaller),
│                       #   VoiceTyper.iss (Inno Setup), make_assets.py
├── tests/              # pytest (python -m pytest)
├── requirements.txt / requirements.lock
└── CLAUDE.md
```
