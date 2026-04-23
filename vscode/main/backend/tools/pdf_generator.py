from datetime import datetime
from typing import Optional, List
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    HRFlowable,
)
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch


def generate_automation_pdf(
    filename: str,
    title: str,
    logs: List[str],
    subtitle: Optional[str] = None,
) -> None:

    doc = SimpleDocTemplate(
        filename,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=60,
        bottomMargin=40,
    )

    elements = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "TitleStyle",
        parent=styles["Heading1"],
        fontSize=18,
        textColor=colors.darkblue,
        spaceAfter=10,
    )

    log_style = ParagraphStyle(
        "LogStyle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        fontName="Courier",
    )

    elements.append(Paragraph(title, title_style))
    elements.append(Spacer(1, 0.2 * inch))

    if subtitle:
        elements.append(Paragraph(subtitle, styles["Italic"]))
        elements.append(Spacer(1, 0.2 * inch))

    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Spacer(1, 0.2 * inch))

    for line in logs:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted_line = f"[{timestamp}] {line}"

        formatted_line = (
            formatted_line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        elements.append(Paragraph(formatted_line, log_style))
        elements.append(Spacer(1, 0.12 * inch))

    doc.build(elements)

    print(f"✅ PDF Generated: {filename}")
