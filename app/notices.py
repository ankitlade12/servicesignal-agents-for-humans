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

from .assets import version as asset_version
from .domain import PROGRAM, visible_facts
from .localization import COPY


def render_notice(payload, public_id, program=None, demo=True, language="en"):
    esc = html.escape
    copy = COPY[language]
    context = payload.get("program_context", PROGRAM) if payload else (program or PROGRAM)
    name, organization = esc(context["name"]), esc(context["organization"])
    badge = " · " + copy["demo"] if demo else ""
    switch = (
        f'<nav aria-label="Language"><a href="/notices/{public_id}" lang="en">English</a> · <a href="/notices/{public_id}?lang=es" lang="es">Español</a></nav>'
        if context.get("spanish_enabled")
        else ""
    )
    if not payload:
        body = f'<span class="eyebrow">{copy["regular"]}{badge}</span><h1>{name}</h1><section class="notice-facts"><h2>{copy["baseline"]}</h2><p>{esc(context["schedule"])}</p><p>{esc(context["location"])} · {esc(context["room"])}</p><p>{organization}</p></section><p>{copy["unpublished"]}</p>'
    else:
        values = visible_facts(payload, language)

        def fact(key):
            return f'<span data-fact="{key}">{esc(values[key])}</span>'

        expired = payload["expired"]
        heading = copy[
            "ended_heading"
            if expired
            else "cancel"
            if payload["facts"]["kind"] == "cancellation"
            else "update"
        ]
        approved = datetime.fromtimestamp(
            payload["approved_at"], ZoneInfo(payload["facts"]["timezone"])
        ).strftime("%Y-%m-%d %H:%M %Z")
        body = f"""<span class="eyebrow">{copy["notice"]}{badge}</span><h1>{heading}</h1>
        <p class="lead">{fact("program")} · {fact("organization")}</p>
        <div class="notice-alert {"amber" if expired else ""}">{fact("message")}</div>
        <section class="notice-facts"><h2>{copy["previous" if expired else "affected"]}</h2>
        <p class="date-line">{fact("dates")}</p><p>{fact("start_time")}–{fact("end_time")} · {fact("timezone")}</p>
        <p class="small">{fact("session_times")}</p><p class="venue">{fact("location")}</p><p>{fact("room")}</p><p class="muted">{fact("kind")} · {fact("expired")}</p></section>
        <p>{fact("contact")}</p><p class="muted">{copy["demo_confirmed" if demo else "confirmed"]}: {esc(approved)}.</p>
        <a class="button" href="/notices/{public_id}/flyer.pdf?lang={language}">{copy["download"]} ↗</a>"""
    return f"""<!doctype html><html lang="{language}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>{name} · {copy["notice"]}</title><meta name="description" content="{copy["notice"]} · {organization}">
    <link rel="stylesheet" href="/static/styles.css?v={asset_version()}"><link rel="icon" href="/static/favicon.svg" type="image/svg+xml"></head>
    <body class="public-body"><a class="skip" href="#notice">{copy["skip"]}</a><header class="public-header"><a href="/">◈ ServiceSignal</a><span>{organization}</span></header>
    <main id="notice" class="public-notice">{switch}{body}<div class="notice-share"><img src="/notices/{public_id}/qr.svg" width="100" height="100" alt="{copy["qr"]}">
    <div><strong>{copy["share"]}</strong><p>{copy["share_help"]}</p><a href="/notices/{public_id}?lang={language}">{copy["link"]}</a></div></div></main>
    <footer class="public-footer">{copy["demo_footer" if demo else "footer"]}</footer></body></html>"""


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


def flyer_pdf(payload, url, draft=False, language="en"):
    copy = COPY[language]
    visible = visible_facts(payload, language)
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles["Title"].textColor = colors.HexColor("#174c40")
    styles["Normal"].fontSize = 12
    styles["Normal"].leading = 18
    context = payload.get("program_context", PROGRAM)
    doc = SimpleDocTemplate(
        out,
        title=payload["facts"]["program"] + " — community notice",
        author=context["organization"] + (" (demonstration)" if payload.get("demo", True) else ""),
    )
    f = payload["facts"]
    lines = [
        copy["draft"] if draft else (copy["demo"] if payload.get("demo", True) else copy["notice"]),
        context["organization"],
        f["program"],
        visible["message"],
        visible["kind"],
        ", ".join(f["dates"]),
        f"{f['start_time']}–{f['end_time']} ({f['timezone']})",
        visible["session_times"],
        f["location"],
        f["room"],
        visible["contact"],
        copy["check_link"],
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
            copy["print_limit"],
            styles["Normal"],
        )
    )
    doc.build(story)
    return out.getvalue()


def render_collection(items, public_id, language="en"):
    """Separate date-scoped notices; never merge incompatible facts into one notice."""
    esc = html.escape
    context = items[0][1]["program_context"]
    cards = []
    for change_id, payload in items:
        selected = language if language == "en" or payload["program_context"].get("spanish_enabled") else "en"
        values = visible_facts(payload, selected)
        cards.append(
            f'<article class="notice-facts" lang="{selected}"><h2>{esc(values["dates"])}</h2><p>{esc(values["message"])}</p><p>{esc(values["start_time"])}–{esc(values["end_time"])} {esc(values["timezone"])}</p><p class="small">{esc(values["session_times"])}</p><p>{esc(values["location"])} · {esc(values["room"])}</p><a class="button" href="/notices/{public_id}/changes/{change_id}?lang={selected}">Open this notice and printable flyer</a></article>'
        )
    return f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(context["name"])} notices</title><link rel="stylesheet" href="/static/styles.css?v={asset_version()}"></head><body class="public-body"><main class="public-notice"><h1>{esc(context["name"])}</h1><p>{esc(context["organization"])}</p><p>Each notice applies only to its listed sessions. Open a notice for its confirmed details and current status.</p>{"".join(cards)}</main></body></html>'
