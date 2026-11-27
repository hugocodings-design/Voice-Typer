"""Writer.rewrite with a fake model: the signature and the subject are handled by code, not by the AI."""

import pytest

writer = pytest.importorskip("voice_typer.writer")


class FakeWriter(writer.Writer):
    def __init__(self, body, subject="Livraison retardée"):
        self.body, self.subject, self.calls = body, subject, []

    def _generate(self, user, system, max_tokens=1024, shots=()):
        self.calls.append((user, system))
        return self.subject if system == writer.SUBJECT_SYSTEM else self.body


RULES = ("Mets en forme de courriel.\n- Toujours signer telle que mentionnée, mais si j'ai dicté ma propre "
         "signature, ne pas mettre la signature enregistrée.\n- Génère un titre de courriel.")


def test_signature_and_subject_by_code():
    w = FakeWriter("Bonjour Marc,\n\nLa livraison est retardée à jeudi.\n\nMerci,\n(aucune signature)")
    out = w.rewrite("courriel à Marc pour dire que la livraison est retardée", RULES, "Hugo Dasilva",
                    add_signature=True, subject=True)
    assert out == ("Livraison retardée\n\nBonjour Marc,\n\nLa livraison est retardée à jeudi.\n\n"
                   "Merci,\nHugo Dasilva")
    prompt = w.calls[0][0]
    assert "signature" not in prompt.split("Transcription brute")[0].lower()   # rules sent without it
    assert "titre" not in prompt.lower()


def test_dictated_signature_not_doubled_and_no_subject_when_off():
    w = FakeWriter("Bonjour,\n\nC'est noté.\n\nMerci,\nHugo pour l'équipe Ventes")
    out = w.rewrite("dictée", RULES, "Hugo Dasilva", add_signature=True, subject=False)
    assert out.endswith("Merci,\nHugo pour l'équipe Ventes") and "Hugo Dasilva" not in out
    assert len(w.calls) == 1                                                  # no subject request


class LangWriter(FakeWriter):
    """Answers in French first (like the small model did), then obeys "Answer in English only"."""

    def _generate(self, user, system, max_tokens=1024, shots=()):
        self.calls.append((user, system))
        if system in (writer.SUBJECT_SYSTEM, writer.SUBJECT_SYSTEM_EN):
            return "Test request"
        if "English only" in system:
            return self.body
        return ("Je voudrais effectuer un test.\n\nPourriez-vous me confirmer si le prix inclut la "
                "livraison ?\n\nMerci,")


def test_english_dictation_gets_an_english_email_and_signature():
    w = LangWriter("Hello,\n\nI would like to do a test.\n\nThank you,")
    out = w.rewrite("Hi, I would like to do a test.", RULES, "Hugo Da Silva\nDirecteur de comptes", True, True,
                    signature_en="Hugo Da Silva\nAccount Manager", language="fr")
    assert out == ("Test request\n\nHello,\n\nI would like to do a test.\n\nThank you,\n"
                   "Hugo Da Silva\nAccount Manager")
    assert w.calls[0][1] == writer.SYSTEM_EN and "Raw transcript" in w.calls[0][0]
    assert writer.EN_RULES_NOTE in w.calls[0][0]


def test_french_dictation_keeps_the_french_signature():
    w = FakeWriter("Bonjour,\n\nC'est noté pour jeudi.\n\nMerci,")
    out = w.rewrite("dis-lui que c'est noté pour jeudi", RULES, "Hugo Da Silva", True, False,
                    signature_en="Hugo Da Silva (EN)", language="en")
    assert out.endswith("Merci,\nHugo Da Silva") and w.calls[0][1] == writer.SYSTEM_FR


def test_english_signature_falls_back_to_the_main_one():
    w = FakeWriter("Hello,\n\nNoted for Thursday.\n\nThank you,")
    assert w.rewrite("tell him it's noted for Thursday", RULES, "Hugo", True, False).endswith("Thank you,\nHugo")


def test_sentences_copied_from_the_example_are_removed():
    out = writer.drop_copied_example("Bonjour,\n\nJe voudrais faire un test.\n\nPourriez-vous me confirmer si le "
                                     "prix inclut la livraison ?\n\nMerci,", "je voudrais faire un test",
                                     writer.EXAMPLE_OUT)
    assert out == "Bonjour,\n\nJe voudrais faire un test.\n\nMerci,"
    # dictated for real: kept
    real = "Bonjour,\n\nPourriez-vous me confirmer si le prix inclut la livraison ?\n\nMerci,"
    assert writer.drop_copied_example(real, "demande si le prix inclut la livraison", writer.EXAMPLE_OUT) == real


class _Tok:
    class _Enc:
        def __init__(self, text):
            self.tokens = text.split()
            self.ids = list(range(len(self.tokens)))

    def encode(self, text, add_special_tokens=False):
        return self._Enc(text)

    def decode(self, ids, skip_special_tokens=True):
        return "Bonjour,"


