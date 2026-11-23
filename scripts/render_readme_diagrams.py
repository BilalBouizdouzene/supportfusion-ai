"""Render the architecture and workflow images used by the project README."""

from __future__ import annotations

import math
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "images"
WIDTH, HEIGHT = 1800, 1100

NAVY = "#10182F"
INK = "#1E2A46"
MUTED = "#77839B"
VIOLET = "#7057E8"
CYAN = "#25B7CB"
GREEN = "#2FA982"
BACKGROUND = "#F4F6FB"
WHITE = "#FFFFFF"
BORDER = "#E2E7F0"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            Path("C:/Windows/Fonts/seguisb.ttf"),
            Path("C:/Windows/Fonts/segoeuib.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ]
        if bold
        else [
            Path("C:/Windows/Fonts/segoeui.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def canvas(
    kicker: str, title: str, subtitle: str
) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BACKGROUND)
    draw = ImageDraw.Draw(image)
    for x in range(30, WIDTH, 48):
        for y in range(30, HEIGHT, 48):
            draw.ellipse((x, y, x + 2, y + 2), fill="#E8ECF5")
    draw.rounded_rectangle((62, 52, 490, 88), radius=18, fill="#E9E7FF")
    draw.text((80, 61), kicker.upper(), fill=VIOLET, font=font(15, True))
    draw.text((62, 113), title, fill=NAVY, font=font(42, True))
    draw.text((64, 173), subtitle, fill=MUTED, font=font(20))
    return image, draw


def card(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    heading: str,
    body: str,
    accent: str,
    number: str | None = None,
) -> None:
    left, top, right, bottom = box
    draw.rounded_rectangle(
        (left + 5, top + 7, right + 5, bottom + 7), radius=18, fill="#E8EBF2"
    )
    draw.rounded_rectangle(box, radius=18, fill=WHITE, outline=BORDER, width=2)
    draw.rounded_rectangle((left, top, left + 8, bottom), radius=4, fill=accent)
    text_left = left + 27
    heading_top = top + 23
    if number:
        draw.ellipse((left + 23, top + 20, left + 59, top + 56), fill=accent)
        draw.text((left + 34, top + 25), number, fill=WHITE, font=font(17, True))
        text_left = left + 72
        heading_top = top + 24
    draw.text((text_left, heading_top), heading, fill=INK, font=font(20, True))
    body_width = 25 if number else 34
    wrapped = "\n".join(
        line
        for paragraph in body.splitlines()
        for line in textwrap.wrap(paragraph, width=body_width)
    )
    draw.multiline_text(
        (left + 27, top + 72), wrapped, fill=MUTED, font=font(16), spacing=9
    )


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = VIOLET,
    width: int = 5,
) -> None:
    draw.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    head_length, spread = 16, 0.58
    tip = end
    base_left = (
        end[0] - head_length * math.cos(angle - spread),
        end[1] - head_length * math.sin(angle - spread),
    )
    base_right = (
        end[0] - head_length * math.cos(angle + spread),
        end[1] - head_length * math.sin(angle + spread),
    )
    draw.polygon((tip, base_left, base_right), fill=color)


def label(draw: ImageDraw.ImageDraw, point: tuple[int, int], value: str) -> None:
    draw.rounded_rectangle(
        (point[0] - 7, point[1] - 3, point[0] + 150, point[1] + 27),
        radius=8,
        fill=BACKGROUND,
    )
    draw.text(point, value, fill=MUTED, font=font(13, True))


