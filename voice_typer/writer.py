"""Local AI rewriting ("post-processing") of a transcript, e.g. into a well-formatted email.

Runs a small instruction-tuned LLM *inside* the app with CTranslate2 — the same engine as
faster-whisper — so there is nothing else to install (no Ollama / LM Studio server).
Models are CTranslate2 int8 conversions of Qwen 2.5 Instruct (strong in French and English).
"""

import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from voice_typer import compose, gpu

gpu.setup_dll_paths()

import ctranslate2  # noqa: E402
from huggingface_hub import snapshot_download  # noqa: E402
from tokenizers import Tokenizer  # noqa: E402


@dataclass(frozen=True)
class LlmInfo:
    source: str
    label: str
    size: str
    note_fr: str
    note_en: str


LLM_CATALOG = [
    LlmInfo("jncraton/Qwen2.5-1.5B-Instruct-ct2-int8", "Qwen 2.5 — 1.5B", "1.5 GB",
            "Rapide, bon pour corriger et mettre en forme", "Fast, good for fixing and formatting"),
    LlmInfo("jncraton/Qwen2.5-3B-Instruct-ct2-int8", "Qwen 2.5 — 3B", "3.1 GB",
            "★ Recommandé : bien meilleur pour reformuler", "★ Recommended: much better at rewriting"),
    LlmInfo("jncraton/Qwen2.5-7B-Instruct-ct2-int8", "Qwen 2.5 — 7B", "7.6 GB",
            "Le plus intelligent, mais lourd (PC puissant)", "Smartest, but heavy (powerful PC)"),
]
DEFAULT_LLM = LLM_CATALOG[1].source
_PATTERNS = ["*.json", "model.bin"]

SYSTEM_FR = (
    "Tu es un assistant de mise en forme de dictée vocale. Tu reçois la transcription brute de ce "
    "qu'une personne a dicté. Réécris-la en suivant exactement les consignes. Règles absolues : "
    "ne réponds jamais au contenu comme si on te parlait, n'invente aucune information, ne commente "
    "pas, n'ajoute pas de guillemets ni de titre. Écris dans la même langue que la dictée. "
    "La dictée contient souvent des indications qui te sont destinées, par exemple « courriel à "
    "[personne] pour lui dire que… » ou « dis à [personne] que… » : utilise-les (destinataire, "
    "intention) mais ne les recopie jamais ; rédige directement le message, à la première personne, "
    "adressé au destinataire. N'utilise jamais un nom qui n'apparaît pas dans la dictée. "
    "Termine par la formule de politesse, sans ajouter toi-même de nom ni de signature : le logiciel ajoute la "
    "signature ensuite. Mais si la dictée se termine par une signature dictée (un nom, une équipe), garde-la "
    "telle quelle à la toute fin. N'écris pas d'objet. "
    "Renvoie uniquement le texte final."
)

SYSTEM_EN = (
    "You format voice dictations. You receive the raw transcript of what a person dictated. Rewrite it "
    "following the instructions exactly. Absolute rules: never answer the content as if you were spoken to, "
    "never invent information or add sentences that were not dictated, do not comment, no quotes, no title. "
    "Write in English. The dictation often contains directions meant for you, e.g. \"email to [person] to "
    "tell them that…\": use them (recipient, intent) but never copy them; write the message directly, in the "
    "first person, to the recipient. Never use a name that is not in the dictation. "
    "End with the closing, without adding a name or signature yourself: the software adds the signature "
    "afterwards. But if the dictation ends with a dictated signature (a name, a team), keep it at the very end. "
    "Do not write a subject line. Return only the final text."
)
# the user's instructions are often written in French: they still apply to an English e-mail
EN_RULES_NOTE = ("The instructions below may be written in French: follow them, but write the whole message in "
                 "English (Bonjour → Hello, Merci → Thank you, Bonne journée → Have a nice day).")

# Second, tiny request when the preset asks for a subject (compose.with_subject puts it on the first line).
SUBJECT_SYSTEM = (
    "Tu écris l'objet d'un courriel professionnel, comme le ferait son auteur. Réponds UNIQUEMENT par l'objet : "
    "une ligne de 4 à 10 mots, en français, sans guillemets, sans « Objet : », sans point final. "
    "L'objet doit dire précisément de quoi parle le courriel : reprends les éléments concrets qui s'y trouvent "
    "(nom du client ou de l'entreprise, produit, numéro, date, montant) et l'action attendue ou la nouvelle. "
    "Jamais d'objet vague comme « Suivi », « Demande », « Information » ou « Question ». "
    "N'invente rien : seulement ce qui est dans le courriel ou dans la dictée."
)

