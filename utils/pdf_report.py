"""
pdf_report.py
--------------
Doctor-Share Mode: generates a concise, clean PDF summary of the user's
current Digital Twin health state that they can print or share with a
physician.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)
from datetime import datetime


def build_report(path, user, record, xai, tips, top_habit_changes):
    doc = SimpleDocTemplate(path, pagesize=A4,
                             topMargin=2*cm, bottomMargin=2*cm,
                             leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleStyle", parent=styles["Title"], fontSize=18,
                                  textColor=colors.HexColor("#0f4c81"))
    heading_style = ParagraphStyle("HeadingStyle", parent=styles["Heading2"], fontSize=13,
                                    textColor=colors.HexColor("#0f4c81"), spaceBefore=14, spaceAfter=6)
    normal = styles["Normal"]

    story = []
    story.append(Paragraph("AI Health Digital Twin — Clinical Summary Report", title_style))
    story.append(Paragraph(f"Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')}", normal))
    story.append(Spacer(1, 12))

    # Patient info
    story.append(Paragraph("Patient Information", heading_style))
    patient_table = Table([
        ["Name", user.get("name", "-")],
        ["Age", str(user.get("age", "-"))],
        ["Gender", str(user.get("gender", "-")).title()],
    ], colWidths=[5*cm, 10*cm])
    patient_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eaf2fb")),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(patient_table)

    # Health score
    story.append(Paragraph("Overall Health Score", heading_style))
    story.append(Paragraph(f"<b>{record['health_score']} / 100</b>", normal))

    # Sub-scores
    sub_table = Table([
        ["Metabolic", "Cardiovascular", "Sleep", "Activity"],
        [f"{record['metabolic_score']}", f"{record['cardio_score']}",
         f"{record['sleep_score']}", f"{record['activity_score']}"],
    ], colWidths=[3.75*cm]*4)
    sub_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(Spacer(1, 6))
    story.append(sub_table)

    # Risk predictions
    story.append(Paragraph("Predicted Chronic Disease Risk", heading_style))
    risk_table = Table([
        ["Condition", "Predicted Risk"],
        ["Diabetes", f"{record['diabetes_risk']}%"],
        ["Hypertension", f"{record['hypertension_risk']}%"],
        ["Heart Disease", f"{record['heart_risk']}%"],
    ], colWidths=[7.5*cm, 7.5*cm])
    risk_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(risk_table)

    # XAI key factors
    story.append(Paragraph("Key Contributing Factors (Explainable AI)", heading_style))
    for disease, factors in xai.items():
        names = ", ".join(f["friendly_name"] for f in factors if f["feature"] != "none")
        if names:
            story.append(Paragraph(f"<b>{disease.title()}:</b> {names}", normal))

    # Top habit changes
    if top_habit_changes:
        story.append(Paragraph("Highest-Impact Recommended Changes", heading_style))
        habit_table_data = [["Change", "Avg. Risk Reduction", "Health Score Gain"]]
        for h in top_habit_changes[:5]:
            habit_table_data.append([
                h["change"], f"{h['risk_reduction_pct']} pts", f"+{h['health_score_gain']}"
            ])
        habit_table = Table(habit_table_data, colWidths=[8*cm, 4*cm, 3*cm])
        habit_table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(habit_table)

    # Recommendations
    story.append(Paragraph("Personalized Recommendations", heading_style))
    for tip in tips:
        story.append(Paragraph(f"• {tip}", normal))
        story.append(Spacer(1, 3))

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "<i>This report is generated by an AI-based predictive model for informational "
        "purposes only and does not constitute a medical diagnosis. Please consult a "
        "qualified healthcare professional for clinical decisions.</i>",
        ParagraphStyle("Disclaimer", parent=normal, fontSize=8, textColor=colors.grey)
    ))

    doc.build(story)
    return path
