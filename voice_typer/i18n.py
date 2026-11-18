"""Interface texts in French and English."""

STRINGS: dict[str, dict[str, str]] = {
    "fr": {
        # navigation & pages
        "nav_home": "Accueil", "nav_dictionary": "Dictionnaire", "nav_languages": "Langues",
        "nav_models": "Modèles IA", "nav_settings": "Réglages",
        "title_home": "Accueil", "sub_home": "Dictez n'importe où : placez le curseur, utilisez votre raccourci, parlez.",
        "title_dictionary": "Dictionnaire",
        "sub_dictionary": "Apprenez à Voice Typer vos noms propres, marques et termes techniques.",
        "title_languages": "Langues", "sub_languages": "Choisissez vos langues préférées et passez de l'une à l'autre en un geste.",
        "title_models": "Modèles IA", "sub_models": "Plus un modèle est gros, plus il est précis. Avec la carte graphique, même les gros restent rapides.",
        "title_settings": "Réglages", "sub_settings": "Personnalisez Voice Typer.",
        # common
        "none": "Aucun", "change": "Changer…", "disable": "Désactiver", "add": "Ajouter", "edit": "Modifier",
        "delete": "Supprimer", "copy": "Copier", "cancel": "Annuler", "active": "● Active", "use_now": "Utiliser maintenant",
        # status
        "status_starting": "Démarrage…",
        "status_ready_hold": "Prêt — maintenez {hotkey} et parlez",
        "status_ready_toggle": "Prêt — appuyez sur {hotkey} pour parler",
        "status_recording_hold": "Écoute… relâchez pour écrire (Échap annule)",
        "status_recording_toggle": "Écoute… appuyez de nouveau sur {hotkey} pour écrire (Échap annule)",
        "status_ready_auto": "Prêt — touchez {hotkey} pour parler, ou maintenez-le",
        "status_recording_auto": "Écoute… relâchez, ou appuyez de nouveau sur {hotkey}, pour écrire (Échap annule)",
        "status_transcribing": "Transcription…",
        "status_loading": "Chargement de {name}…",
        "status_downloading": "Téléchargement de {name}…",
        "status_no_model": "Aucun modèle chargé",
        "side_ok": "Prêt", "side_rec": "Écoute", "side_busy": "Occupé…", "side_off": "Arrêté",
        "overlay_listening": "Écoute…", "overlay_transcribing": "Transcription…", "lang_now": "Langue :",
        # home
        "home_lang_title": "Langue active",
        "home_lang_sub": "Français, anglais, ou détection automatique si vous passez de l'un à l'autre.",
        "manage_languages": "Gérer les langues →",
        "shortcut_title": "Raccourci pour dicter",
        "mode_hold": "Maintenir pendant que je parle",
        "mode_toggle": "Appuyer pour commencer, appuyer pour finir",
        "mode_auto": "Automatique (appui bref ou maintenu)",
        "mode_auto_hint": "Appui bref : la dictée continue jusqu'au prochain appui. Maintenu : elle s'arrête quand vous relâchez.",
        "chip_model": "Modèle", "chip_gpu": "Carte graphique", "chip_cpu": "Processeur", "chip_lang": "Langue",
        "chip_dict": "Dictionnaire : {n} mot(s)",
        "history_title": "Historique", "col_time": "Quand", "col_lang": "Langue", "col_text": "Texte",
        "history_empty": "Vos dictées apparaîtront ici. Clic droit pour copier ou supprimer.",
        "history_off": "L'historique est désactivé (Réglages).",
        "history_clear": "Effacer l'historique", "history_clear_confirm": "Effacer tout l'historique des dictées ?",
        "hist_to_dict": "Corriger via le dictionnaire…",
        "last_empty": "Placez le curseur dans n'importe quelle application et utilisez {hotkey}.",
        "nothing_heard": "(rien entendu)", "too_short": "Trop court, ignoré.",
        "no_model": "Patientez, le modèle est en cours de chargement.",
        "no_model_none": "Aucun modèle chargé : choisissez-en un dans Modèles IA.",
        "model_ready": "Modèle « {name} » prêt sur {where} ({s:.1f} s).",
        "where_gpu": "la carte graphique", "where_cpu": "le processeur",
        # dictionary
        "vocab_title": "Mots à reconnaître",
        "vocab_sub": "Noms, marques, jargon… Voice Typer les donne au modèle comme indices pour mieux les reconnaître.",
        "col_term": "Mot ou expression",
        "repl_title": "Remplacements automatiques",
        "repl_sub": "Si le modèle écrit toujours mal un mot, corrigez-le automatiquement après la dictée.",
        "repl_from": "Texte entendu", "repl_to": "Écrire à la place",
        "dict_tip": "Astuce : clic droit ou double-clic pour modifier, touche Suppr pour effacer. Exemple de remplacement : « chat GPT » → « ChatGPT ».",
        # languages
        "lang_hotkey_title": "Raccourci pour changer de langue",
        "lang_hotkey_sub": "Bascule entre français et anglais depuis n'importe quelle application. Un petit message confirme la langue.",
        "all_languages": "Toutes les langues",
        "all_languages_sub": "★ = favorite. Double-clic pour ajouter ou retirer des favoris, clic droit pour plus d'options.",
        "col_fav": "Favori", "col_language": "Langue", "col_code": "Code", "col_active": "État",
        "fav_add": "★ Ajouter aux favoris", "fav_remove": "Retirer des favoris",
        "move_up": "Monter dans les favoris", "move_down": "Descendre dans les favoris",
        # models
        "col_model": "Modèle", "col_size": "Taille", "col_speed": "Vitesse", "col_accuracy": "Précision",
        "col_status": "État", "col_notes": "Notes",
        "st_in_use": "● Utilisé", "st_downloaded": "✓ Téléchargé", "st_not_downloaded": "Non téléchargé",
        "st_loading": "⏳ Chargement…",
        "btn_use": "Utiliser ce modèle", "btn_import_folder": "Importer un dossier…",
        "btn_import_hf": "Ajouter depuis Hugging Face…", "btn_remove": "Retirer de la liste",
        "disk_used": "Espace utilisé : {size}",
        "models_tip": "Clic droit sur un modèle : télécharger, supprimer du disque, ouvrir son dossier, voir sa page…",
        "imported_model": "Modèle importé",
        "dl_title": "Télécharger le modèle",
        "dl_msg": "« {name} »{size} n'est pas encore sur ce PC.\n\nLe télécharger maintenant ? C'est la seule étape qui utilise Internet ; ensuite tout fonctionne hors ligne.",
        "dl_only_msg": "Télécharger « {name} »{size} sans l'utiliser tout de suite ?",
        "download_only": "Télécharger sans l'utiliser", "downloaded_msg": "« {name} » est téléchargé.",
        "delete_files": "Supprimer du disque…", "delete_files_title": "Supprimer le modèle du disque",
        "delete_files_msg": "Supprimer les fichiers de « {name} » ({size}) ?\n\nIl faudra le retélécharger pour l'utiliser à nouveau.",
        "open_folder": "Ouvrir le dossier",
        "already_added_title": "Déjà ajouté", "already_added_msg": "« {name} » est déjà dans la liste.",
        "folder_title": "Choisissez un dossier de modèle faster-whisper (CTranslate2)",
        "folder_error_title": "Modèle incompatible",
        "folder_error_msg": "Il manque {missing} dans ce dossier.\n\nVoice Typer a besoin d'un modèle Whisper au format CTranslate2 (ceux publiés sous le nom « faster-whisper-… » sur Hugging Face).",
        "hf_title": "Ajouter depuis Hugging Face",
        "hf_prompt": "Nom du dépôt Hugging Face d'un modèle faster-whisper (CTranslate2),\npar exemple :  Systran/faster-whisper-large-v3",
        "hf_invalid_title": "Nom invalide", "hf_invalid_msg": "Utilisez la forme  propriétaire/nom-du-modèle",
        "hf_not_ct2": "Ce dépôt ne contient pas de modèle au format CTranslate2 (model.bin).\nCherchez une version « faster-whisper » ou « ct2 » du modèle.",
        "hf_network": "Impossible de lire ce dépôt sur Hugging Face :\n\n{err}",
        "remove_title": "Retirer le modèle",
        "remove_msg": "Retirer « {name} » de la liste ?\n\n(Les fichiers sur le disque ne sont pas supprimés.)",
        "model_error_title": "Erreur de modèle", "model_error_msg": "Impossible de charger « {name} » :\n\n{err}",
        # settings
        "set_appearance": "Apparence", "set_theme": "Thème", "theme_system": "Comme Windows",
        "theme_light": "Clair", "theme_dark": "Sombre", "set_ui_lang": "Langue de l'interface",
        "set_overlay": "Afficher l'indicateur flottant en bas de l'écran pendant la dictée",
        "set_mic": "Microphone", "set_mic_sub": "Choisissez le micro et vérifiez qu'il vous entend bien.",
        "mic_default": "Micro par défaut de Windows", "mic_test": "Tester", "mic_stop": "Arrêter le test",
        "set_sounds": "Petit son au début et à la fin de la dictée",
        "set_output": "Écriture du texte",
        "out_paste": "Coller d'un coup (rapide, recommandé)",
        "out_type": "Taper lettre par lettre (si le collage ne marche pas dans une app)",
        "set_trailing_space": "Ajouter un espace après chaque dictée",
        "set_accel": "Accélération",
        "accel_auto": "Automatique : carte graphique NVIDIA si disponible (recommandé)",
        "accel_cuda": "Toujours la carte graphique NVIDIA", "accel_cpu": "Processeur uniquement (plus lent)",
        "accel_now_gpu": "Utilisé maintenant : carte graphique {name}", "accel_now_cpu": "Utilisé maintenant : processeur",
        "accel_no_gpu": "Aucune carte graphique NVIDIA compatible détectée.",
        "gpu_fallback_title": "Carte graphique indisponible",
        "gpu_fallback_msg": "La carte graphique n'a pas pu être utilisée : Voice Typer tourne sur le processeur (plus lent).\n\nDétail : {err}",
        "set_startup": "Démarrage et historique",
        "set_autostart": "Lancer Voice Typer au démarrage de Windows (discrètement, près de l'horloge)",
        "set_history": "Garder l'historique des dictées (200 dernières, sur ce PC uniquement)",
        "set_about": "À propos",
        "about_text": "Voice Typer {version} — dictée 100 % locale : votre voix ne quitte jamais ce PC.",
        "open_models_dir": "Dossier des modèles", "open_settings_dir": "Dossier des réglages",
        "btn_quit": "Quitter Voice Typer",
        # shortcut dialog
        "rec_title": "Nouveau raccourci",
        "rec_prompt": "Appuyez sur la combinaison de touches voulue, puis relâchez.\n(Échap pour annuler)",
        "rec_waiting": "En attente des touches…", "rec_presets": "Ou choisissez une suggestion :",
        "rec_err_single": "« {combo} » bloquerait l'écriture normale.\nAjoutez Ctrl, Alt, Maj ou Win, ou utilisez une touche comme F9 ou Ctrl droit.",
        "rec_err_unknown": "Touche non reconnue : « {combo} ».",
        "rec_err_same": "« {combo} » est déjà utilisé par l'autre raccourci.",
        "rec_err_title": "Raccourci impossible",
        # tray
        "tray_open": "Ouvrir Voice Typer", "tray_language": "Langue", "tray_quit": "Quitter",
        "tray_hint": "Voice Typer reste actif ici. Votre raccourci fonctionne toujours.",
        "already_running": "Voice Typer est déjà ouvert.\nCherchez son icône près de l'horloge, en bas à droite de l'écran.",
    },
    "en": {
        "nav_home": "Home", "nav_dictionary": "Dictionary", "nav_languages": "Languages",
        "nav_models": "AI models", "nav_settings": "Settings",
        "title_home": "Home", "sub_home": "Dictate anywhere: place your cursor, use your shortcut, speak.",
        "title_dictionary": "Dictionary", "sub_dictionary": "Teach Voice Typer your names, brands and technical terms.",
        "title_languages": "Languages", "sub_languages": "Pick your favorite languages and switch between them in one move.",
        "title_models": "AI models", "sub_models": "Bigger models are more accurate. With a GPU, even big ones stay fast.",
        "title_settings": "Settings", "sub_settings": "Make Voice Typer yours.",
        "none": "None", "change": "Change…", "disable": "Disable", "add": "Add", "edit": "Edit",
        "delete": "Delete", "copy": "Copy", "cancel": "Cancel", "active": "● Active", "use_now": "Use now",
        "status_starting": "Starting…",
        "status_ready_hold": "Ready — hold {hotkey} and speak",
        "status_ready_toggle": "Ready — press {hotkey} to speak",
        "status_recording_hold": "Listening… release to type (Esc cancels)",
        "status_recording_toggle": "Listening… press {hotkey} again to type (Esc cancels)",
        "status_ready_auto": "Ready — tap {hotkey} to speak, or hold it",
        "status_recording_auto": "Listening… release, or press {hotkey} again, to type (Esc cancels)",
        "status_transcribing": "Transcribing…",
        "status_loading": "Loading {name}…", "status_downloading": "Downloading {name}…",
        "status_no_model": "No model loaded",
        "side_ok": "Ready", "side_rec": "Listening", "side_busy": "Busy…", "side_off": "Stopped",
        "overlay_listening": "Listening…", "overlay_transcribing": "Transcribing…", "lang_now": "Language:",
        "home_lang_title": "Active language",
        "home_lang_sub": "French, English, or auto-detect if you switch between the two.",
        "manage_languages": "Manage languages →",
        "shortcut_title": "Dictation shortcut",
        "mode_hold": "Hold while I speak", "mode_toggle": "Press to start, press to finish",
        "mode_auto": "Automatic (quick tap or hold)",
        "mode_auto_hint": "Quick tap: dictation keeps going until the next press. Held: it stops when you release.",
        "chip_model": "Model", "chip_gpu": "GPU", "chip_cpu": "CPU", "chip_lang": "Language",
        "chip_dict": "Dictionary: {n} term(s)",
        "history_title": "History", "col_time": "When", "col_lang": "Language", "col_text": "Text",
        "history_empty": "Your dictations will appear here. Right-click to copy or delete.",
        "history_off": "History is turned off (Settings).",
        "history_clear": "Clear history", "history_clear_confirm": "Clear the whole dictation history?",
        "hist_to_dict": "Fix with the dictionary…",
        "last_empty": "Put your cursor in any app and use {hotkey}.",
        "nothing_heard": "(nothing heard)", "too_short": "Too short, ignored.",
        "no_model": "Please wait, the model is still loading.",
        "no_model_none": "No model loaded: pick one in AI models.",
        "model_ready": "Model '{name}' ready on {where} ({s:.1f}s).",
        "where_gpu": "the GPU", "where_cpu": "the CPU",
        "vocab_title": "Words to recognize",
        "vocab_sub": "Names, brands, jargon… Voice Typer gives them to the model as hints so it recognizes them better.",
        "col_term": "Word or phrase",
        "repl_title": "Automatic replacements",
        "repl_sub": "If the model keeps misspelling something, fix it automatically after dictation.",
        "repl_from": "Heard text", "repl_to": "Write instead",
        "dict_tip": "Tip: right-click or double-click to edit, Delete key to remove. Replacement example: 'chat GPT' → 'ChatGPT'.",
        "lang_hotkey_title": "Shortcut to switch language",
        "lang_hotkey_sub": "Switches between French and English from any app. A small message confirms the language.",
        "all_languages": "All languages",
        "all_languages_sub": "★ = favorite. Double-click to add/remove favorites, right-click for more.",
        "col_fav": "Favorite", "col_language": "Language", "col_code": "Code", "col_active": "Status",
        "fav_add": "★ Add to favorites", "fav_remove": "Remove from favorites",
        "move_up": "Move up in favorites", "move_down": "Move down in favorites",
        "col_model": "Model", "col_size": "Size", "col_speed": "Speed", "col_accuracy": "Accuracy",
        "col_status": "Status", "col_notes": "Notes",
        "st_in_use": "● In use", "st_downloaded": "✓ Downloaded", "st_not_downloaded": "Not downloaded",
        "st_loading": "⏳ Loading…",
        "btn_use": "Use this model", "btn_import_folder": "Import model folder…",
        "btn_import_hf": "Add from Hugging Face…", "btn_remove": "Remove from list",
        "disk_used": "Disk used: {size}",
        "models_tip": "Right-click a model: download, delete from disk, open its folder, see its page…",
        "imported_model": "Imported model",
        "dl_title": "Download model",
        "dl_msg": "'{name}'{size} isn't on this PC yet.\n\nDownload it now? This is the only step that needs the internet; afterwards it works offline.",
        "dl_only_msg": "Download '{name}'{size} without using it yet?",
        "download_only": "Download without using", "downloaded_msg": "'{name}' is downloaded.",
        "delete_files": "Delete from disk…", "delete_files_title": "Delete model from disk",
        "delete_files_msg": "Delete the files of '{name}' ({size})?\n\nYou'll need to download it again to use it.",
        "open_folder": "Open folder",
        "already_added_title": "Already added", "already_added_msg": "'{name}' is already in the list.",
        "folder_title": "Choose a faster-whisper (CTranslate2) model folder",
        "folder_error_title": "Not a compatible model",
        "folder_error_msg": "This folder is missing {missing}.\n\nVoice Typer needs a Whisper model converted to CTranslate2 format (the kind published as 'faster-whisper-…' on Hugging Face).",
        "hf_title": "Add from Hugging Face",
        "hf_prompt": "Hugging Face repository of a faster-whisper (CTranslate2) model,\nfor example:  Systran/faster-whisper-large-v3",
        "hf_invalid_title": "Invalid name", "hf_invalid_msg": "Use the form  owner/model-name",
        "hf_not_ct2": "This repository has no CTranslate2 model (model.bin).\nLook for a 'faster-whisper' or 'ct2' version of the model.",
        "hf_network": "Couldn't read this repository on Hugging Face:\n\n{err}",
        "remove_title": "Remove model", "remove_msg": "Remove '{name}' from the list?\n\n(Files on disk are not deleted.)",
        "model_error_title": "Model error", "model_error_msg": "Couldn't load '{name}':\n\n{err}",
        "set_appearance": "Appearance", "set_theme": "Theme", "theme_system": "Same as Windows",
        "theme_light": "Light", "theme_dark": "Dark", "set_ui_lang": "Interface language",
        "set_overlay": "Show the floating indicator at the bottom of the screen while dictating",
        "set_mic": "Microphone", "set_mic_sub": "Pick your microphone and check that it hears you.",
        "mic_default": "Windows default microphone", "mic_test": "Test", "mic_stop": "Stop test",
        "set_sounds": "Short sound at the start and end of dictation",
        "set_output": "Writing the text",
        "out_paste": "Paste all at once (fast, recommended)",
        "out_type": "Type letter by letter (if pasting doesn't work in an app)",
        "set_trailing_space": "Add a space after each dictation",
        "set_accel": "Acceleration",
        "accel_auto": "Automatic: NVIDIA GPU if available (recommended)",
        "accel_cuda": "Always use the NVIDIA GPU", "accel_cpu": "CPU only (slower)",
        "accel_now_gpu": "Currently using: GPU {name}", "accel_now_cpu": "Currently using: CPU",
        "accel_no_gpu": "No compatible NVIDIA GPU detected.",
        "gpu_fallback_title": "GPU unavailable",
        "gpu_fallback_msg": "The GPU couldn't be used: Voice Typer is running on the CPU (slower).\n\nDetails: {err}",
        "set_startup": "Startup and history",
        "set_autostart": "Start Voice Typer with Windows (quietly, next to the clock)",
        "set_history": "Keep dictation history (last 200, on this PC only)",
        "set_about": "About",
        "about_text": "Voice Typer {version} — 100% local dictation: your voice never leaves this PC.",
        "open_models_dir": "Models folder", "open_settings_dir": "Settings folder",
        "btn_quit": "Quit Voice Typer",
        "rec_title": "New shortcut",
        "rec_prompt": "Press the key combination you want, then release.\n(Esc to cancel)",
        "rec_waiting": "Waiting for keys…", "rec_presets": "Or pick a suggestion:",
        "rec_err_single": "'{combo}' would block normal typing.\nAdd Ctrl, Alt, Shift or Win, or use a key like F9 or Right Ctrl.",
        "rec_err_unknown": "Unrecognized key: '{combo}'.",
        "rec_err_same": "'{combo}' is already used by the other shortcut.",
        "rec_err_title": "Can't use this shortcut",
        "tray_open": "Open Voice Typer", "tray_language": "Language", "tray_quit": "Quit",
        "tray_hint": "Voice Typer keeps running here. Your shortcut still works.",
        "already_running": "Voice Typer is already open.\nLook for its icon next to the clock, bottom right of the screen.",
    },
}

