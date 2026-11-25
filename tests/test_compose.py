from voice_typer import compose

USER_RULES = ("Mets la dictée en forme de courriel professionnel.\n"
              "- Petits paragraphes.\n"
              "- Toujours signer telle que mentionnée, mais si jamais j'ai déjà dicté ma propre signature, "
              "ne pas mettre la signature enregistrée.\n"
              "- Génère un titre de courriel automatiquement.")
DEFAULT_EMAIL = ("Mets cette dictée en forme de courriel professionnel.\n- N'écris pas d'objet.\n"
                 "- Termine par une formule de politesse courte suivie exactement de cette signature :\n{signature}")


def test_old_presets_switches_are_guessed():
    assert compose.preset_flags({"instructions": USER_RULES}) == (True, True)
    assert compose.preset_flags({"instructions": DEFAULT_EMAIL}) == (True, False)
    assert compose.preset_flags({"instructions": "Message court, ton amical, sans signature."}) == (False, False)
    assert compose.preset_flags({"instructions": "Write a short message. No signature, no subject line."}) == (False, False)
    # the switches win once set
    assert compose.preset_flags({"instructions": USER_RULES, "add_signature": False, "subject": False}) == (False, False)


def test_model_never_sees_signature_or_subject_rules():
    out = compose.model_instructions(USER_RULES)
    assert "signature" not in out.lower() and "signer" not in out.lower() and "titre" not in out.lower()
    assert "Petits paragraphes." in out and "courriel professionnel" in out
    out = compose.model_instructions(DEFAULT_EMAIL)
    assert "{signature}" not in out and "objet" not in out.lower() and "signature" not in out.lower()
    assert "Termine par une formule de politesse courte" in out          # the closing rule survives
    out = compose.model_instructions('End with "Thanks," followed by this exact signature:\n{signature}')
    assert out == 'End with "Thanks,"'


def test_signature_added_after_the_closing():
    body = "Bonjour Marc,\n\nLe rapport est prêt.\n\nMerci,"
    assert compose.finish_signature(body, "Hugo Dasilva\nVentes", True) == body + "\nHugo Dasilva\nVentes"
    assert compose.finish_signature(body, "Hugo", False) == body           # switch off
    assert compose.finish_signature(body, "", True) == body                # no signature saved


def test_optional_blank_line_before_signature():
    body = "Bonjour Marc,\n\nLe rapport est prêt.\n\nMerci,"
    assert compose.finish_signature(body, "Hugo Dasilva", True, blank_line=True) == body + "\n\nHugo Dasilva"
    assert compose.finish_signature(body, "\n\nHugo Dasilva\n", True) == body + "\nHugo Dasilva"   # off by default
    dictated = "Bonjour,\n\nC'est noté.\n\nMerci,\nHugo pour l'équipe Ventes"
    assert compose.finish_signature(dictated, "Hugo Dasilva", True, blank_line=True) == dictated


def test_dictated_signature_is_kept_and_not_doubled():
    for body in ("Bonjour,\n\nC'est noté.\n\nMerci,\nHugo pour l'équipe Ventes",
                 "Bonjour,\n\nC'est noté.\n\nBonne journée, Hugo",
                 "Hello,\n\nNoted.\n\nBest regards,\nJ. Tremblay",
                 "Bonjour,\n\nC'est noté.\n\nMerci,\nHugo Dasilva\nVentes"):
        assert compose.finish_signature(body, "Hugo Dasilva\nVentes", True) == body


def test_a_last_sentence_is_not_a_signature():
    body = "Bonjour,\n\nMerci pour votre aide. Le dossier est complet."
    assert compose.finish_signature(body, "Hugo", True).endswith("\nHugo")


def test_subject_line():
    assert compose.with_subject("Bonjour Marc,\n\nTexte.", " Objet : « Livraison retardée à jeudi ». ") == \
        "Livraison retardée à jeudi\n\nBonjour Marc,\n\nTexte."
    assert compose.with_subject("Hello Mark,\n\nText.", "Delivery delayed") == "Delivery delayed\n\nHello Mark,\n\nText."
    assert compose.with_subject("Bonjour,", "   ") == "Bonjour,"


SIG_WITH_CLOSING = "N'hésitez pas à m'appeler au 438-555-0100 pour toute question.\n\nMerci et à bientôt !"