def test_system_prompt_and_example_are_cached():
    calls = []

    class Gen:
        def generate_batch(self, batch, **kw):
            calls.append((batch, kw))
            return [type("R", (), {"sequences_ids": [[1]]})()]

    w = writer.Writer.__new__(writer.Writer)
    w.tokenizer, w.generator = _Tok(), Gen()
    assert w._generate("dictée", "SYSTEM", shots=[("q", "a")]) == "Bonjour,"
    batch, kw = calls[0]
    assert kw["cache_static_prompt"] and "SYSTEM" in " ".join(kw["static_prompt"])
    assert "SYSTEM" not in " ".join(batch[0]) and "dictée" in " ".join(batch[0])   # only the new part


def test_old_ctranslate2_without_static_prompt_still_works():
    calls = []

    class OldGen:
        def generate_batch(self, batch, **kw):
            if "static_prompt" in kw:
                raise TypeError("unexpected keyword")
            calls.append(batch)
            return [type("R", (), {"sequences_ids": [[1]]})()]

    w = writer.Writer.__new__(writer.Writer)
    w.tokenizer, w.generator = _Tok(), OldGen()
    assert w._generate("dictée", "SYSTEM") == "Bonjour,"
    assert "SYSTEM" in " ".join(calls[0][0]) and "dictée" in " ".join(calls[0][0])


class SubjectWriter(FakeWriter):
    def __init__(self, body, subjects):
        super().__init__(body)
        self.subjects = list(subjects)

    def _generate(self, user, system, max_tokens=1024, shots=()):
        self.calls.append((user, system, shots))
        return self.subjects.pop(0) if system == writer.SUBJECT_SYSTEM else self.body


def test_vague_subject_gets_a_second_more_precise_try():
    body = ("Bonjour,\n\nLe terminal du Garage Tremblay ne se connecte plus depuis ce matin.\n\n"
            "Merci,")
    w = SubjectWriter(body, ["Suivi", "Garage Tremblay : terminal hors ligne depuis ce matin"])
    out = w.rewrite("courriel au support le terminal du garage Tremblay ne se connecte plus depuis ce matin",
                    "Mets en forme.", "Hugo", True, True)
    assert out.startswith("Garage Tremblay : terminal hors ligne depuis ce matin\n\n")
    first_ask = w.calls[1][0]
    assert "Bonjour" not in first_ask and "Hugo" not in first_ask          # greeting / signature left out
    assert "garage Tremblay ne se connecte" in first_ask                   # the dictation gives the context
    assert w.calls[1][2] == writer.SUBJECT_SHOTS_FR                         # worked examples
    assert "trop vague" in w.calls[2][0]


def test_good_subject_needs_one_request_only():
    body = "Bonjour,\n\nLa livraison des 4 terminaux pour Fleurs Lina est reportée à jeudi.\n\nMerci,"
    w = SubjectWriter(body, ["Fleurs Lina : livraison des 4 terminaux reportée à jeudi"])
    w.rewrite("dis que la livraison des 4 terminaux pour Fleurs Lina est reportée à jeudi", "x", "", False, True)
    assert len(w.calls) == 2


def test_subject_line_written_by_the_ai_is_removed():
    w = FakeWriter("Objet : Livraison\n\nBonjour Marc,\n\nC'est noté.\n\nMerci,")
    out = w.rewrite("dis à Marc que c'est noté", "Mets en forme.", "", False, False)
    assert out == "Bonjour Marc,\n\nC'est noté.\n\nMerci,"


class _VocabTok(_Tok):
    VOCAB = {"Bon": 0, "jour": 1, "神": 2, "通": 3, "8": 4, "é": 5, "ア": 6}

    def get_vocab(self):
        return dict(self.VOCAB)

    def decode_batch(self, batch):
        names = {v: k for k, v in self.VOCAB.items()}
        return [names[ids[0]] for ids in batch]


def test_chinese_pieces_are_forbidden_and_digits_not_penalised():
    """Screenshot case: "1-88神通6-9906" — Qwen wrote Chinese in the middle of a phone number."""
    assert sorted(writer.cjk_tokens(_VocabTok())) == ["ア", "神", "通"]
    calls = []

    class Gen:
        def generate_batch(self, batch, **kw):
            calls.append(kw)
            return [type("R", (), {"sequences_ids": [[1]]})()]

    w = writer.Writer.__new__(writer.Writer)
    w.tokenizer, w.generator = _VocabTok(), Gen()
    w._suppress = [[t] for t in writer.cjk_tokens(w.tokenizer)]
    w._generate("appelle au 1-888-6", "SYSTEM")
    assert calls[0]["repetition_penalty"] == 1.0                     # repeated digits are fine
    assert ["神"] in calls[0]["suppress_sequences"] and ["8"] not in calls[0]["suppress_sequences"]


def test_chinese_never_reaches_the_email():
    from voice_typer import compose

    assert compose.strip_cjk("au 1-88神通6-9906 extension 2") == "au 1-886-9906 extension 2"
    assert compose.strip_cjk("Café à Montréal, été") == "Café à Montréal, été"   # French accents untouched