FR_D2 = "bofenghuang/whisper-large-v3-french-distil-dec2#ctranslate2"
FR_D16 = "bofenghuang/whisper-large-v3-french-distil-dec16#ctranslate2"
FR_L3 = "bofenghuang/whisper-large-v3-french#ctranslate2"
TURBO_C = "Zoont/faster-whisper-large-v3-turbo-int8-ct2"

MODEL_NOTES = {
    "fr": {
        FR_D2: "Entraîné sur le français : le plus rapide des modèles français",
        FR_D16: "★ Recommandé français : presque aussi précis que Large v3",
        FR_L3: "Le plus précis en français",
        "tiny": "Instantané, mais beaucoup d'erreurs",
        "base": "Rapide, correct pour des phrases courtes",
        "small": "Bon équilibre, léger",
        "medium": "Précis",
        TURBO_C: "★ Recommandé FR + EN : qualité Turbo, 2× plus léger",
        "large-v3-turbo": "Presque la meilleure précision, rapide",
        "large-v3": "Meilleure précision multilingue",
        "distil-small.en": "Anglais uniquement, très rapide",
        "distil-medium.en": "Anglais uniquement, rapide et précis",
        "distil-large-v3.5": "★ Recommandé anglais : précision Large v3, plus rapide",
    },
    "en": {
        FR_D2: "Trained on French: the fastest French model",
        FR_D16: "★ Recommended for French: nearly Large v3 accuracy",
        FR_L3: "Most accurate in French",
        "tiny": "Instant, but many mistakes",
        "base": "Fast, OK for short sentences",
        "small": "Good balance, lightweight",
        "medium": "Accurate",
        TURBO_C: "★ Recommended FR + EN: Turbo quality, half the size",
        "large-v3-turbo": "Near-best accuracy, fast",
        "large-v3": "Best multilingual accuracy",
        "distil-small.en": "English only, very fast",
        "distil-medium.en": "English only, fast and accurate",
        "distil-large-v3.5": "★ Recommended for English: Large v3 accuracy, faster",
    },
}

