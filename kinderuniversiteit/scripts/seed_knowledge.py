"""
Seed the ChromaDB knowledge base with Kinderuniversiteit content.

Run this once (or after clearing the collection) to populate the knowledge
base so the chatbot can answer questions from day one.

Usage:
    python scripts/seed_knowledge.py
    python scripts/seed_knowledge.py --clear   # wipe then re-seed
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.infrastructure.ai.rag.knowledge_base_service import ChromaKnowledgeBase

# ---------------------------------------------------------------------------
# Knowledge content
# Each entry becomes one ChromaDB document.  Keep chunks under ~800 chars.
# ---------------------------------------------------------------------------

KNOWLEDGE_CHUNKS: list[tuple[str, str, dict]] = [
    # (doc_id, content, metadata)

    # ── Holiday camps ────────────────────────────────────────────────────────
    (
        "camps-overview",
        (
            "Kinderuniversiteit biedt vakantieprogramma's voor kinderen van 6 tot 16 jaar. "
            "De kampen worden georganiseerd tijdens de schoolvakanties: herfstvakantie, "
            "kerstvakantie, voorjaarsvakantie, paasvakantie en zomervakantie. "
            "Elk kamp duurt één week en focust op thema's zoals wetenschap, technologie, "
            "kunst, coderen en natuur. Kinderen leren door middel van experimenten, "
            "projecten en creatieve opdrachten."
        ),
        {"source_file": "kampen-overzicht.md", "page_number": 1, "category": "camps"},
    ),
    (
        "camps-ages",
        (
            "Leeftijdsgroepen bij Kinderuniversiteit vakantieprogramma's:\n"
            "• Groep Ster (6-8 jaar): speelse introductie tot wetenschap en kunst.\n"
            "• Groep Explorer (9-11 jaar): diepgaandere experimenten en samenwerken.\n"
            "• Groep Innovator (12-14 jaar): technologie, coderen en robotica.\n"
            "• Groep Leader (15-16 jaar): projectmatig werken en presentaties.\n"
            "Elk groep heeft maximaal 15 deelnemers zodat begeleiding persoonlijk blijft."
        ),
        {"source_file": "kampen-leeftijden.md", "page_number": 1, "category": "camps"},
    ),

    # ── Pricing ──────────────────────────────────────────────────────────────
    (
        "pricing-camps",
        (
            "Prijzen vakantieprogramma's Kinderuniversiteit 2024-2025:\n"
            "• Dagprogramma (9:00-16:00): €195 per week.\n"
            "• Verlengde opvang (8:00-18:00): €245 per week.\n"
            "• Broer/zus-korting: 10% op het tweede kind en elk volgend kind.\n"
            "• Vroegboekkorting: 15% korting bij inschrijving meer dan 8 weken van tevoren.\n"
            "• Betalingsmogelijkheden: iDEAL, bankoverschrijving, creditcard.\n"
            "Prijzen zijn inclusief alle materialen en een dagelijkse lunch."
        ),
        {"source_file": "prijzen.md", "page_number": 1, "category": "pricing"},
    ),
    (
        "pricing-courses",
        (
            "Reguliere cursussen (najaar en voorjaar):\n"
            "• Losse workshop (2 uur): €35 per kind.\n"
            "• Cursusreeks (6 weken, 1x per week): €175 per kind.\n"
            "• Jaarabonnement (onbeperkt workshops): €495 per jaar.\n"
            "Cursussen vinden plaats op zaterdagochtend en woensdagmiddag. "
            "Materiaalkosten zijn inbegrepen."
        ),
        {"source_file": "prijzen.md", "page_number": 2, "category": "pricing"},
    ),

    # ── Registration ─────────────────────────────────────────────────────────
    (
        "registration-process",
        (
            "Inschrijven voor een vakantieprogramma of cursus:\n"
            "Gebruik het officiële inschrijfformulier via deze link:\n"
            "https://forms.office.com/r/QGWdkT61aJ\n\n"
            "Stappen:\n"
            "1. Open het inschrijfformulier: https://forms.office.com/r/QGWdkT61aJ\n"
            "2. Vul de naam, leeftijd en contactgegevens van je kind in.\n"
            "3. Kies het gewenste programma en de gewenste week.\n"
            "4. Kies een betaalmethode en rond de betaling af.\n"
            "5. Je ontvangt binnen 24 uur een WhatsApp-bevestiging met alle details.\n"
            "Je kunt ook meer informatie vinden op onze website: www.kinderuniversiteit.com\n"
            "Inschrijving is definitief na ontvangst van de betaling. "
            "Bij populaire kampen geldt aanmelding op volgorde van binnenkomst."
        ),
        {"source_file": "inschrijven.md", "page_number": 1, "category": "registration"},
    ),
    (
        "registration-deadline",
        (
            "Inschrijvingsdeadlines Kinderuniversiteit:\n"
            "• Zomerkamp: inschrijving opent 1 maart, sluit 1 juni.\n"
            "• Herfst- en kerstvakantie: inschrijving opent 6 weken van tevoren.\n"
            "• Voorjaars- en paasvakantie: inschrijving opent 6 weken van tevoren.\n"
            "• Reguliere cursussen: inschrijving mogelijk tot 1 week voor aanvang.\n"
            "Bij uitverkochte kampen kun je je aanmelden voor de wachtlijst via de website."
        ),
        {"source_file": "inschrijven.md", "page_number": 2, "category": "registration"},
    ),

    # ── Cancellation & refund policy ─────────────────────────────────────────
    (
        "cancellation-policy",
        (
            "Annuleringsbeleid Kinderuniversiteit:\n"
            "• Meer dan 4 weken voor aanvang: volledige terugbetaling minus €25 administratiekosten.\n"
            "• 2-4 weken voor aanvang: 50% restitutie.\n"
            "• Minder dan 2 weken voor aanvang: geen restitutie.\n"
            "• Bij annulering door Kinderuniversiteit (bijv. te weinig aanmeldingen): "
            "volledige terugbetaling zonder administratiekosten.\n"
            "Annuleren doe je via info@kinderuniversiteit.com met vermelding van naam en programma."
        ),
        {"source_file": "annuleringsbeleid.md", "page_number": 1, "category": "policy"},
    ),

    # ── Locations ────────────────────────────────────────────────────────────
    (
        "locations",
        (
            "Locaties Kinderuniversiteit:\n"
            "• Amsterdam: Sciencepark 1, 1098 XG Amsterdam (hoofdlocatie).\n"
            "• Rotterdam: Lloydstraat 300, 3024 EA Rotterdam.\n"
            "• Utrecht: Heidelberglaan 8, 3584 CS Utrecht.\n"
            "• Den Haag: Laan van Nieuw Oost-Indië 300, 2593 CE Den Haag.\n"
            "Alle locaties zijn goed bereikbaar met het openbaar vervoer. "
            "Fietsstalling aanwezig. Beperkt parkeren mogelijk."
        ),
        {"source_file": "locaties.md", "page_number": 1, "category": "locations"},
    ),

    # ── Summer camp specifics ─────────────────────────────────────────────────
    (
        "summer-camp-2025",
        (
            "Zomerkamp 2025 — programma-overzicht:\n"
            "Week 1 (7-11 juli): Ruimtewetenschap — raketbouw, sterrenkunde, Mars-missie simulatie.\n"
            "Week 2 (14-18 juli): Digitale kunst & animatie — stop-motion, pixel art, muziekproductie.\n"
            "Week 3 (21-25 juli): Natuur & duurzaamheid — ecologie, zonne-energie, tuinieren.\n"
            "Week 4 (28 juli-1 aug): Coderen & games — Scratch, Python basics, eigen game bouwen.\n"
            "Week 5 (4-8 aug): Biologie & geneeskunde — microscopen, DNA, EHBO.\n"
            "Elke week is los in te schrijven. Prijs: €195 per week (dagprogramma)."
        ),
        {"source_file": "zomerkamp-2025.md", "page_number": 1, "category": "camps"},
    ),

    # ── Website ───────────────────────────────────────────────────────────────
    (
        "website-url",
        (
            "De officiële website van Kinderuniversiteit is: www.kinderuniversiteit.com\n"
            "Website adres / link / URL: https://www.kinderuniversiteit.com\n"
            "Op de website vind je alle informatie over programma's, vakantieprogramma's, "
            "cursussen, locaties en prijzen. Je kunt ook direct inschrijven via de website "
            "of via het inschrijfformulier: https://forms.office.com/r/QGWdkT61aJ"
        ),
        {"source_file": "website.md", "page_number": 1, "category": "contact"},
    ),

    # ── Contact & support ─────────────────────────────────────────────────────
    (
        "contact-info",
        (
            "Contact Kinderuniversiteit:\n"
            "• E-mail algemeen: info@kinderuniversiteit.com\n"
            "• E-mail inschrijvingen: aanmeldingen@kinderuniversiteit.com\n"
            "• Telefoon: 020 123 4567 (ma-vr 9:00-17:00)\n"
            "• Website: www.kinderuniversiteit.com\n"
            "• Social media: @kinderuniversiteit op Instagram, Facebook en WhatsApp\n"
            "Voor dringende zaken tijdens een kamp: gebruik het noodnummer op de bevestigingsmail."
        ),
        {"source_file": "contact.md", "page_number": 1, "category": "contact"},
    ),

    # ── Bank details ──────────────────────────────────────────────────────────
    (
        "bank-details",
        (
            "Bankgegevens Kinderuniversiteit:\n"
            "• Naam: Stichting Kinderuniversiteit Nederland\n"
            "• IBAN: NL91 ABNA 0417 1643 00\n"
            "• BIC: ABNANL2A\n"
            "• Bank: ABN AMRO\n"
            "Vermeld bij betaling altijd: naam van het kind + naam van het programma. "
            "Betalingen worden doorgaans binnen 2 werkdagen verwerkt."
        ),
        {"source_file": "bankgegevens.md", "page_number": 1, "category": "financial"},
    ),

    # ── FAQ ───────────────────────────────────────────────────────────────────
    (
        "faq-what-to-bring",
        (
            "Wat moet mijn kind meenemen naar het kamp?\n"
            "• Lunchpakket is NIET nodig — lunch is inbegrepen in de prijs.\n"
            "• Wel meenemen: waterfles, comfortabele kleding, gymschoenen.\n"
            "• Bij buitenactiviteiten: regenjas en zonnecrème.\n"
            "• Waardevolle spullen en elektronica beter thuislaten.\n"
            "• Medicijnen: vooraf melden bij aanmelding en meegeven met instructies."
        ),
        {"source_file": "veelgestelde-vragen.md", "page_number": 1, "category": "faq"},
    ),
    (
        "faq-supervision",
        (
            "Begeleiding en veiligheid bij Kinderuniversiteit:\n"
            "• Maximale groepsgrootte: 15 kinderen per begeleider.\n"
            "• Alle begeleiders hebben een VOG (Verklaring Omtrent Gedrag).\n"
            "• EHBO-gecertificeerde medewerker altijd aanwezig.\n"
            "• Kinderen worden alleen meegegeven aan aangemelde ophaalgerechtigden.\n"
            "• Bij ziekte of incident wordt de ouder/verzorger direct gecontacteerd."
        ),
        {"source_file": "veelgestelde-vragen.md", "page_number": 2, "category": "faq"},
    ),
    (
        "faq-languages",
        (
            "In welke taal worden de kampen gegeven?\n"
            "Alle Kinderuniversiteit-programma's worden gegeven in het Nederlands. "
            "Begeleiders spreken ook Engels voor kinderen die nog weinig Nederlands kennen. "
            "Internationale kinderen zijn van harte welkom — een basiskennis Nederlands "
            "of Engels is voldoende om te kunnen deelnemen."
        ),
        {"source_file": "veelgestelde-vragen.md", "page_number": 3, "category": "faq"},
    ),

    # ── Social media ──────────────────────────────────────────────────────────
    (
        "social-media",
        (
            "Kinderuniversiteit is actief op de volgende sociale media:\n"
            "Facebook: facebook.com/kinderuniversiteit\n"
            "LinkedIn: linkedin.com/company/kinderuniversiteit\n"
            "Instagram: instagram.com/kinderuniversiteit\n"
            "Volg ons voor nieuws over nieuwe programma's, foto's van onze kampen en updates. "
            "Je kunt ook via Facebook Messenger of Instagram Direct berichten sturen. "
            "Website: www.kinderuniversiteit.com"
        ),
        {"source_file": "socials.md", "page_number": 1, "category": "contact"},
    ),
]


# ── Seed logic ────────────────────────────────────────────────────────────────


async def seed(clear: bool = False) -> None:
    kb = ChromaKnowledgeBase()

    if clear:
        import asyncio as _asyncio
        import chromadb as _chromadb
        from app.core.config import settings as _s
        from app.infrastructure.ai.rag import vector_store as _vs
        _client = _chromadb.PersistentClient(path=str(_s.chroma_persist_dir.resolve()))
        if any(c.name == _s.chroma_collection_name for c in _client.list_collections()):
            _client.delete_collection(_s.chroma_collection_name)
            _vs._collection = None  # reset singleton so it's recreated with new embedding fn
            print(f"Deleted collection '{_s.chroma_collection_name}'.")

    print(f"Seeding {len(KNOWLEDGE_CHUNKS)} knowledge chunks…")
    for i, (doc_id, content, metadata) in enumerate(KNOWLEDGE_CHUNKS, 1):
        await kb.ingest_document(doc_id, content, metadata)
        print(f"  [{i:2d}/{len(KNOWLEDGE_CHUNKS)}] {doc_id}")

    # Verify
    from app.infrastructure.ai.rag.vector_store import get_chroma_collection
    import asyncio as _asyncio
    col = await _asyncio.to_thread(get_chroma_collection)
    count = await _asyncio.to_thread(col.count)
    print(f"\nDone. Collection '{col.name}' now contains {count} chunks.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Kinderuniversiteit knowledge base")
    parser.add_argument("--clear", action="store_true", help="Delete all existing chunks before seeding")
    args = parser.parse_args()
    asyncio.run(seed(clear=args.clear))


if __name__ == "__main__":
    main()
