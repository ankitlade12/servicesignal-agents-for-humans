import html
import io
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import qrcode
import qrcode.image.svg
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from .domain import PROGRAM, visible_facts


def render_notice(payload, public_id, program=None):
    esc = html.escape
    context = payload.get("program_context", PROGRAM) if payload else (program or PROGRAM)
    name, organization = esc(context["name"]), esc(context["organization"])
    if not payload:
        body = f"""<span class="eyebrow">REGULAR PROGRAM · FICTIONAL DEMO</span><h1>{name}</h1>
        <p class="lead">A little confidence. A world of possibilities.</p>
        <section class="notice-facts"><h2>Regular program details</h2><p>{esc(context["schedule"])}</p>
        <p>{esc(context["location"])} · {esc(context["room"])}</p><p>{organization}</p></section>
        <p class="muted">Seeded program information. No temporary update has been published.</p>"""
    else:
        values = visible_facts(payload)

        def fact(key):
            return f'<span data-fact="{key}">{esc(values[key])}</span>'

        expired = payload["expired"]
        heading = (
            "Please check before your next visit"
            if expired
            else (
                "These sessions are canceled"
                if payload["facts"]["kind"] == "cancellation"
                else "An update for your next visit"
            )
        )
        approved = datetime.fromtimestamp(
            payload["approved_at"], ZoneInfo(payload["facts"]["timezone"])
        ).strftime("%b %d, %Y at %I:%M %p %Z")
        body = f"""<span class="eyebrow">COMMUNITY NOTICE · FICTIONAL DEMO</span><h1>{heading}</h1>
        <p class="lead">{fact("program")} at {fact("organization")}</p>
        <div class="notice-alert {"amber" if expired else ""}">{fact("message")}</div>
        <section class="notice-facts"><h2>{"Previous temporary arrangement" if expired else "Affected sessions"}</h2>
        <p class="date-line">{fact("dates")}</p><p>{fact("start_time")}–{fact("end_time")} · {fact("timezone")}</p>
        <p class="venue">{fact("location")}</p><p>{fact("room")}</p>
        <p class="muted">{fact("kind")} · {fact("expired")}</p></section>
        <p>{fact("contact")}</p>
        <p class="muted">Last confirmed by the demo coordinator: {esc(approved)}.</p>
        <a class="button" href="/notices/{public_id}/flyer.pdf">Download printable notice ↗</a>"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{name} · Community notice</title><meta name="description" content="Current approved program information from {organization}. Fictional demonstration.">
    <link rel="stylesheet" href="/static/styles.css"><link rel="icon" href="/static/favicon.svg" type="image/svg+xml"></head>
    <body class="public-body"><a class="skip" href="#notice">Skip to notice</a><header class="public-header"><a href="/">◈ ServiceSignal</a><span>{organization}</span></header>
    <main id="notice" class="public-notice">{body}<div class="notice-share"><img src="/notices/{public_id}/qr.svg" width="100" height="100" alt="QR code for this permanent notice link">
    <div><strong>One link. The latest confirmed details.</strong><p>Share this page with someone who attends. No account needed.</p><a href="/notices/{public_id}">Permanent notice link</a></div></div></main>
    <footer class="public-footer">Demonstration workspace. Program details are entered for testing and are not a verified real service listing.</footer></body></html>"""


class FactParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.facts = {}
        self.active = None

    def handle_starttag(self, tag, attrs):
        key = dict(attrs).get("data-fact")
        if key:
            self.active = key
            self.facts[key] = ""

    def handle_data(self, data):
        if self.active:
            self.facts[self.active] += data

    def handle_endtag(self, tag):
        if tag == "span":
            self.active = None


def qr_svg(url):
    out = io.BytesIO()
    qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=2).save(out)
    return out.getvalue()


def flyer_pdf(payload, url, draft=False):
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#174c40")
    styles["Normal"].fontSize = 12
    styles["Normal"].leading = 18
    context = payload.get("program_context", PROGRAM)
    doc = SimpleDocTemplate(
        out,
        title=payload["facts"]["program"] + " — community notice",
        author=context["organization"] + " (demonstration)",
    )
    f = payload["facts"]
    lines = [
        "DRAFT PREVIEW — NOT PUBLISHED" if draft else "FICTIONAL DEMONSTRATION",
        context["organization"],
        f["program"],
        payload["message"],
        f"Change: {f['kind']}",
        ", ".join(f["dates"]),
        f"{f['start_time']}–{f['end_time']} ({f['timezone']})",
        f["location"],
        f["room"],
        context.get("contact", ""),
        "Check this permanent link before your next visit:",
        url,
    ]
    story = []
    for i, line in enumerate(lines):
        story.extend(
            [Paragraph(html.escape(line), styles["Title"] if i == 2 else styles["Normal"]), Spacer(1, 14)]
        )
    png = io.BytesIO()
    qrcode.make(url).save(png, format="PNG")
    png.seek(0)
    story.append(Image(png, width=110, height=110))
    story.append(
        Paragraph(
            "A new file does not replace previously printed copies. HTML is the primary accessible notice.",
            styles["Normal"],
        )
    )
    doc.build(story)
    return out.getvalue()