GROUP_LABELS = {
    "fr": {"fr": "Spécialisés français", "multi": "Multilingues (~100 langues)",
           "en": "Spécialisés anglais", "custom": "Mes modèles importés"},
    "en": {"fr": "French-specialised", "multi": "Multilingual (~100 languages)",
           "en": "English-specialised", "custom": "My imported models"},
}

KEY_NAMES = {
    "fr": {"ctrl": "Ctrl", "alt": "Alt", "shift": "Maj", "windows": "Win", "space": "Espace",
           "right ctrl": "Ctrl droit", "left ctrl": "Ctrl gauche", "right shift": "Maj droite",
           "right alt": "Alt droit", "alt gr": "Alt Gr", "caps lock": "Verr. Maj", "enter": "Entrée",
           "scroll lock": "Arrêt défil", "insert": "Inser", "menu": "Menu"},
    "en": {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "windows": "Win", "space": "Space",
           "right ctrl": "Right Ctrl", "left ctrl": "Left Ctrl", "right shift": "Right Shift",
           "right alt": "Right Alt", "alt gr": "Alt Gr", "caps lock": "Caps Lock", "enter": "Enter",
           "scroll lock": "Scroll Lock", "insert": "Insert", "menu": "Menu"},
}


# AI writing (post-processing presets)
STRINGS["fr"].update({
    "nav_writing": "Écriture IA",
    "title_writing": "Écriture IA",
    "sub_writing": "Dictez avec un raccourci de préréglage : une IA locale met le texte en forme avant de l'écrire.",
    "wr_model_title": "IA d'écriture (100 % locale)",
    "wr_model_sub": "Fonctionne dans Voice Typer, sans Ollama ni autre logiciel à installer. "
                    "Téléchargée une seule fois, puis tout reste hors ligne.",
    "wr_load": "Télécharger et charger", "wr_unload": "Libérer la mémoire",
    "wr_keep_loaded": "Garder l'IA chargée en mémoire (mise en forme instantanée)",
    "wr_st_loading": "Chargement de l'IA d'écriture…",
    "wr_st_downloading": "Téléchargement de {name} ({size})… (une seule fois)",
    "wr_st_gpu": "✓ Prête — carte graphique (GPU)", "wr_st_cpu": "✓ Prête — processeur (CPU, plus lent)",
    "wr_st_disk": "Téléchargée — se charge à la première utilisation",
    "wr_st_missing": "Pas encore téléchargée ({size})",
    "wr_dl_title": "Télécharger l'IA d'écriture",
    "wr_dl_confirm": "Télécharger {name} ({size}) ? C'est fait une seule fois ; ensuite tout fonctionne hors ligne.",
    "wr_presets_title": "Préréglages",
    "wr_presets_sub": "Maintenez le raccourci d'un préréglage pour dicter : le texte est réécrit selon ses consignes, "
                      "puis écrit dans l'application active.",
    "wr_col_name": "Préréglage", "wr_col_key": "Raccourci",
    "wr_new": "Nouveau", "wr_duplicate": "Dupliquer", "wr_new_name": "Nouveau préréglage",
    "wr_copy_suffix": "(copie)",
    "wr_name": "Nom", "wr_hotkey": "Raccourci", "wr_remove_key": "Retirer",
    "wr_instructions": "Consignes pour l'IA",
    "wr_instructions_hint": "Décrivez le résultat voulu. {signature} sera remplacé par votre signature.",
    "wr_save": "Enregistrer", "wr_saved": "✓ Enregistré",
    "wr_delete_confirm": "Supprimer le préréglage « {name} » ?",
    "wr_reset": "Rétablir les préréglages d'origine",
    "wr_reset_confirm": "Remplacer tous vos préréglages par ceux d'origine ?",
    "wr_signature_title": "Signature",
    "wr_signature_sub": "Ajoutée à la fin des préréglages qui contiennent {signature} (par ex. Courriel).",
    "wr_test_title": "Essayer sans micro",
    "wr_test_sub": "Tapez une dictée brute et voyez le résultat avec les consignes du préréglage sélectionné.",
    "wr_test_btn": "Tester la mise en forme", "wr_test_running": "Mise en forme…",
    "wr_test_sample": "euh donc courriel à monsieur Tremblay pour lui dire que la livraison des pièces est "
                      "retardée à jeudi prochain à cause du fournisseur et aussi demander si la réunion de lundi "
                      "tient toujours sinon on pourrait la déplacer à mardi matin",
    "wr_error": "Mise en forme impossible ({err}). Le texte brut a été écrit.",
    "wr_load_error_title": "IA d'écriture",
    "wr_key_note": "Astuce : une touche comme F2 est réservée à Voice Typer tant qu'elle est assignée "
                   "(F2 ne renommera plus dans l'Explorateur ou Excel).",
    "overlay_rewriting": "Mise en forme : {name}…",
    "status_rewriting": "Mise en forme « {name} »…",
    "home_presets": "Préréglages IA :",
    "hist_copy_raw": "Copier le texte brut (avant IA)",
    "rec_err_taken": "« {combo} » est déjà utilisé par : {what}.",
    "rec_target_main": "la dictée", "rec_target_lang": "le changement de langue",
    "rec_target_paste": "recoller la dernière dictée",
    "paste_last_title": "Recoller la dernière dictée",
    "set_keep_clipboard": "Laisser la dernière dictée dans le presse-papiers (Ctrl+V la recolle)",
    "overlay_pasted": "Dernière dictée recollée",
    "overlay_cancelled": "Dictée annulée", "cancelled": "Dictée annulée (Échap) — rien n'a été écrit.",
    "rec_target_undo": "annuler la dernière dictée",
    "undo_title": "Annuler la dernière dictée",
    "undo_sub": "Efface exactement ce que la dernière dictée a écrit. Marche aussi en disant « efface ça » seul.",
    "help_key_undo": "Effacer la dernière dictée (ou dire « efface ça »)",
    "overlay_undone": "Dernière dictée effacée",
    "undo_done": "Dernière dictée effacée.",
    "undo_no_nothing": "Rien à effacer : aucune dictée récente.",
    "undo_no_done": "La dernière dictée est déjà effacée.",
    "undo_no_too_old": "Rien effacé : la dernière dictée date de plus de 10 minutes.",
    "undo_no_other_window": "Rien effacé : vous n'êtes plus dans la fenêtre de la dernière dictée.",
    "undo_no_typed_since": "Rien effacé : vous avez tapé au clavier depuis (utilisez Ctrl+Z).",
    "undo_no_clicked_since": "Rien effacé : vous avez cliqué depuis, le curseur a pu bouger (utilisez Ctrl+Z).",
    "mic_unplugged": "{name} (débranché — repris dès qu'il revient)",
    "mic_remember_note": "Le micro choisi est retenu : s'il est débranché, celui de Windows prend le relais, "
                         "puis Voice Typer revient au vôtre tout seul dès qu'il est rebranché.",
    "mic_fallback": "Micro « {name} » absent : micro par défaut de Windows utilisé.",
    "mic_back": "Micro « {name} » de retour : il est de nouveau utilisé.",
    "dict_scope": "Dictionnaire :",
    "dict_scope_all": "Général (toutes les applications)",
    "dict_scope_app": "Seulement dans {app}",
    "dict_add_app": "Ajouter une application…",
    "dict_remove_app": "Supprimer ce dictionnaire",
    "dict_remove_confirm": "Supprimer le dictionnaire propre à {app} (ses mots et remplacements) ?",
    "dict_scope_note_all": "Ces mots et remplacements servent partout. Ajoutez une application pour des termes "
                           "qui ne servent que là (ex. noms de clients dans Outlook).",
    "dict_scope_note_app": "Ces entrées s'ajoutent au dictionnaire général quand vous dictez dans cette "
                           "application ; en cas de conflit, ce sont elles qui l'emportent.",
})
STRINGS["en"].update({
    "nav_writing": "AI writing",
    "title_writing": "AI writing",
    "sub_writing": "Dictate with a preset shortcut: a local AI formats the text before typing it.",
    "wr_model_title": "Writing AI (100% local)",
    "wr_model_sub": "Runs inside Voice Typer — no Ollama or other software to install. "
                    "Downloaded once, then everything stays offline.",
    "wr_load": "Download and load", "wr_unload": "Free memory",
    "wr_keep_loaded": "Keep the AI loaded in memory (instant formatting)",
    "wr_st_loading": "Loading the writing AI…",
    "wr_st_downloading": "Downloading {name} ({size})… (only once)",
    "wr_st_gpu": "✓ Ready — graphics card (GPU)", "wr_st_cpu": "✓ Ready — processor (CPU, slower)",
    "wr_st_disk": "Downloaded — loads on first use",
    "wr_st_missing": "Not downloaded yet ({size})",
    "wr_dl_title": "Download the writing AI",
    "wr_dl_confirm": "Download {name} ({size})? This happens once; afterwards everything works offline.",
    "wr_presets_title": "Presets",
    "wr_presets_sub": "Hold a preset's shortcut to dictate: the text is rewritten following its instructions, "
                      "then typed into the active app.",
    "wr_col_name": "Preset", "wr_col_key": "Shortcut",
    "wr_new": "New", "wr_duplicate": "Duplicate", "wr_new_name": "New preset", "wr_copy_suffix": "(copy)",
    "wr_name": "Name", "wr_hotkey": "Shortcut", "wr_remove_key": "Remove",
    "wr_instructions": "Instructions for the AI",
    "wr_instructions_hint": "Describe the result you want. {signature} is replaced by your signature.",
    "wr_save": "Save", "wr_saved": "✓ Saved",
    "wr_delete_confirm": "Delete the preset \"{name}\"?",
    "wr_reset": "Restore default presets",
    "wr_reset_confirm": "Replace all your presets with the default ones?",
    "wr_signature_title": "Signature",
    "wr_signature_sub": "Added at the end of presets containing {signature} (e.g. Email).",
    "wr_test_title": "Try it without a microphone",
    "wr_test_sub": "Type a raw dictation and see the result with the selected preset's instructions.",
    "wr_test_btn": "Test formatting", "wr_test_running": "Formatting…",
    "wr_test_sample": "um so email to mister Smith to tell him the parts delivery is delayed to next thursday "
                      "because of the supplier and also ask if monday's meeting is still on otherwise we could "
                      "move it to tuesday morning",
    "wr_error": "Formatting failed ({err}). The raw text was typed.",
    "wr_load_error_title": "Writing AI",
    "wr_key_note": "Tip: a key like F2 is reserved for Voice Typer while assigned "
                   "(F2 will no longer rename in Explorer or Excel).",
    "overlay_rewriting": "Formatting: {name}…",
    "status_rewriting": "Formatting \"{name}\"…",
    "home_presets": "AI presets:",
    "hist_copy_raw": "Copy raw text (before AI)",
    "rec_err_taken": "\"{combo}\" is already used by: {what}.",
    "rec_target_main": "dictation", "rec_target_lang": "language switching",
    "rec_target_paste": "paste last dictation",
    "paste_last_title": "Paste last dictation again",
    "set_keep_clipboard": "Leave the last dictation on the clipboard (Ctrl+V pastes it again)",
    "overlay_pasted": "Last dictation pasted",
    "overlay_cancelled": "Dictation cancelled", "cancelled": "Dictation cancelled (Esc) — nothing was typed.",
    "rec_target_undo": "undo last dictation",
    "undo_title": "Undo last dictation",
    "undo_sub": "Deletes exactly what the last dictation typed. Also works by saying “delete that” on its own.",
    "help_key_undo": "Delete the last dictation (or say “delete that”)",
    "overlay_undone": "Last dictation deleted",
    "undo_done": "Last dictation deleted.",
    "undo_no_nothing": "Nothing to delete: no recent dictation.",
    "undo_no_done": "The last dictation is already deleted.",
    "undo_no_too_old": "Nothing deleted: the last dictation is more than 10 minutes old.",
    "undo_no_other_window": "Nothing deleted: you are no longer in the window of the last dictation.",
    "undo_no_typed_since": "Nothing deleted: you typed on the keyboard since (use Ctrl+Z).",
    "undo_no_clicked_since": "Nothing deleted: you clicked since, the cursor may have moved (use Ctrl+Z).",
    "mic_unplugged": "{name} (unplugged — used again once it is back)",
    "mic_remember_note": "Your microphone choice is remembered: if it is unplugged the Windows default takes over, "
                         "then Voice Typer switches back to yours by itself as soon as it is reconnected.",
    "mic_fallback": "Microphone “{name}” missing: using the Windows default.",
    "mic_back": "Microphone “{name}” is back and in use again.",
    "dict_scope": "Dictionary:",
    "dict_scope_all": "General (all applications)",
    "dict_scope_app": "Only in {app}",
    "dict_add_app": "Add an application…",
    "dict_remove_app": "Delete this dictionary",
    "dict_remove_confirm": "Delete the dictionary for {app} (its words and replacements)?",
    "dict_scope_note_all": "These words and replacements apply everywhere. Add an application for terms only "
                           "used there (e.g. client names in Outlook).",
    "dict_scope_note_app": "These entries are added to the general dictionary when you dictate in this "
                           "application; on conflicts, they win.",
})


