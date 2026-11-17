#!/usr/bin/env python3
"""Build the submission-ready SupeRR Selector Round 1 Word report."""

from __future__ import annotations

import csv
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "SupeRR_Selector_Round1_Final_Report.docx"
CHART_DIR = ROOT / "report_charts"
NAVY = "183B56"
BLUE = "2F75B5"
RED = "C44E52"
PALE_BLUE = "EAF2F8"
PALE_GREY = "F4F6F7"
GREY = "D9D9D9"


def read_tsv(name: str) -> list[dict[str, str]]:
    with (ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def set_cell_shading(cell, fill: str) -> None:
    properties = cell._tc.get_or_add_tcPr()
    shading = OxmlElement("w:shd")
    shading.set(qn("w:fill"), fill)
    properties.append(shading)


def set_cell_border(cell, color: str = GREY) -> None:
    properties = cell._tc.get_or_add_tcPr()
    borders = properties.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        properties.append(borders)
    for edge in ("top", "left", "bottom", "right"):
        tag = f"w:{edge}"
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), "4")
        element.set(qn("w:color"), color)


def format_cell(cell, bold: bool = False, white: bool = False, size: float = 8.5) -> None:
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(0)
        for run in paragraph.runs:
            run.font.name = "Aptos"
            run.font.size = Pt(size)
            run.font.bold = bold
            if white:
                run.font.color.rgb = RGBColor(255, 255, 255)
    set_cell_border(cell)


