"""Read public HTTPS copies with pinned DNS, bounded I/O and no credentials or browser execution."""

import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

MAX_BYTES = 5 * 1024**2


def public_target(url):
    if len(url) > 2048 or any(ord(c) < 33 for c in url) or "\\" in url:
        raise ValueError("Use a valid public HTTPS URL without whitespace.")
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username is not None
        or parts.password is not None
        or parts.port not in (None, 443)
    ):
        raise ValueError("Use a public HTTPS URL on port 443, without embedded credentials.")
    host = parts.hostname.encode("idna").decode("ascii")
    if host.endswith("."):
        host = host[:-1]
    answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(x[4][0] for x in answers))

    def allowed(ip):
        address = ipaddress.ip_address(ip)
        if not address.is_global or address.is_multicast or address.is_reserved:
            return False
        if address.version == 6 and (
            address.ipv4_mapped
            or address.sixtofour
            or address.teredo
            or address in ipaddress.ip_network("64:ff9b::/96")
        ):
            return False
        return True

    if not addresses or any(not allowed(ip) for ip in addresses):
        raise ValueError(
            "Private, local, reserved and mixed public/private network addresses cannot be inspected."
        )
    return host, addresses[0], urlunsplit(("https", parts.netloc, parts.path or "/", parts.query, ""))


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address):
        super().__init__(host, 443, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def fetch_public(url):
    started = time.monotonic()
    for _ in range(4):
        host, address, url = public_target(url)
        parts = urlsplit(url)
        conn = PinnedHTTPS(host, address)
        try:
            conn.request(
                "GET",
                parts.path + ("?" + parts.query if parts.query else ""),
                headers={
                    "User-Agent": "ServiceSignal-CopyCheck/1.0",
                    "Accept": "text/html,text/plain,application/pdf",
                    "Accept-Encoding": "identity",
                },
            )
            response = conn.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                target = response.getheader("Location")
                if not target:
                    raise ValueError("The copy redirected without a destination.")
                url = urljoin(url, target)
                continue
            if response.status != 200:
                raise ValueError(f"The remote copy returned HTTP {response.status}; no comparison was made.")
            media = response.getheader("Content-Type", "").split(";")[0].lower().strip()
            if media not in ("text/html", "text/plain", "application/pdf"):
                raise ValueError("The URL must return HTML, plain text, or a PDF.")
            if response.getheader("Content-Encoding", "identity").lower() not in ("", "identity"):
                raise ValueError("Compressed HTTP responses are not supported by this inspector.")
            size = response.getheader("Content-Length")
            if size and int(size) > MAX_BYTES:
                raise ValueError("The external copy exceeds 5 MB.")
            raw = bytearray()
            while True:
                if time.monotonic() - started > 25:
                    raise ValueError("The external copy exceeded the reading time limit.")
                chunk = response.read(65536)
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise ValueError("The external copy exceeds 5 MB.")
            return bytes(raw), media, url
        finally:
            conn.close()
    raise ValueError("The external copy redirected too many times.")


class ReadableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = (
            tag in ("script", "style", "template", "noscript", "head")
            or "hidden" in attrs
            or attrs.get("aria-hidden") == "true"
            or re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attrs.get("style", ""), re.I)
        )
        if tag not in (
            "area",
            "base",
            "br",
            "col",
            "embed",
            "hr",
            "img",
            "input",
            "link",
            "meta",
            "param",
            "source",
            "track",
            "wbr",
        ):
            self.stack.append((tag, bool(hidden)))
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "tr", "section"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.stack = self.stack[:i]
                break
        self.parts.append(" ")

    def handle_data(self, data):
        if not any(hidden for _, hidden in self.stack):
            self.parts.append(data)


def extract_copy(raw, media):
    if media == "application/pdf":
        from .pdf_intake import extract

        result = extract(raw)
        return result["source"], bool(result["ocr_pages"])
    text = raw.decode("utf-8", errors="replace")
    if media == "text/html":
        parser = ReadableHTML()
        parser.feed(text)
        text = "".join(parser.parts)
    if len(text) > 100000:
        raise ValueError("The external copy exceeds 100,000 text characters; inspect a specific notice URL.")
    if len(text.strip()) < 10:
        raise ValueError(
            "No readable text found. Sign-in, JavaScript-only pages and blocked copies require manual inspection."
        )
    return text, False


def compare_text(text, facts):
    from .domain import Facts

    f = Facts.model_validate(facts)
    expected = {
        "program": f.program,
        "location": f.location,
        "room": f.room,
        "timezone": f.timezone,
        "start_time": f.start_time,
        "end_time": f.end_time,
    }
    expected.update({"date_" + d.isoformat(): d.isoformat() for d in f.dates})
    expected.update(
        {"end_" + str(i): x["end"] for i, x in enumerate(f.occurrences())}
        if f.end_day_offset or f.time_choices
        else {}
    )
    normalized = " ".join(text.casefold().split())
    fields = []
    for field, value in expected.items():
        needle = " ".join(value.casefold().split())
        match = re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", normalized)
        fields.append(
            {
                "field": field,
                "expected": value,
                "state": "TEXT_FOUND" if match else "NOT_FOUND",
                "excerpt": normalized[max(0, match.start() - 50) : match.end() + 80] if match else "",
            }
        )
    return {
        "state": "TEXT_MATCH" if all(x["state"] == "TEXT_FOUND" for x in fields) else "REVIEW_REQUIRED",
        "fields": fields,
        "limitations": "Text presence is not proof of correct context, current availability, visual rendering or external publication. Missing text may use another format. Review the source before acting; no website was changed.",
    }


def inspect(url):
    raw, media, final_url = fetch_public(url)
    text, ocr = extract_copy(raw, media)
    return {
        "url": final_url,
        "media_type": media,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "text": text,
        "ocr": ocr,
        "bytes": len(raw),
    }


if __name__ == "__main__":
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (25, 25))
        if sys.platform == "linux":
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        body = json.loads(sys.stdin.read(4096))
        print(json.dumps(inspect(body["url"])))
    except Exception as error:
        print(
            json.dumps(
                {
                    "error": str(error)
                    if isinstance(error, ValueError)
                    else "The external copy could not be read. Check the public URL or upload its PDF for manual review."
                }
            )
        )
        sys.exit(1)