# Help page, voice commands, live preview, rewrite selection, per-app presets, diagnostics
STRINGS["fr"].update({
    "nav_help": "Aide & commandes", "title_help": "Aide & commandes",
    "sub_help": "Toutes les commandes vocales et tous les raccourcis, au même endroit.",
    "help_voice_title": "Commandes vocales",
    "help_voice_sub": "Dites ces mots pendant la dictée : ils sont remplacés par la mise en forme correspondante.",
    "help_voice_enable": "Activer les commandes vocales",
    "help_col_say": "Dites…", "help_col_get": "Vous obtenez",
    "help_voice_example": "Exemple : « Bonjour Julie virgule à la ligne merci pour ton message point "
                          "d'exclamation » → « Bonjour Julie, ⏎ Merci pour ton message ! ». Les expressions "
                          "ambiguës (comme « deux points ») ne sont volontairement pas des commandes.",
    "help_keys_title": "Raccourcis clavier",
    "help_keys_sub": "Vos raccourcis actuels. Modifiez-les sur l'Accueil ou la page Écriture IA.",
    "help_key_dictate": "Dicter (texte tel quel)", "help_key_esc": "Annuler la dictée en cours",
    "help_key_preset": "Dicter avec le préréglage « {name} »",
    "help_key_rewrite": "Réécrire le texte sélectionné avec l'IA",
    "help_key_paste": "Recoller la dernière dictée", "help_key_lang": "Changer de langue",
    "help_keys_note": "« Aucun » = pas encore assigné.",
    "rw_title": "Réécrire le texte sélectionné",
    "rw_sub": "Surlignez du texte déjà écrit dans n'importe quelle application, appuyez sur ce raccourci : "
              "l'IA le remplace par la version réécrite selon le préréglage choisi. Ctrl+Z annule.",
    "rw_with": "avec le préréglage", "rec_target_rewrite": "réécrire la sélection",
    "rw_empty": "Aucun texte sélectionné : surlignez d'abord le texte à réécrire.",
    "rw_empty_short": "Sélectionnez d'abord du texte",
    "ap_title": "Préréglage automatique selon l'application",
    "ap_sub": "Avec le raccourci de dictée normal, le préréglage associé à l'application active s'applique "
              "tout seul (ex. Outlook → Courriel, Teams → Message rapide). Ailleurs, le texte reste tel quel.",
    "ap_col_app": "Application", "ap_col_preset": "Préréglage",
    "ap_add": "Associer une application…", "ap_dlg_app": "Application",
    "ap_dlg_hint": "Choisissez dans la liste ou tapez le nom du programme (ex. « thunderbird.exe »). "
                   "Le Gestionnaire des tâches → Détails affiche le nom de chaque programme.",
    "set_live": "Afficher la transcription en temps réel pendant que je parle",
    "set_live_note": "Le texte apparaît dans l'indicateur flottant. Plus fluide avec une carte graphique NVIDIA ; "
                     "sur processeur seul, l'aperçu est plus lent et utilise plus le processeur.",
})
STRINGS["en"].update({
    "nav_help": "Help & commands", "title_help": "Help & commands",
    "sub_help": "Every voice command and shortcut in one place.",
    "help_voice_title": "Voice commands",
    "help_voice_sub": "Say these words while dictating: they are replaced by the matching formatting.",
    "help_voice_enable": "Enable voice commands",
    "help_col_say": "Say…", "help_col_get": "You get",
    "help_voice_example": "Example: “Hi Julie comma new line thanks for your message exclamation mark” → "
                          "“Hi Julie, ⏎ Thanks for your message!”. Ambiguous phrases (like “period”) "
                          "are deliberately not commands.",
    "help_keys_title": "Keyboard shortcuts",
    "help_keys_sub": "Your current shortcuts. Change them on Home or the AI writing page.",
    "help_key_dictate": "Dictate (text as is)", "help_key_esc": "Cancel the dictation in progress",
    "help_key_preset": "Dictate with the \"{name}\" preset",
    "help_key_rewrite": "Rewrite the selected text with AI",
    "help_key_paste": "Paste the last dictation again", "help_key_lang": "Switch language",
    "help_keys_note": "\"None\" = not assigned yet.",
    "rw_title": "Rewrite the selected text",
    "rw_sub": "Highlight text you already wrote in any app and press this shortcut: the AI replaces it with "
              "the version rewritten by the chosen preset. Ctrl+Z undoes it.",
    "rw_with": "with preset", "rec_target_rewrite": "rewrite selection",
    "rw_empty": "No text selected: highlight the text to rewrite first.",
    "rw_empty_short": "Select some text first",
    "ap_title": "Automatic preset per application",
    "ap_sub": "With the normal dictation shortcut, the preset linked to the active app applies by itself "
              "(e.g. Outlook → Email, Teams → Quick message). Elsewhere, text stays as dictated.",
    "ap_col_app": "Application", "ap_col_preset": "Preset",
    "ap_add": "Link an application…", "ap_dlg_app": "Application",
    "ap_dlg_hint": "Pick from the list or type the program name (e.g. \"thunderbird.exe\"). "
                   "Task Manager → Details shows each program's name.",
    "set_live": "Show the transcription in real time while I speak",
    "set_live_note": "Text appears in the floating indicator. Smoothest with an NVIDIA graphics card; on a CPU "
                     "only, the preview is slower and uses more processor.",
})