def add_table(document: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = document.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = False
    for index, header in enumerate(headers):
        cell = table.rows[0].cells[index]
        cell.text = header
        set_cell_shading(cell, NAVY)
        format_cell(cell, bold=True, white=True)
        if widths:
            cell.width = Inches(widths[index])
    for row_index, values in enumerate(rows):
        cells = table.add_row().cells
        for index, value in enumerate(values):
            cells[index].text = str(value)
            if row_index % 2 == 1:
                set_cell_shading(cells[index], PALE_GREY)
            format_cell(cells[index])
            if widths:
                cells[index].width = Inches(widths[index])
    document.add_paragraph().paragraph_format.space_after = Pt(4)


def add_heading(document: Document, text: str, level: int = 1) -> None:
    paragraph = document.add_heading(text, level=level)
    for run in paragraph.runs:
        run.font.color.rgb = RGBColor(0, 0, 0)
        run.font.name = "Aptos Display" if level == 1 else "Aptos"
    paragraph.paragraph_format.space_before = Pt(10)
    paragraph.paragraph_format.space_after = Pt(5)


def add_paragraph(document: Document, text: str, bold_lead: str | None = None) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.space_after = Pt(6)
    if bold_lead:
        run = paragraph.add_run(bold_lead)
        run.bold = True
        paragraph.add_run(text)
    else:
        paragraph.add_run(text)


def remove_title_border(document: Document) -> None:
    properties = document.styles["Title"]._element.get_or_add_pPr()
    border = properties.find(qn("w:pBdr"))
    if border is not None:
        properties.remove(border)


def create_charts(batters: list[dict[str, str]], bowlers: list[dict[str, str]]) -> tuple[Path, Path]:
    CHART_DIR.mkdir(exist_ok=True)
    batting_chart = CHART_DIR / "batting_scores.png"
    bowling_chart = CHART_DIR / "bowling_scores.png"

    def draw_chart(names: list[str], scores: list[float], color: str, title: str, output: Path) -> None:
        width, height = 1600, 960
        image = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(image)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        draw.text((65, 38), title, fill="#1A1A1A", font=font_bold)
        max_score = max(scores) * 1.12
        top, row_height, left, chart_width = 125, 72, 480, 980
        for index, (name, score) in enumerate(zip(names, scores)):
            y = top + index * row_height
            draw.text((65, y + 11), name, fill="#222222", font=font)
            draw.rounded_rectangle((left, y + 12, left + int(chart_width * score / max_score), y + 52), radius=8, fill=color)
            draw.text((left + int(chart_width * score / max_score) + 16, y + 12), f"{score:.2f}", fill="#222222", font=font)
        draw.text((left, 885), "Reliability adjusted pressure score", fill="#555555", font=font)
        image.save(output)

    batter_names = [row["batter"] for row in batters][::-1]
    batter_scores = [float(next(item["adjusted_pressure_score"] for item in read_tsv("batting_pressure_rankings.tsv") if item["striker_name"] == name)) for name in batter_names]
    draw_chart(batter_names, batter_scores, "#2F75B5", "Batting pressure scores", batting_chart)
    bowler_names = [row["bowler"] for row in bowlers][::-1]
    bowler_scores = [float(next(item["adjusted_pressure_score"] for item in read_tsv("bowling_pressure_rankings.tsv") if item["bowler_name"] == name)) for name in bowler_names]
    draw_chart(bowler_names, bowler_scores, "#C44E52", "Bowling pressure scores", bowling_chart)
    return batting_chart, bowling_chart


def main() -> None:
    batters = read_tsv("batting_final_ranking_with_evidence.tsv")
    bowlers = read_tsv("bowling_final_ranking_with_evidence.tsv")
    batting_chart, bowling_chart = create_charts(batters, bowlers)
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.65)
    section.right_margin = Inches(0.65)
    styles = document.styles
    styles["Normal"].font.name = "Aptos"
    styles["Normal"].font.size = Pt(10.5)
    remove_title_border(document)

    title = document.add_paragraph(style="Title")
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title.add_run("SupeRR Selector Season 2 Round 1")
    for run in title.runs:
        run.font.name = "Aptos Display"
        run.font.color.rgb = RGBColor(0, 0, 0)
        run.font.size = Pt(24)
    subtitle = document.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Pressure performance rankings for T20 batters and bowlers")
    subtitle.runs[0].italic = True
    subtitle.runs[0].font.size = Pt(12)
    document.add_paragraph()
    add_paragraph(document, "This report identifies players who improved or sustained their performance in high-pressure T20 chases compared with their own normal-pressure baseline. The final ranking prioritises reproducibility, sample reliability and stability across seasons.")

    add_heading(document, "Final ranked lists")
    add_paragraph(document, "The ordered lists below are the final submission recommendations. Context features such as death overs, wickets in hand, yorkers, recovery after boundaries, pace versus spin and batter handedness were tested as evidence. They were not forced into the rank score when validation showed no improvement in season-to-season stability.")
    add_table(document, ["Rank", "Top batters", "Confidence"], [[row["rank"], row["batter"], row["confidence_note"]] for row in batters], [0.45, 1.8, 4.35])
    add_table(document, ["Rank", "Top bowlers", "Confidence"], [[row["rank"], row["bowler"], row["confidence_note"]] for row in bowlers], [0.45, 1.8, 4.35])

    document.add_page_break()
    add_heading(document, "What pressure means in this model")
    add_paragraph(document, "The analysis uses second-innings chases only. A chase gives an observable target, required run rate, wickets in hand and balls remaining, which makes pressure measurable without inventing a first-innings target.")
    add_table(document, ["Pressure component", "How it is measured", "Why it matters"], [
        ["Required rate", "Percentile of the pre-ball required run rate", "Captures scoring urgency"],
        ["Wickets lost", "Wickets lost divided by 10", "Captures declining batting resources"],
        ["Time pressure", "1 minus balls remaining divided by scheduled balls", "Captures match-stage urgency"],
    ], [1.45, 2.75, 2.4])
    add_paragraph(document, "The three normalised components are equally weighted. High pressure is the top quarter of the observed chase-state pressure distribution. This produces 23,795 high-pressure deliveries from 95,177 eligible chase deliveries.")

    add_heading(document, "Data preparation and quality control")
    add_table(document, ["Check", "Result"], [
        ["Raw delivery data", "200,999 deliveries across 883 matches"],
        ["Eligible analysis base", "200,741 deliveries across 864 non-abandoned matches"],
        ["Keys and links", "Delivery, match, competition and team checks passed"],
        ["Abandoned matches", "19 removed, including partial-delivery abandonments"],
        ["Playing XI table", "Used with is_played flag because squads include non-playing members"],
    ], [2.2, 4.4])

    document.add_page_break()
    add_heading(document, "Batting model and evidence")
    add_paragraph(document, "Each batter is compared with their own normal-pressure chase baseline. The model uses high-pressure runs per ball and survival, measured as the change in dismissal rate. Both are standardised and equally weighted. A batter must face at least 53 balls in both high- and normal-pressure states. Scores are shrunk using a 108-ball reliability prior so short high-pressure cameos cannot dominate.")
    document.add_picture(str(batting_chart), width=Inches(6.8))
    document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_paragraph(document, "The chart is a reliability-adjusted ranking, not a career-ability ranking. It measures who improves or sustains performance when the chase state is most difficult.")

    document.add_page_break()
    add_heading(document, "Bowling model and evidence")
    add_paragraph(document, "Each bowler is compared with their normal-pressure chase baseline using run suppression and wicket impact. Run suppression is the reduction in economy under high pressure; wicket impact is the change in wickets per legal ball. Byes, leg-byes and penalty runs are not charged to the bowler, and run outs are not treated as bowler wickets.")
    add_paragraph(document, "A bowler must deliver at least 84 legal balls in both high- and normal-pressure states. The 143-ball reliability prior reduces volatility from short spells.")
    document.add_picture(str(bowling_chart), width=Inches(6.8))
    document.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER

    document.add_page_break()
    add_heading(document, "Cricket context and validation")
    add_table(document, ["Cricket factor", "Use in final report", "Reason"], [
        ["Death overs", "Supporting evidence", "Already represented by the time-pressure component; avoids double counting."],
        ["Wickets in hand", "Core input and supporting split", "Already represented continuously in pressure classification."],
        ["Yorker execution", "Supporting bowling evidence", "Explicitly labelled in the source but player samples differ materially."],
        ["Post-boundary recovery", "Supporting bowling evidence", "Measures the next legal ball in the same over after a boundary."],
        ["Pace spin and handedness", "Tested challenger", "Did not improve leave-one-season-out stability."],
    ], [1.5, 1.6, 3.3])
    add_heading(document, "Stability results", level=2)
    add_table(document, ["Discipline", "Core model", "Matchup challenger", "Decision"], [
        ["Batting", "7.75 of 10 retained", "7.50 of 10 retained", "Keep core rank"],
        ["Bowling", "7.50 of 10 retained", "7.25 of 10 retained", "Keep core rank"],
    ], [1.1, 1.8, 1.95, 1.5])
    add_paragraph(document, "The main score was retained because it is more stable when seasons are withheld. This is an intentional anti-overfitting decision: plausible cricket features are used as evidence unless they make the ranking more reliable out of sample.")

    add_heading(document, "Limitations and submission notes")
    add_paragraph(document, "The method measures pressure performance in chases, not universal player quality. IPL and T20I roles and opportunities differ, so format-specific evidence is disclosed. Lower-stability selections are transparently labelled in the evidence tables. The ranking should be submitted in the same order shown in this report.")
    document.save(OUT)
    print(OUT)


if __name__ == "__main__":
    main()