def test_closing_is_not_doubled_when_the_signature_has_one():
    body = "Bonjour,\n\nJ'ai activé la carte SIM.\n\nMerci et à bientôt !"
    out = compose.finish_signature(body, SIG_WITH_CLOSING, True, blank_line=True)
    assert out == "Bonjour,\n\nJ'ai activé la carte SIM.\n\n" + SIG_WITH_CLOSING
    assert out.count("Merci et à bientôt") == 1
    other = compose.finish_signature(body.replace("Merci et à bientôt !", "Merci,"), SIG_WITH_CLOSING, True)
    assert "Merci," not in other and other.endswith(SIG_WITH_CLOSING)
    # already there (the model copied it): left once
    assert compose.finish_signature(out, SIG_WITH_CLOSING, True, blank_line=True) == out


def test_a_closing_alone_is_not_taken_for_a_signature():
    body = "Bonjour,\n\nMerci de me revenir rapidement.\n\nMerci et à bientôt !"
    assert compose.finish_signature(body, "Hugo Da Silva", True, blank_line=True) == body + "\n\nHugo Da Silva"
    assert compose.ends_with_signature("Bonjour,\n\nC'est noté.\n\nMerci et bonne journée !") is False


def test_closing_lines():
    for line in ("Merci,", "Merci et à bientôt !", "Cordialement,", "Bien à vous,", "Best regards,"):
        assert compose.is_closing_line(line)
    for line in ("Bonne journée, Hugo", "Merci de me revenir rapidement.", "Merci pour votre aide ?"):
        assert not compose.is_closing_line(line)


def test_detect_language():
    assert compose.detect_language("Hi, I would like to do a test.") == "en"
    assert compose.detect_language("Bonjour, je voudrais faire un test.") == "fr"
    assert compose.detect_language("OK", "en") == "en"
    assert compose.with_subject("Bonjour,\n\nTest", "Essai", "en").startswith("Essai\n\n")


def test_subject_source_keeps_only_the_content():
    body = ("Bonjour Carole,\n\nLe changement de propriétaire est en cours.\n\nJ'attends le formulaire.\n\n"
            "Merci et à bientôt !\nHugo Da Silva\nDirecteur de comptes")
    assert compose.subject_source(body) == "Le changement de propriétaire est en cours.\n\nJ'attends le formulaire."


def test_subject_quality_check():
    src = "Le terminal du Café Lina ne se connecte plus depuis ce matin. Pouvez-vous envoyer un technicien ?"
    assert compose.subject_ok("Café Lina : terminal hors ligne, technicien demandé", src)
    assert not compose.subject_ok("Suivi", src)                                   # too short / generic
    assert not compose.subject_ok("Demande d'information", src)                   # 2 words
    assert not compose.subject_ok("Soumission pour trois terminaux livraison incluse", src)   # not this email
    assert not compose.subject_ok("Café Lina : terminal hors ligne, technicien demandé", src,
                                  examples=("Café Lina : terminal hors ligne, technicien demandé",))


def test_no_objet_label_ever():
    assert compose.with_subject("Bonjour,\n\nTexte.", "Objet : Visite du technicien") == \
        "Visite du technicien\n\nBonjour,\n\nTexte."
    assert compose.strip_subject_line("Objet : Visite\n\nBonjour,\n\nTexte.") == "Bonjour,\n\nTexte."
    assert compose.strip_subject_line("**Subject:** Visit\nHello,") == "Hello,"
    assert compose.strip_subject_line("Bonjour,\n\nL'objet de ma visite : réparer.") == \
        "Bonjour,\n\nL'objet de ma visite : réparer."                     # only a first-line label


def test_objet_label_never_reaches_the_email():
    """The exact case from the screenshot: written by a home PC still on older code."""
    got = "Objet : Objet 2 points courriels Claude\n\nBonjour Claude,\n\nTexte."
    assert compose.drop_subject_label(got) == "Objet 2 points courriels Claude\n\nBonjour Claude,\n\nTexte."
    assert compose.drop_subject_label("Subject: Visit Thursday\n\nHello,") == "Visit Thursday\n\nHello,"
    assert compose.drop_subject_label("**Objet :** Visite\n\nBonjour,") == "Visite\n\nBonjour,"
    assert compose.drop_subject_label("objet: Visite") == "Visite"
    body = "Bonjour,\n\nL'objet de ma demande : la visite."
    assert compose.drop_subject_label(body) == body                     # a sentence is never touched
    assert compose.drop_subject_label("") == ""