# Welcome assistant + diagnostics
STRINGS["fr"].update({
    "diag_export": "Exporter un diagnostic…",
    "diag_done": "Diagnostic enregistré :\n{path}\n\nIl ne contient ni historique, ni audio, ni signature. "
                 "Envoyez-le à la personne qui vous aide.",
    "wizard_open": "Relancer l'assistant de bienvenue",
    "wz_title": "Bienvenue dans Voice Typer", "wz_next": "Suivant", "wz_back": "Retour", "wz_finish": "Terminer",
    "wz_skip": "Passer l'assistant", "wz_step": "Étape {n} sur {total}",
    "wz_welcome_title": "Bienvenue !",
    "wz_welcome_sub": "Voice Typer écrit ce que vous dites, dans n'importe quelle application. "
                      "Quelques réglages rapides, et c'est parti.",
    "wz_welcome_1": "Maintenez un raccourci, parlez, relâchez : le texte s'écrit là où se trouve votre curseur.",
    "wz_welcome_2": "100 % sur votre ordinateur : rien n'est envoyé sur Internet.",
    "wz_welcome_3": "Une IA locale peut mettre vos dictées en forme (courriels, messages, notes).",
    "wz_welcome_4": "Tout se modifie ensuite dans la fenêtre (icône près de l'horloge).",
    "wz_speak_title": "Dans quelle langue dictez-vous ?",
    "wz_speak_sub": "Choisir votre langue rend la reconnaissance plus rapide et plus précise.",
    "wz_speak_fr": "Surtout en français", "wz_speak_en": "Surtout en anglais",
    "wz_speak_both": "Les deux (l'app détecte la langue automatiquement)",
    "wz_models_title": "Les modèles d'IA",
    "wz_hw_gpu": "Carte graphique détectée : {name}. Les modèles tourneront dessus, très rapidement.",
    "wz_hw_cpu": "Pas de carte graphique NVIDIA : les modèles tourneront sur le processeur. "
                 "Nous recommandons donc des modèles légers.",
    "wz_speech_model": "Reconnaissance vocale",
    "wz_tag_best": "le meilleur pour vous", "wz_tag_balanced": "équilibré", "wz_tag_fast": "le plus rapide",
    "wz_tag_precise": "plus précis, plus lourd", "wz_recommended": "Recommandé", "wz_on_pc": "déjà sur le PC",
    "wz_writing_title": "Écriture IA (optionnel)",
    "wz_writing_check": "Installer l'IA d'écriture — {name} ({size})",
    "wz_models_note": "Les modèles se téléchargent une seule fois, en arrière-plan, après l'assistant. "
                      "Vous pourrez en changer à tout moment (pages Modèles IA et Écriture IA).",
    "wz_mic_title": "Votre micro",
    "wz_mic_sub": "Choisissez le micro à utiliser, puis parlez : la barre doit bouger.",
    "wz_mic_speak": "Parlez pour tester…",
    "wz_key_title": "Votre raccourci de dictée",
    "wz_key_sub": "C'est la touche à maintenir pour parler. Choisissez-en une facile à atteindre "
                  "et que vous n'utilisez pas déjà (ex. F1, F9, Ctrl droit).",
    "wz_key_tips": "Astuces : Échap annule une dictée en cours. F2, F3 et F4 dictent avec mise en forme IA "
                   "(courriel, message, notes). Toutes les commandes sont dans « Aide & commandes ».",
    "wz_done_title": "Tout est prêt !",
    "wz_done_sub": "Voici votre configuration. Les modèles se téléchargent maintenant en arrière-plan.",
    "wz_sum_speech": "Reconnaissance vocale", "wz_sum_writing": "Écriture IA", "wz_sum_key": "Raccourci",
    "wz_sum_presets": "Préréglages IA",
    "wz_done_try": "Essayez : ouvrez un document ou un courriel, placez le curseur, maintenez {hotkey} "
                   "et dites « Bonjour, ceci est mon premier essai ».",
})
STRINGS["en"].update({
    "diag_export": "Export a diagnostic…",
    "diag_done": "Diagnostic saved:\n{path}\n\nIt contains no history, audio or signature. "
                 "Send it to whoever is helping you.",
    "wizard_open": "Run the welcome assistant again",
    "wz_title": "Welcome to Voice Typer", "wz_next": "Next", "wz_back": "Back", "wz_finish": "Finish",
    "wz_skip": "Skip the assistant", "wz_step": "Step {n} of {total}",
    "wz_welcome_title": "Welcome!",
    "wz_welcome_sub": "Voice Typer types what you say, in any application. A few quick settings and you're set.",
    "wz_welcome_1": "Hold a shortcut, speak, release: the text appears where your cursor is.",
    "wz_welcome_2": "100% on your computer: nothing is sent over the Internet.",
    "wz_welcome_3": "A local AI can format your dictations (emails, messages, notes).",
    "wz_welcome_4": "Everything can be changed later in the window (icon next to the clock).",
    "wz_speak_title": "Which language do you dictate in?",
    "wz_speak_sub": "Choosing your language makes recognition faster and more accurate.",
    "wz_speak_fr": "Mostly French", "wz_speak_en": "Mostly English",
    "wz_speak_both": "Both (the app detects the language automatically)",
    "wz_models_title": "AI models",
    "wz_hw_gpu": "Graphics card detected: {name}. Models will run on it, very fast.",
    "wz_hw_cpu": "No NVIDIA graphics card: models will run on the processor, so we recommend light models.",
    "wz_speech_model": "Speech recognition",
    "wz_tag_best": "best for you", "wz_tag_balanced": "balanced", "wz_tag_fast": "fastest",
    "wz_tag_precise": "more accurate, heavier", "wz_recommended": "Recommended", "wz_on_pc": "already on this PC",
    "wz_writing_title": "AI writing (optional)",
    "wz_writing_check": "Install the writing AI — {name} ({size})",
    "wz_models_note": "Models download once, in the background, after the assistant. "
                      "You can change them anytime (AI models and AI writing pages).",
    "wz_mic_title": "Your microphone",
    "wz_mic_sub": "Pick the microphone to use, then speak: the bar should move.",
    "wz_mic_speak": "Speak to test…",
    "wz_key_title": "Your dictation shortcut",
    "wz_key_sub": "This is the key you hold to speak. Pick one that's easy to reach and that you don't already "
                  "use (e.g. F1, F9, Right Ctrl).",
    "wz_key_tips": "Tips: Esc cancels a dictation in progress. F2, F3 and F4 dictate with AI formatting "
                   "(email, message, notes). Every command is listed in \"Help & commands\".",
    "wz_done_title": "All set!",
    "wz_done_sub": "Here is your setup. The models are now downloading in the background.",
    "wz_sum_speech": "Speech recognition", "wz_sum_writing": "AI writing", "wz_sum_key": "Shortcut",
    "wz_sum_presets": "AI presets",
    "wz_done_try": "Try it: open a document or an email, place the cursor, hold {hotkey} and say "
                   "\"Hello, this is my first try\".",
})