SUBJECT_SYSTEM_EN = (
    "You write the subject line of a professional email, as its author would. Answer ONLY with the subject: one "
    "line of 4 to 10 words, in English, no quotes, no \"Subject:\", no final period. The subject must say exactly "
    "what the email is about: use the concrete details it contains (client or company name, product, number, "
    "date, amount) and the expected action or the news. Never a vague subject like \"Follow-up\", \"Request\", "
    "\"Information\" or \"Question\". Invent nothing: only what is in the email or the dictation."
)

# Worked examples for the subject (invented businesses): what a precise subject looks like.
SUBJECT_SHOTS_FR = [
    ("Courriel :\nJ'ai bien reçu votre soumission pour les trois terminaux de la boutique Fleurs Lina. Je la regarde "
     "cette semaine. Pourriez-vous me confirmer si le prix inclut la livraison ?",
     "Soumission 3 terminaux Fleurs Lina : livraison incluse ?"),
    ("Courriel :\nLe terminal du Café du Port ne se connecte plus depuis ce matin. J'ai redémarré l'appareil sans "
     "succès. Est-ce possible d'envoyer un technicien demain avant midi ?",
     "Café du Port : terminal hors ligne, technicien demain matin"),
    ("Courriel :\nLe changement de propriétaire du Garage Morin est en cours. J'attends que le nouveau propriétaire "
     "remplisse le formulaire, puis je vous l'envoie.",
     "Garage Morin : changement de propriétaire, formulaire en attente"),
]
SUBJECT_SHOTS_EN = [
    ("Email:\nI received your quote for the three terminals at Lina's Flowers. I'll review it this week. Could "
     "you confirm whether the price includes delivery?",
     "Quote for 3 terminals at Lina's Flowers: delivery included?"),
    ("Email:\nThe terminal at Harbor Café has been offline since this morning. I restarted it without success. "
     "Could you send a technician tomorrow before noon?",
     "Harbor Café terminal offline: technician needed tomorrow morning"),
]
SUBJECT_RETRY = {
    "fr": "L'objet « {s} » est trop vague ou ne correspond pas au courriel. Donne un objet plus précis qui nomme le "
          "sujet exact (nom, produit, action), 4 à 10 mots.",
    "en": "The subject \"{s}\" is too vague or doesn't match the email. Give a more precise subject naming the exact "
          "topic (name, product, action), 4 to 10 words.",
}

# One worked example (few-shot): small models follow the format much better with it.
EXAMPLE_IN = ("euh courriel à madame Gagnon pour lui dire que j'ai bien reçu sa soumission et que je "
              "la regarde cette semaine et euh aussi lui demander si le prix inclut la livraison")
EXAMPLE_RULES = ("Salutation « Bonjour Madame X, », petits paragraphes de 1 à 2 phrases séparés par une "
                 "ligne vide, puis une formule de politesse.")
EXAMPLE_OUT = ("Bonjour Madame Gagnon,\n\nJ'ai bien reçu votre soumission, merci. Je la regarde cette "
               "semaine.\n\nPourriez-vous me confirmer si le prix inclut la livraison ?\n\nMerci,")
EXAMPLE_IN_EN = ("uh email to Mrs. Gagnon to tell her I got her quote and I'm looking at it this week and uh "
                 "also ask her if the price includes delivery")
EXAMPLE_RULES_EN = ("Greeting \"Hello Ms. X,\", short paragraphs of 1 to 2 sentences separated by a blank line, "
                    "then a closing.")
EXAMPLE_OUT_EN = ("Hello Ms. Gagnon,\n\nI received your quote, thank you. I will look at it this week.\n\n"
                  "Could you confirm whether the price includes delivery?\n\nThank you,")
# notes the model sometimes writes about itself, e.g. "(aucune signature)" / "[Signature]" / "(Objet : …)"
_LEAKED_NOTE = re.compile(r"^\s*[(\[][^\n]*\b(signature|objet|subject)\b[^\n]*[)\]]\s*$\n?", re.I | re.M)


