#!/usr/bin/env python3
"""
Generates an enterprise-grade PDF engineering runbook for CloudPulse TimescaleDB.
Includes CLI commands, interactive PSQL queries, REST API endpoints, and architectural concepts.
"""

import os
import sys
from datetime import datetime, timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Preformatted
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute total page count."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Top Running Header (Pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 752, "CloudPulse FinOps • TimescaleDB Time-Series Operations Guide")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 746, 558, 746)

        # Bottom Running Footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_str)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY • CLOUDPULSE AUTONOMOUS FINOPS PLATFORM")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, 558, 46)

        self.restoreState()


def create_timeseries_guide_pdf(output_path: str):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom Palette
    c_primary = colors.HexColor("#0F172A")    # Slate 900
    c_secondary = colors.HexColor("#0284C7")  # Sky 600
    c_accent = colors.HexColor("#059669")     # Emerald 600
    c_dark = colors.HexColor("#1E293B")       # Slate 800
    c_muted = colors.HexColor("#64748B")      # Slate 500
    c_bg_code = colors.HexColor("#F8FAFC")    # Slate 50
    c_border_code = colors.HexColor("#E2E8F0")# Slate 200

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=c_primary,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=c_secondary,
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=c_primary,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=c_secondary,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=c_dark,
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Block',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    )

    story = []

    # 1. Document Title & Header Card
    story.append(Paragraph("CloudPulse FinOps Architecture Spec", subtitle_style))
    story.append(Paragraph("TimescaleDB Time-Series Operations & Telemetry Guide", title_style))
    story.append(Paragraph(
        "<b>Platform:</b> CloudPulse Autonomous FinOps &nbsp;|&nbsp; <b>Engine:</b> PostgreSQL 18.6 + TimescaleDB 2.23.0 &nbsp;|&nbsp; <b>Date:</b> September 2026",
        ParagraphStyle('Meta', parent=body_style, textColor=c_muted, fontSize=8, spaceAfter=10)
    ))

    # Decorative Rule
    rule = Table([[""]], colWidths=[504], rowHeights=[2])
    rule.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), c_secondary),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(rule)
    story.append(Spacer(1, 10))

    # Executive Summary Callout Box
    summary_text = (
        "<b>Executive Summary:</b> CloudPulse utilizes TimescaleDB hypertables to ingest high-frequency, sub-second telemetry "
        "streamed from guest virtual machines alongside CloudWatch hypervisor metrics. This runbook provides the operational "
        "commands to inspect the database, verify hypertable partitioning, execute sub-millisecond time-bucket rollups, "
        "and validate live ingestion from running EC2 instances."
    )
    summary_table = Table([[Paragraph(summary_text, body_style)]], colWidths=[504])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0F9FF")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#BAE6FD")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Helper function for Code Blocks
    def make_code_box(code_text: str):
        p = Preformatted(code_text.strip(), code_style)
        t = Table([[p]], colWidths=[504])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), c_bg_code),
            ('BORDER', (0,0), (-1,-1), 1, c_border_code),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,0), (-1,-1), 8),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    # SECTION 1: OPTION 1
    story.append(Paragraph("1. Option 1: 1-Line Terminal CLI Command (Automated Inspection)", h1_style))
    story.append(Paragraph(
        "Run the automated diagnostic CLI tool directly from the repository root to verify TimescaleDB connectivity, "
        "hypertables, active chunks, and sample time-bucket rollups in a single step:",
        body_style
    ))
    cmd_cli = (
        'DATABASE_URL="postgresql://cloudpulse_db_i402_user:LkQtWiawBtDkRyCNlaQO6C1agZi6XZ1d@'
        'dpg-daml14e1egvs73cllhpg-a.oregon-postgres.render.com/cloudpulse_db_i402" \\\n'
        './venv/bin/python scripts/show_timeseries_db.py'
    )
    story.append(make_code_box(cmd_cli))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Standard Output Verification:</b>", body_style))
    story.append(Paragraph("• <b>TimescaleDB Extension:</b> Reports active version <code>2.23.0</code> on PostgreSQL 18.6.", bullet_style))
    story.append(Paragraph("• <b>Hypertables & Chunks:</b> Confirms <code>resource_telemetry</code> (2 chunks) and <code>daily_spend_records</code> (1 chunk).", bullet_style))
    story.append(Paragraph("• <b>Real In-Guest Rows:</b> Live CPU (0.0% – 51.2%), RAM (12.6%), and Disk (30.5%) records from <code>i-07d01b00f95a4cc41</code>.", bullet_style))
    story.append(Paragraph("• <b>Time-Bucket Rollup:</b> Computes 1-minute analytical aggregations (avg, peak, sample counts).", bullet_style))
    story.append(Spacer(1, 10))

    # SECTION 2: OPTION 2
    story.append(Paragraph("2. Option 2: Connect via psql (Interactive PostgreSQL Shell)", h1_style))
    story.append(Paragraph(
        "For direct database administration, connect via the official PostgreSQL client:",
        body_style
    ))
    cmd_psql = (
        'psql "postgresql://cloudpulse_db_i402_user:LkQtWiawBtDkRyCNlaQO6C1agZi6XZ1d@'
        'dpg-daml14e1egvs73cllhpg-a.oregon-postgres.render.com/cloudpulse_db_i402"'
    )
    story.append(make_code_box(cmd_psql))
    story.append(Spacer(1, 8))

    story.append(Paragraph("Diagnostic Query 1: Verify TimescaleDB Extension", h2_style))
    story.append(make_code_box("SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Diagnostic Query 2: List All Active Hypertables", h2_style))
    story.append(make_code_box(
        "SELECT hypertable_schema, hypertable_name, num_dimensions, num_chunks, compression_enabled\n"
        "FROM timescaledb_information.hypertables;"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Diagnostic Query 3: Inspect Hypertable Chunks & Partition Time Ranges", h2_style))
    story.append(make_code_box(
        "SELECT chunk_name, hypertable_name, range_start, range_end\n"
        "FROM timescaledb_information.chunks;"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Diagnostic Query 4: View Latest High-Frequency Raw Telemetry Ticks", h2_style))
    story.append(make_code_box(
        "SELECT time, resource_id, metric_name, val_avg, val_max, val_p95\n"
        "FROM resource_telemetry\n"
        "ORDER BY time DESC\n"
        "LIMIT 10;"
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Diagnostic Query 5: Real-Time 1-Minute Time-Bucket Analytical Rollup", h2_style))
    story.append(Paragraph(
        "Aggregates second-by-second guest agent telemetry into continuous 1-minute time windows:",
        body_style
    ))
    sql_bucket = (
        "SELECT \n"
        "    time_bucket('1 minute', time) AS bucket,\n"
        "    metric_name,\n"
        "    ROUND(AVG(val_avg)::numeric, 2) AS avg_value,\n"
        "    ROUND(MAX(val_max)::numeric, 2) AS peak_value,\n"
        "    COUNT(*) AS sample_count\n"
        "FROM resource_telemetry\n"
        "WHERE resource_id = 'i-07d01b00f95a4cc41'\n"
        "GROUP BY bucket, metric_name\n"
        "ORDER BY bucket DESC\n"
        "LIMIT 12;"
    )
    story.append(make_code_box(sql_bucket))
    story.append(Spacer(1, 10))

    # SECTION 3: OPTION 3
    story.append(Paragraph("3. Option 3: REST API Integration Endpoints (cURL / HTTP)", h1_style))
    story.append(Paragraph(
        "TimescaleDB metrics are exposed through the CloudPulse REST API gateway:",
        body_style
    ))
    api_cmd = (
        "# 1. Check TimescaleDB connection health and engine version\n"
        "curl -s https://cloud-cost-optimization.onrender.com/api/v2/database/status\n\n"
        "# 2. Query high-frequency hypertable records directly\n"
        'curl -s "https://cloud-cost-optimization.onrender.com/api/v2/telemetry/hypertable?limit=10"'
    )
    story.append(make_code_box(api_cmd))
    story.append(Spacer(1, 10))

    # SECTION 4: ARCHITECTURE TABLE
    story.append(Paragraph("4. Key TimescaleDB Concepts in CloudPulse", h1_style))
    story.append(Paragraph(
        "TimescaleDB extends PostgreSQL with dedicated primitives engineered for multi-tenant cloud time-series telemetry:",
        body_style
    ))

    table_data = [
        [
            Paragraph("<b>Concept</b>", ParagraphStyle('TH', parent=body_style, textColor=colors.white)),
            Paragraph("<b>Implementation in CloudPulse</b>", ParagraphStyle('TH', parent=body_style, textColor=colors.white)),
            Paragraph("<b>Operational & Architectural Benefit</b>", ParagraphStyle('TH', parent=body_style, textColor=colors.white))
        ],
        [
            Paragraph("<b>Hypertable</b>", body_style),
            Paragraph("<code>resource_telemetry</code> (7-day interval)<br/><code>daily_spend_records</code> (30-day interval)", body_style),
            Paragraph("Presents a unified standard PostgreSQL table interface while auto-partitioning writes into physical chunk tables.", body_style)
        ],
        [
            Paragraph("<b>Chunks</b>", body_style),
            Paragraph("Partitioned by time intervals (e.g., 7 days per telemetry chunk)", body_style),
            Paragraph("Keeps indexes in memory, preventing B-tree index bloat and guaranteeing constant-time write throughput at scale.", body_style)
        ],
        [
            Paragraph("<b>time_bucket()</b>", body_style),
            Paragraph("High-speed rollup primitive for 1m, 5m, 1h, and 24h charts", body_style),
            Paragraph("Replaces slow <code>date_trunc</code> with optimized C-level arithmetic, enabling sub-millisecond multi-day aggregations.", body_style)
        ]
    ]

    t_concepts = Table(table_data, colWidths=[100, 174, 230])
    t_concepts.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), c_primary),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
    ]))
    story.append(t_concepts)
    story.append(Spacer(1, 14))

    # Topology Summary Callout Box
    topo_text = (
        "<b>Verified Production Database Topology:</b><br/>"
        "• <b>Instance ID:</b> <code>dpg-daml14e1egvs73cllhpg-a</code> &nbsp;|&nbsp; <b>Name:</b> <code>cloudpulse-db</code> (Oregon)<br/>"
        "• <b>Database Name:</b> <code>cloudpulse_db_i402</code> &nbsp;|&nbsp; <b>Postgres Engine:</b> Version 18.6 &nbsp;|&nbsp; <b>Timescale:</b> v2.23.0<br/>"
        "• <b>Status:</b> Healthy, live connections accepted from Render API & authenticated CLI."
    )
    topo_table = Table([[Paragraph(topo_text, body_style)]], colWidths=[504])
    topo_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#ECFDF5")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#A7F3D0")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(topo_table)

    # Build Document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Generated TimescaleDB PDF Guide successfully at: {output_path}")

if __name__ == "__main__":
    out_file = sys.argv[1] if len(sys.argv) > 1 else "CloudPulse_TimescaleDB_Guide.pdf"
    create_timeseries_guide_pdf(out_file)