def render_architecture() -> None:
    image, draw = canvas(
        "Vue d’ensemble · application locale",
        "Architecture de SupportFusion",
        "Les sources alimentent le corpus ; l’API retourne des éléments traçables à l’interface.",
    )

    card(
        draw,
        (85, 295, 430, 485),
        "Interface React",
        "Tableau de bord\nRecherche\nAnalyse des tickets",
        VIOLET,
    )
    card(
        draw,
        (535, 295, 850, 485),
        "API FastAPI",
        "Incidents · sources\nRecherche · analyse\nSQLite avec SQLAlchemy",
        CYAN,
    )
    card(
        draw,
        (955, 270, 1340, 510),
        "Recherche hybride",
        "BM25 + codes d’erreur\nEmbeddings et FAISS CPU\nFusion RRF\nCross-Encoder optionnel",
        VIOLET,
    )
    card(
        draw,
        (1440, 295, 1720, 485),
        "Dossier de preuves",
        "Résultats classés\nURL et provenance\nBrouillon à vérifier",
        GREEN,
    )

    arrow(draw, (435, 390), (520, 390))
    arrow(draw, (855, 390), (940, 390))
    arrow(draw, (1345, 390), (1425, 390))

    card(
        draw,
        (140, 710, 480, 895),
        "Sources publiques",
        "Issues GitHub\nDocumentation produit\nTickets et journaux locaux",
        CYAN,
    )
    card(
        draw,
        (635, 710, 960, 895),
        "Collecte et préparation",
        "Pagination et reprise\nExtraction des champs\nNettoyage et découpage",
        VIOLET,
    )
    card(
        draw,
        (1120, 700, 1510, 910),
        "Stockage local",
        "SQLite : incidents, docs, tickets\nRaw : réponses et provenance\nFAISS : vecteurs du corpus",
        GREEN,
    )
    arrow(draw, (485, 800), (620, 800), color=CYAN)
    arrow(draw, (965, 800), (1105, 800), color=CYAN)

    draw.line((1260, 695, 1260, 625), fill=GREEN, width=4)
    draw.line((1260, 625, 1130, 625), fill=GREEN, width=4)
    arrow(draw, (1130, 625), (1130, 520), color=GREEN, width=4)
    label(draw, (1274, 585), "corpus et index")

    draw.rounded_rectangle((85, 970, 1715, 1032), radius=14, fill=NAVY)
    draw.text((112, 990), "Exécution locale", fill="#8EDCE5", font=font(17, True))
    draw.text(
        (310, 990),
        "SQLite · modèles CPU facultatifs · validation humaine avant toute réponse",
        fill="#E2E7F3",
        font=font(17),
    )

    image.save(OUTPUT_DIR / "architecture.png", optimize=True)


def render_pipeline() -> None:
    image, draw = canvas(
        "Flux de données · ingestion et diagnostic",
        "Du contenu source à une réponse vérifiable",
        "Deux parcours : construire l’index, puis rechercher des preuves pour un ticket.",
    )

    draw.text((78, 230), "01  CONSTRUIRE LE CORPUS", fill=VIOLET, font=font(16, True))
    ingest = [
        ("Sources", "Issues GitHub\nDocs officielles", CYAN),
        ("Collecte bornée", "Pagination\nCheckpoint\nRobots.txt", VIOLET),
        ("Préparation", "Extraction\nNettoyage\nChunks", CYAN),
        ("SQLite", "Contenu\nMétadonnées\nProvenance", GREEN),
        ("FAISS", "Vecteurs\nModèle local\nIndex persistant", VIOLET),
    ]
    x_positions = [78, 425, 772, 1119, 1466]
    for index, ((heading, body, accent), left) in enumerate(
        zip(ingest, x_positions, strict=True), 1
    ):
        card(draw, (left, 278, left + 260, 455), heading, body, accent, f"{index:02d}")
        if index < len(ingest):
            arrow(draw, (left + 268, 366), (left + 337, 366), color=VIOLET, width=4)

    draw.text((78, 690), "02  TRAITER UN TICKET", fill=CYAN, font=font(16, True))
    runtime = [
        ("Ticket", "Symptômes\nVersion\nLogs", CYAN),
        ("Recherche", "Lexicale\nSémantique\nCodes d’erreur", VIOLET),
        ("Classement", "Fusion RRF\nCross-Encoder\nsi disponible", VIOLET),
        ("Preuves", "Résultats classés\nSources et extraits\nEvidenceBundle", GREEN),
        ("Validation", "Brouillon proposé\nTechnicien vérifie\navant envoi", CYAN),
    ]
    for index, ((heading, body, accent), left) in enumerate(
        zip(runtime, x_positions, strict=True), 1
    ):
        card(draw, (left, 738, left + 260, 915), heading, body, accent, f"{index:02d}")
        if index < len(runtime):
            arrow(draw, (left + 268, 826), (left + 337, 826), color=CYAN, width=4)

    # The indexed corpus feeds the hybrid retriever in the second lane.
    draw.line((1596, 458, 1596, 615), fill=GREEN, width=4)
    draw.line((1596, 615, 555, 615), fill=GREEN, width=4)
    arrow(draw, (555, 615), (555, 726), color=GREEN, width=4)
    label(draw, (1100, 585), "corpus indexé réutilisé pour la recherche")

    image.save(OUTPUT_DIR / "pipeline.png", optimize=True)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    render_architecture()
    render_pipeline()
    print(f"Images created in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