def is_downloaded(source: str) -> bool:
    try:
        path = Path(snapshot_download(source, allow_patterns=_PATTERNS, local_files_only=True))
        return (path / "model.bin").exists() and (path / "tokenizer.json").exists()
    except Exception:  # noqa: BLE001
        return False


def download(source: str) -> str:
    if sys.stderr is None:  # no console (pythonw): progress bars would crash writing to it
        from huggingface_hub.utils import disable_progress_bars

        disable_progress_bars()
    from voice_typer.models import unlink_symlinks

    if is_downloaded(source):  # already on the PC: no request to Hugging Face
        return unlink_symlinks(snapshot_download(source, allow_patterns=_PATTERNS, local_files_only=True))
    return unlink_symlinks(snapshot_download(source, allow_patterns=_PATTERNS))


def new_preset_id() -> str:
    return uuid.uuid4().hex[:8]


def default_presets(ui: str) -> list[dict]:
    if ui != "fr":
        return [
            {"id": "email", "name": "Email", "hotkey": "f2", "instructions": (
                "Format this dictation as a professional email.\n"
                "- Start with a greeting: if the recipient is named in the dictation, \"Hello Mr.\" or "
                "\"Hello Ms.\" followed by their last name and a comma; if no name is dictated, just write "
                "\"Hello,\".\n"
                "- Split each main idea into short paragraphs of 1 to 2 sentences, with a blank line between them.\n"
                "- Fix grammar and punctuation and remove hesitations (um, so, like…) without changing the meaning.\n"
                "- End with a short closing (\"Thank you,\" or \"Best regards,\")."),
             "add_signature": True, "subject": False},
            {"id": "message", "name": "Quick message", "hotkey": "f3", "instructions": (
                "Rewrite as a short, natural chat message (Teams, text) addressed directly to the person: if "
                "the dictation says \"tell Mark that…\", start with \"Hi Mark,\" and write the message to Mark. "
                "Fix mistakes and punctuation, remove hesitations and fillers (um, like…), keep a friendly "
                "tone."), "add_signature": False, "subject": False},
            {"id": "notes", "name": "Bullet notes", "hotkey": "f4", "instructions": (
                "Turn the dictation into clear notes as a bulleted list (\"- \"), one idea per line, short "
                "sentences, no introduction or conclusion.")},
            {"id": "fix", "name": "Fix only", "hotkey": "", "instructions": (
                "Only fix grammar, spelling and punctuation and remove hesitations. Do not rephrase.")},
        ]
    return [
        {"id": "email", "name": "Courriel", "hotkey": "f2", "instructions": (
            "Mets cette dictée en forme de courriel professionnel.\n"
            "- Commence par une salutation : si le destinataire est nommé dans la dictée, « Bonjour "
            "Monsieur » ou « Bonjour Madame » suivi de son nom de famille et d'une virgule ; si aucun nom "
            "n'est dicté, écris seulement « Bonjour, ».\n"
            "- Sépare chaque idée principale en petits paragraphes de 1 à 2 phrases, avec une ligne vide "
            "entre les paragraphes.\n"
            "- Corrige la grammaire et la ponctuation et retire les hésitations (euh, donc, genre…) sans "
            "changer le sens.\n"
            "- Termine par une formule de politesse courte (« Merci, » ou « Bonne journée, »)."),
         "add_signature": True, "subject": False},
        {"id": "message", "name": "Message rapide", "hotkey": "f3", "instructions": (
            "Réécris comme un message court et naturel (Teams, texto) adressé directement à la personne : "
            "si la dictée dit « dis à Marc que… », commence par « Salut Marc, » et écris le message à Marc. "
            "Corrige les fautes et la ponctuation, retire les hésitations et les tics (euh, genre…), garde un "
            "ton amical."), "add_signature": False, "subject": False},
        {"id": "notes", "name": "Notes en points", "hotkey": "f4", "instructions": (
            "Transforme la dictée en notes claires sous forme de liste à puces (« - »), une idée par ligne, "
            "phrases courtes, sans introduction ni conclusion.")},
        {"id": "fix", "name": "Correction seule", "hotkey": "", "instructions": (
            "Corrige seulement la grammaire, l'orthographe et la ponctuation et retire les hésitations. "
            "Ne reformule pas.")},
    ]