# Power sharing removed in 0.9.3 (legacy.py): leftover firewall rules
STRINGS["fr"].update({
    "fw_title": "Pare-feu Windows",
    "fw_msg": "Le partage de puissance a été retiré de Voice Typer : l'application n'ouvre plus aucun port réseau.\n\n"
              "Windows garde encore {n} règle(s) de pare-feu qui autorisaient Voice Typer sur le réseau. "
              "Les supprimer maintenant ? Windows va demander l'autorisation administrateur.",
    "fw_failed": "La suppression n'a pas pu être lancée. Vous pouvez retirer les règles « Voice Typer » dans "
                 "Pare-feu Windows Defender → Paramètres avancés → Règles de trafic entrant.",
})
STRINGS["en"].update({
    "fw_title": "Windows Firewall",
    "fw_msg": "Power sharing has been removed from Voice Typer: the app no longer opens any network port.\n\n"
              "Windows still keeps {n} firewall rule(s) that allowed Voice Typer on the network. "
              "Delete them now? Windows will ask for administrator permission.",
    "fw_failed": "The removal could not be started. You can delete the \"Voice Typer\" rules in Windows Defender "
                 "Firewall → Advanced settings → Inbound Rules.",
})


# Automatic updates (updater.py, gui/updates.py)
STRINGS["fr"].update({
    "upd_card": "Mises à jour",
    "upd_current": "Version installée : {version}",
    "upd_auto": "Rechercher automatiquement les mises à jour",
    "upd_check": "Rechercher maintenant",
    "upd_checking": "Recherche…",
    "upd_uptodate": "✓ Voice Typer est à jour ({version}).",
    "upd_available": "Version {version} disponible.",
    "upd_error": "Impossible de vérifier : {err}",
    "upd_note": "La mise à jour se télécharge depuis le dépôt officiel de Voice Typer, est vérifiée (empreinte "
                "SHA-256), puis s'installe en quelques secondes. Vos réglages, votre historique et vos modèles sont conservés.",
    "upd_banner": "Nouvelle version disponible : Voice Typer {version}",
    "upd_size": "Téléchargement : {mb} Mo.",
    "upd_dev": "Version de développement : mettez-la à jour avec git.",
    "upd_install": "Installer maintenant", "upd_later": "Plus tard", "upd_skip": "Ignorer cette version",
    "upd_downloading": "Téléchargement de la mise à jour… {pct} %",
    "upd_installing": "Installation… Voice Typer va redémarrer dans quelques secondes.",
    "upd_failed": "La mise à jour n'a pas pu être installée :\n\n{err}\n\nRéessayez plus tard.",
    "upd_tray": "Voice Typer {version} est disponible. Ouvrez Voice Typer pour l'installer.",
    "upd_tray_item": "Installer la mise à jour {version}",
    "upd_done": "Voice Typer a été mis à jour (version {version}).",
})
STRINGS["en"].update({
    "upd_card": "Updates",
    "upd_current": "Installed version: {version}",
    "upd_auto": "Check for updates automatically",
    "upd_check": "Check now",
    "upd_checking": "Checking…",
    "upd_uptodate": "✓ Voice Typer is up to date ({version}).",
    "upd_available": "Version {version} available.",
    "upd_error": "Could not check: {err}",
    "upd_note": "Updates are downloaded from the official Voice Typer repository, verified (SHA-256), then "
                "installed in a few seconds. Your settings, history and models are kept.",
    "upd_banner": "New version available: Voice Typer {version}",
    "upd_size": "Download: {mb} MB.",
    "upd_dev": "Development copy: update it with git.",
    "upd_install": "Install now", "upd_later": "Later", "upd_skip": "Skip this version",
    "upd_downloading": "Downloading the update… {pct} %",
    "upd_installing": "Installing… Voice Typer will restart in a few seconds.",
    "upd_failed": "The update could not be installed:\n\n{err}\n\nPlease try again later.",
    "upd_tray": "Voice Typer {version} is available. Open Voice Typer to install it.",
    "upd_tray_item": "Install update {version}",
    "upd_done": "Voice Typer was updated (version {version}).",
})


