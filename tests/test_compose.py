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
        "Objet : Livraison retardée à jeudi\n\nBonjour Marc,\n\nTexte."
    assert compose.with_subject("Hello Mark,\n\nText.", "Delivery delayed") == "Subject: Delivery delayed\n\nHello Mark,\n\nText."
    assert compose.with_subject("Bonjour,", "   ") == "Bonjour,"
