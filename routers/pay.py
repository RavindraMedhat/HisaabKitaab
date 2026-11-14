"""Public payment pages (no login): a QR image and a share-friendly pay page.

WhatsApp can't attach an image to a text link, but it shows a preview card using the page's
og:image — so /pay carries og tags pointing at /qr.png, and the QR appears right in the chat.
"""
import io
import re
from html import escape
from urllib.parse import quote, urlencode

import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

router = APIRouter()

UPI_RE = re.compile(r"^[a-zA-Z0-9.\-_]{2,256}@[a-zA-Z]{2,64}$")


def _params(pa: str, pn: str, am: float, tn: str):
    pa, pn, tn = pa.strip(), pn.strip()[:60], tn.strip()[:80]
    if not UPI_RE.match(pa) or not (0 < am <= 1_000_000):
        raise HTTPException(400, "Invalid payment link")
    return pa, pn, round(am, 2), tn


def _upi_uri(pa, pn, am, tn) -> str:
    return f"upi://pay?pa={quote(pa)}&pn={quote(pn)}&am={am:.2f}&cu=INR&tn={quote(tn)}"


def _origin(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    return f"{proto}://{request.headers.get('host', request.url.netloc)}"


@router.get("/qr.png")
def qr_png(pa: str, pn: str = "", am: float = 0, tn: str = ""):
    pa, pn, am, tn = _params(pa, pn, am, tn)
    buf = io.BytesIO()
    segno.make(_upi_uri(pa, pn, am, tn), error="m").save(buf, kind="png", scale=10, border=4)
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})


@router.get("/pay", response_class=HTMLResponse)
def pay_page(request: Request, pa: str, pn: str = "", am: float = 0, tn: str = ""):
    pa, pn, am, tn = _params(pa, pn, am, tn)
    q = urlencode({"pa": pa, "pn": pn, "am": f"{am:.2f}", "tn": tn})
    amount = f"₹{am:,.2f}".rstrip("0").rstrip(".") if am != int(am) else f"₹{int(am):,}"
    title = f"Pay {amount} to {pn or pa}"
    img = f"{_origin(request)}/qr.png?{q}"
    e = escape
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta property="og:type" content="website">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="Scan the QR or tap to pay with any UPI app. UPI ID: {e(pa)}">
<meta property="og:image" content="{e(img)}">
<meta property="og:image:type" content="image/png">
<meta property="og:image:width" content="370"><meta property="og:image:height" content="370">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="#5B3DF5">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#F5F4FA;color:#1C1C1E;min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:1rem}}
.card{{background:#fff;border-radius:22px;padding:1.6rem 1.4rem;width:100%;max-width:360px;text-align:center;box-shadow:0 6px 30px rgba(22,19,58,.08)}}
.to{{font-size:.9rem;color:#8E8E93;font-weight:600}} .name{{font-size:1.15rem;font-weight:800;margin:.1rem 0 .6rem}}
.amt{{font-size:2.6rem;font-weight:800;letter-spacing:-.03em;margin-bottom:1rem}}
img{{width:240px;height:240px;border-radius:12px;border:1px solid #E5E5EA;background:#fff}}
.hint{{font-size:.78rem;color:#8E8E93;margin:.5rem 0 1rem}}
a.btn{{display:block;padding:.9rem;border-radius:12px;background:#5B3DF5;color:#fff;font-weight:700;text-decoration:none}}
.upi{{font-size:.85rem;color:#3C3C43;font-weight:700;word-break:break-all;margin-top:.8rem}}
</style></head><body><div class="card">
<div class="to">Pay</div><div class="name">{e(pn or pa)}</div><div class="amt">{e(amount)}</div>
<img src="/qr.png?{e(q)}" alt="UPI payment QR">
<div class="hint">Scan with any UPI app, or tap the button on your phone</div>
<a class="btn" href="{e(_upi_uri(pa, pn, am, tn))}">Pay with UPI app</a>
<div class="upi">{e(pa)}</div></div></body></html>""")