# Live typing (streaming.py)
STRINGS["fr"].update({
    "set_live_typing": "Écrire au fur et à mesure que je parle (là où se trouve le curseur)",
    "set_live_typing_note": "Les mots s'écrivent dès qu'ils sont sûrs ; quand vous relâchez, la fin est corrigée avec la "
                            "transcription complète. Ne cliquez pas ailleurs pendant la dictée. Avec un raccourci qui contient "
                            "Ctrl ou Alt, l'écriture attend que ces touches soient relâchées : une touche seule (F1, F9…) ou le "
                            "mode « Appuyer pour commencer » est plus fluide. Les préréglages IA (F2…) écrivent toujours à la fin. "
                            "Très fluide avec une carte graphique NVIDIA.",
})
STRINGS["en"].update({
    "set_live_typing": "Type as I speak (where the cursor is)",
    "set_live_typing_note": "Words are typed as soon as they are certain; when you release, the end is corrected with the "
                            "full transcription. Don't click elsewhere while dictating. With a shortcut containing Ctrl or "
                            "Alt, typing waits until those keys are released: a single key (F1, F9…) or the \"press to "
                            "start\" mode is smoother. AI presets (F2…) still type at the end. Smoothest with an NVIDIA "
                            "graphics card.",
})

# Settings export / import (transfer.py)
STRINGS["fr"].update({
    "xfer_title": "Transférer vers un autre PC",
    "xfer_sub": "Emportez votre configuration sur un autre ordinateur en un seul fichier",
    "xfer_note": "Contient : dictionnaire (général et par application), préréglages IA et signature, raccourcis, "
                 "choix du modèle et options d'écriture et d'affichage. Ne contient pas : le micro, "
                 "l'historique ni les modèles eux-mêmes (ils se téléchargent sur l'autre PC).",
    "xfer_export": "Exporter mes réglages…",
    "xfer_import": "Importer des réglages…",
    "xfer_exported": "Réglages enregistrés :\n{path}\n\nSur l'autre PC : Réglages → Transférer vers un autre PC → "
                     "Importer des réglages.\n\nLe fichier contient votre dictionnaire et votre signature : "
                     "gardez-le pour vous.",
    "xfer_confirm": "Remplacer les réglages de ce PC par ceux du fichier ?\n\n{count} réglage(s) vont changer "
                    "(dictionnaire, préréglages, raccourcis…). Le micro de ce PC est "
                    "conservé.\n\nVoice Typer va redémarrer pour tout appliquer.",
    "xfer_nothing": "Ce fichier ne change rien : ce PC a déjà les mêmes réglages.",
    "xfer_bad_file": "Ce fichier n'est pas un export de réglages Voice Typer (ou il est abîmé).",
    "xfer_too_new": "Ce fichier vient d'une version plus récente de Voice Typer. Mettez ce PC à jour, puis réessayez.",
    "xfer_file_type": "Réglages Voice Typer",
})
STRINGS["en"].update({
    "xfer_title": "Move to another PC",
    "xfer_sub": "Take your setup to another computer in a single file",
    "xfer_note": "Includes: dictionary (general and per application), AI presets and signature, shortcuts, model "
                 "choice, typing and display options. Does not include: the microphone, "
                 "history or the models themselves (they download on the other PC).",
    "xfer_export": "Export my settings…",
    "xfer_import": "Import settings…",
    "xfer_exported": "Settings saved:\n{path}\n\nOn the other PC: Settings → Move to another PC → Import "
                     "settings.\n\nThe file contains your dictionary and signature: keep it to yourself.",
    "xfer_confirm": "Replace this PC's settings with the ones in the file?\n\n{count} setting(s) will change "
                    "(dictionary, presets, shortcuts…). This PC's microphone is kept.\n\n"
                    "Voice Typer will restart to apply everything.",
    "xfer_nothing": "This file changes nothing: this PC already has the same settings.",
    "xfer_bad_file": "This file is not a Voice Typer settings export (or it is damaged).",
    "xfer_too_new": "This file comes from a newer version of Voice Typer. Update this PC, then try again.",
    "xfer_file_type": "Voice Typer settings",
})