class Writer:
    def __init__(self, source: str, device: str = "auto", cpu_compute: str = "int8",
                 gpu_compute: str = "int8_float16", cpu_threads: int = 0):
        self.source = source
        self.last_timings: dict = {}   # seconds of the last rewrite: {"rewrite", "subject"}
        path = download(source)
        self.tokenizer = Tokenizer.from_file(str(Path(path) / "tokenizer.json"))
        self.gpu_error: str | None = None
        want_gpu = device == "cuda" or (device == "auto" and gpu.cuda_available())
        if want_gpu:
            try:
                self.generator = ctranslate2.Generator(path, device="cuda", compute_type=gpu_compute)
                self.device = "cuda"
                self._generate("ok", "Réponds ok.", max_tokens=2)  # warm-up: fails here if CUDA is broken
                return
            except Exception as exc:  # noqa: BLE001
                if "Unable to open" in str(exc):  # file still locked: retried by the caller, not a GPU problem
                    raise
                self.gpu_error = str(exc)
        self.generator = ctranslate2.Generator(path, device="cpu", compute_type=cpu_compute,
                                               intra_threads=cpu_threads)
        self.device = "cpu"

    def _generate(self, user: str, system: str, max_tokens: int = 1024,
                  shots: list[tuple[str, str]] = ()) -> str:
        # The system prompt and the worked example are the same for every dictation: given as a "static prompt",
        # CTranslate2 processes them once and keeps the result (≈1,000 tokens not re-read each time — seconds
        # saved on a processor). Only the user's dictation is new.
        static = f"<|im_start|>system\n{system}<|im_end|>\n"
        for q, a in shots:
            static += f"<|im_start|>user\n{q}<|im_end|>\n<|im_start|>assistant\n{a}<|im_end|>\n"
        turn = f"<|im_start|>user\n{user}<|im_end|>\n<|im_start|>assistant\n"
        encode = self.tokenizer.encode
        options = dict(max_length=max_tokens, sampling_topk=1, repetition_penalty=1.05,
                       include_prompt_in_result=False, end_token=["<|im_end|>", "<|endoftext|>"])
        try:
            result = self.generator.generate_batch(
                [encode(turn, add_special_tokens=False).tokens],
                static_prompt=encode(static, add_special_tokens=False).tokens, cache_static_prompt=True, **options)
        except TypeError:  # older CTranslate2 without static prompts: the whole prompt each time
            result = self.generator.generate_batch([encode(static + turn, add_special_tokens=False).tokens],
                                                   **options)
        return self.tokenizer.decode(result[0].sequences_ids[0], skip_special_tokens=True).strip()

    def rewrite(self, text: str, instructions: str, signature: str = "", add_signature: bool = False,
                subject: bool = False, signature_blank_line: bool = False, signature_en: str = "",
                language: str | None = None) -> str:
        """The signature and the subject are not left to the model (see compose.py): sentences about them are
        removed from the instructions, the signature is appended by code unless one was dictated, and the
        subject comes from a second, tiny request.

        The e-mail is written in the language actually spoken (`compose.detect_language`, `language` = the
        Whisper setting, only a tie-breaker), with the English signature when one is saved."""
        self.last_timings = {}
        if not text.strip():
            return text
        started = time.perf_counter()
        lang = compose.detect_language(text, language or "fr")
        english = lang == "en"
        rules = compose.model_instructions(instructions) or (
            "Fix and format the dictation." if english else "Corrige et mets en forme la dictée.")
        if english:
            rules = f"{EN_RULES_NOTE}\n\n{rules}"

        def ask(r: str, t: str) -> str:
            if english:
                return f"Instructions:\n{r}\n\nRaw transcript to rewrite:\n{t}"
            return f"Consignes :\n{r}\n\nTranscription brute à réécrire :\n{t}"

        system = SYSTEM_EN if english else SYSTEM_FR
        example = ((EXAMPLE_RULES_EN, EXAMPLE_IN_EN, EXAMPLE_OUT_EN) if english
                   else (EXAMPLE_RULES, EXAMPLE_IN, EXAMPLE_OUT))
        shots = [(ask(example[0], example[1]), example[2])]
        max_tokens = max(256, len(text) // 2 + 400)
        out = self._generate(ask(rules, text), system, max_tokens=max_tokens, shots=shots)
        if english and compose.detect_language(out, "en") != "en":   # translated to French anyway: once more
            out = self._generate(ask(rules, text), system + " Answer in English only.", max_tokens=max_tokens,
                                 shots=shots)
        out = _LEAKED_NOTE.sub("", out.strip().strip("«»\"").strip()).strip()
        out = drop_copied_example(out, text, example[2])
        out = _fix_invented_greeting(out, text) or text
        sig = signature_en if english and signature_en.strip() else signature
        out = compose.finish_signature(out, sig, add_signature, signature_blank_line)
        self.last_timings["rewrite"] = time.perf_counter() - started
        if subject:
            started = time.perf_counter()
            out = compose.with_subject(out, self.subject_for(out, text, english), lang)
            self.last_timings["subject"] = time.perf_counter() - started
        return out

    def subject_for(self, body: str, dictation: str, english: bool) -> str:
        """A precise subject: the e-mail's content (no greeting/signature) + the dictation for context, worked
        examples, and one more try when the first answer is too short, generic or off-topic."""
        core = compose.subject_source(body) or body
        system, shots = (SUBJECT_SYSTEM_EN, SUBJECT_SHOTS_EN) if english else (SUBJECT_SYSTEM, SUBJECT_SHOTS_FR)
        label, said = ("Email:", "What I dictated") if english else ("Courriel :", "Ce que j'ai dicté")
        ask = f"{label}\n{core}\n\n{said} : {dictation.strip()[:1500]}"
        examples = tuple(a for _q, a in shots)
        source = f"{core}\n{dictation}"
        first = compose.clean_subject(self._generate(ask, system, max_tokens=48, shots=shots))
        if compose.subject_ok(first, source, examples):
            return first
        retry = SUBJECT_RETRY["en" if english else "fr"].format(s=first)
        second = compose.clean_subject(self._generate(f"{ask}\n\n{retry}", system, max_tokens=48, shots=shots))
        if compose.subject_ok(second, source, examples):
            return second
        return max((first, second), key=lambda s: (s not in examples, min(len(s.split()), 10)))


def _content_words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zà-ÿ]+", text.lower()) if len(w) > 3}