# Floating mic button, filler removal, suggested app presets (features from Voice Typer Mobile)
STRINGS["fr"].update({
    "instance_frozen": "Voice Typer est déjà lancé mais ne répond pas (il est peut-être bloqué en arrière-plan, "
                       "sans fenêtre).\n\nLe fermer et redémarrer Voice Typer ?",
    "instance_still_running": "L'ancienne copie de Voice Typer n'a pas pu être fermée.\nRedémarrez l'ordinateur, "
                              "ou fermez « Voice Typer » dans le Gestionnaire des tâches (Ctrl+Maj+Échap).",
    "close_ask": "Fermer la fenêtre…\n\nGarder Voice Typer actif : la fenêtre disparaît, mais les raccourcis et le "
                 "bouton micro continuent de marcher (icône près de l'horloge).\n\nQuitter : Voice Typer s'arrête "
                 "complètement.\n\nVotre choix est retenu (modifiable dans Réglages).",
    "close_keep": "Garder actif", "close_quit": "Quitter",
    "set_close": "Quand je ferme la fenêtre",
    "set_close_tray": "Garder Voice Typer actif près de l'horloge (les raccourcis continuent de marcher)",
    "set_close_quit": "Quitter complètement Voice Typer",
    "set_close_ask": "Me demander",
    "set_remove_fillers": "Retirer les hésitations (euh, hum…) et les mots répétés",
    "set_mic_button": "Bouton micro flottant (clic = dicter, clic droit = menu)",
    "set_mic_button_note": "Un rond vert toujours visible, à déplacer où vous voulez : cliquez pour commencer, "
                           "recliquez pour finir. Le texte va dans l'application où vous écriviez.",
    "report_btn": "Signaler un problème…",
    "report_intro": "Que s'est-il passé ? Décrivez en quelques mots ce que vous faisiez et ce qui n'a pas marché.",
    "report_privacy": "Un fichier de diagnostic sera joint : réglages et journal, sans votre historique, "
                      "sans audio, sans votre dictionnaire ni votre signature. Vous verrez le courriel avant de "
                      "l'envoyer.",
    "report_send": "Préparer le courriel",
    "report_done_outlook": "Le courriel est prêt dans Outlook, avec le diagnostic joint : relisez-le puis "
                           "cliquez sur Envoyer.\n\nS'il ne s'est pas ouvert, écrivez à {email} en joignant :\n{path}",
    "report_done_mailto": "Votre logiciel de courriel s'est ouvert. Joignez-y le fichier de diagnostic (son dossier "
                          "vient de s'ouvrir), puis envoyez.\n\nAdresse : {email}\nFichier : {path}",
    "report_done_none": "Aucun logiciel de courriel n'a pu s'ouvrir. Écrivez à {email} depuis votre messagerie "
                        "en joignant ce fichier (son dossier vient de s'ouvrir) :\n{path}",
    "upd_required_banner": "Mise à jour importante : Voice Typer {version} s'installe…",
    "upd_required_tray": "Mise à jour importante de Voice Typer ({version}) : elle s'installe dès que vous ne "
                         "dictez pas. Voice Typer redémarre tout seul.",
    "mb_dictate_with": "Dicter avec…",
    "mb_plain": "Dictée normale (sans IA)",
    "mb_no_preset": "Aucun préréglage",
    "mb_always_in": "Toujours dans {app}",
    "mb_language": "Langue : {lang}",
    "mb_repaste": "Recoller la dernière dictée",
    "mb_undo": "Annuler la dernière dictée",
    "mb_open": "Ouvrir Voice Typer",
    "mb_hide": "Masquer le bouton",
    "mb_hidden": "Bouton masqué — réactivable dans Réglages",
    "ap_suggest": "Ajouter les suggestions",
    "ap_suggest_hint": "Outlook → Courriel, Teams et Slack → Message rapide, OneNote → Notes",
    "ap_suggest_none": "Les suggestions sont déjà toutes associées.",
})
STRINGS["en"].update({
    "instance_frozen": "Voice Typer is already running but does not respond (it may be stuck in the background, "
                       "with no window).\n\nClose it and restart Voice Typer?",
    "instance_still_running": "The old copy of Voice Typer could not be closed.\nRestart the computer, or end "
                              "\"Voice Typer\" in Task Manager (Ctrl+Shift+Esc).",
    "close_ask": "Closing the window…\n\nKeep Voice Typer running: the window goes away, but the shortcuts and the "
                 "mic button keep working (icon next to the clock).\n\nQuit: Voice Typer stops completely.\n\n"
                 "Your choice is remembered (changeable in Settings).",
    "close_keep": "Keep running", "close_quit": "Quit",
    "set_close": "When I close the window",
    "set_close_tray": "Keep Voice Typer running next to the clock (shortcuts keep working)",
    "set_close_quit": "Quit Voice Typer completely",
    "set_close_ask": "Ask me",
    "set_remove_fillers": "Remove hesitations (um, uh…) and repeated words",
    "set_mic_button": "Floating mic button (click = dictate, right-click = menu)",
    "set_mic_button_note": "An always-visible green circle you can move anywhere: click to start, click again "
                           "to finish. The text goes to the application you were typing in.",
    "report_btn": "Report a problem…",
    "report_intro": "What happened? Describe in a few words what you were doing and what went wrong.",
    "report_privacy": "A diagnostic file will be attached: settings and log, without your history, audio, "
                      "dictionary or signature. You will see the e-mail before sending it.",
    "report_send": "Prepare the e-mail",
    "report_done_outlook": "The e-mail is ready in Outlook with the diagnostic attached: read it, then click "
                           "Send.\n\nIf it did not open, write to {email} and attach:\n{path}",
    "report_done_mailto": "Your e-mail app opened. Attach the diagnostic file (its folder just opened), then "
                          "send.\n\nAddress: {email}\nFile: {path}",
    "report_done_none": "No e-mail app could be opened. Write to {email} from your mailbox and attach this file "
                        "(its folder just opened):\n{path}",
    "upd_required_banner": "Important update: Voice Typer {version} is installing…",
    "upd_required_tray": "Important Voice Typer update ({version}): it installs as soon as you are not dictating. "
                         "Voice Typer restarts by itself.",
    "mb_dictate_with": "Dictate with…",
    "mb_plain": "Plain dictation (no AI)",
    "mb_no_preset": "No preset",
    "mb_always_in": "Always in {app}",
    "mb_language": "Language: {lang}",
    "mb_repaste": "Paste the last dictation again",
    "mb_undo": "Undo the last dictation",
    "mb_open": "Open Voice Typer",
    "mb_hide": "Hide the button",
    "mb_hidden": "Button hidden — turn it back on in Settings",
    "ap_suggest": "Add the suggestions",
    "ap_suggest_hint": "Outlook → Email, Teams and Slack → Quick message, OneNote → Bullet notes",
    "ap_suggest_none": "All the suggestions are already linked.",
})


def tr(lang: str, key: str, **kwargs) -> str:
    text = STRINGS.get(lang, STRINGS["en"]).get(key) or STRINGS["en"].get(key, key)
    return text.format(**kwargs) if kwargs else text


def pretty_hotkey(lang: str, combo: str) -> str:
    names = KEY_NAMES.get(lang, KEY_NAMES["en"])
    parts = [p.strip() for p in combo.split("+") if p.strip()]
    return " + ".join(names.get(p, p.upper() if len(p) <= 3 else p.title()) for p in parts)