def drop_copied_example(out: str, source: str, example_out: str) -> str:
    """Removes sentences the model copied from the worked example instead of the dictation (on a short
    dictation a small model may pad the e-mail with "Pourriez-vous me confirmer si le prix inclut la
    livraison ?"). A sentence goes if it is mostly the example's words and those words were not dictated."""
    said = _content_words(source)
    examples = [_content_words(s) for s in re.split(r"(?<=[.!?])\s+|\n+", example_out) if s.strip()]
    examples = [e for e in examples if len(e) >= 3]
    kept_lines = []
    for line in out.split("\n"):
        parts = re.split(r"(?<=[.!?])\s+", line)
        kept = []
        for sentence in parts:
            words = _content_words(sentence)
            copied = any(len(words & e) >= 0.6 * len(e) and len((words & e) - said) > 0.5 * len(words & e)
                         for e in examples)
            if not copied:
                kept.append(sentence)
        if parts and not kept and line.strip():
            continue   # the whole line was copied: drop it (its blank line is collapsed below)
        kept_lines.append(" ".join(kept))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()


_GREETING = re.compile(r"^(Bonjour|Bonsoir|Salut|Hello|Hi|Dear)\s+(?:Monsieur|Madame|M\.|Mme|Mr\.?|Mrs\.?|Ms\.?)?"
                       r"\s*([^\s,]+(?:\s+[^\s,]+)?)\s*,", re.IGNORECASE)


def _fix_invented_greeting(out: str, source: str) -> str:
    """Small models sometimes greet a made-up person ("Bonjour Monsieur Y,"): keep a plain greeting."""
    out = re.sub(r"^(Bonjour|Bonsoir|Salut|Hello|Hi), ([A-ZÀ-Ý][^,\n]{0,40}),", r"\1 \2,", out)  # "Bonjour, Julie,"
    first, _, rest = out.partition("\n")
    m = _GREETING.match(first)
    if not m:
        return out
    words = [w for w in re.split(r"\s+", m.group(2)) if w]
    if any(w.lower().strip(".") in source.lower() for w in words if len(w.strip(".")) > 1):
        return out
    return f"{m.group(1)},{first[m.end():]}" + (f"\n{rest}" if rest else "")
