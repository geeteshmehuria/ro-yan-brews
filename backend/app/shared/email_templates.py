"""HTML versions of the emails Mr. Momo sends (the plain-text body always goes along too).

Email clients are not browsers: Gmail strips <style> blocks in many cases and ignores web fonts,
so everything here is table layout with inline styles, system fonts and hex colours (the
stall's poster colours, as in frontend/src/styles/index.css). The logo is loaded from the
public website, so it shows only when the client loads images; the alt text covers the rest.
"""
import os
from html import escape
from typing import Optional

# The website's public copy of frontend/public/logo.png.
LOGO_URL = os.getenv("MAIL_LOGO_URL", "https://ro-yan-brews.vercel.app/logo.png")

FONT = "-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
CHARCOAL, CREAM, YELLOW, GREEN = "#17110d", "#fff7ea", "#ffc93c", "#4ade80"
INK, MUTED, FAINT = "#2b1a10", "#6b5a4a", "#8a7a6a"


def _layout(preheader: str, body: str) -> str:
    """The shared frame: cream page, white card, charcoal header band with the logo, footer."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>Mr. Momo</title>
<style>
/* Phones: less padding, a smaller code. The inline styles are the full-size layout, so a client
   that drops this block (some Gmail views, Outlook) still shows a working email. */
@media only screen and (max-width: 480px) {{
  .mm-page {{ padding: 12px 8px !important; }}
  .mm-head {{ padding: 16px 18px !important; }}
  .mm-veg {{ display: none !important; }}
  .mm-body {{ padding: 28px 18px 22px !important; }}
  .mm-h1 {{ font-size: 22px !important; }}
  .mm-ticket {{ padding: 14px 18px 12px !important; }}
  .mm-code {{ font-size: 32px !important; letter-spacing: 6px !important; }}
  .mm-num {{ font-size: 44px !important; }}
  .mm-line {{ padding: 10px 12px !important; font-size: 14px !important; }}
  .mm-foot {{ padding: 16px 18px !important; }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#f4ece0;">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{escape(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#f4ece0" style="background:#f4ece0;">
<tr><td class="mm-page" align="center" style="padding:28px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;background:#ffffff;border-radius:20px;overflow:hidden;font-family:{FONT};color:{INK};">
<tr><td class="mm-head" bgcolor="{CHARCOAL}" style="background:{CHARCOAL};padding:20px 28px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
<td width="56" valign="middle"><img src="{escape(LOGO_URL)}" width="44" height="44" alt="Mr. Momo" style="display:block;width:44px;height:44px;border-radius:12px;background:#ffffff;border:0;"></td>
<td valign="middle" style="font-family:{FONT};font-size:22px;font-weight:800;color:{CREAM};">Mr. <span style="color:{YELLOW};">MOMO</span></td>
<td class="mm-veg" align="right" valign="middle" style="font-family:{FONT};font-size:11px;font-weight:700;color:{GREEN};letter-spacing:1px;">100% PURE VEG</td>
</tr></table>
</td></tr>
{body}
<tr><td class="mm-foot" bgcolor="#fbf6ee" align="center" style="background:#fbf6ee;padding:18px 28px;font-family:{FONT};font-size:12px;line-height:1.6;color:{FAINT};">
<b style="color:{INK};">Mr. Momo</b> &middot; Fresh momos, steamed to order<br>Pickup only &middot; pay cash at the counter
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""


def otp_email(code: str, minutes: int) -> str:
    """The login-code email: the code big, in a dashed "ticket", easy to read and copy."""
    code = escape(code)
    body = f"""<tr><td class="mm-body" align="center" style="padding:36px 32px 28px;font-family:{FONT};">
<h1 class="mm-h1" style="margin:0;font-size:26px;line-height:1.25;font-weight:800;color:{INK};">Here's your login code</h1>
<p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:{MUTED};">Type it in the Mr. Momo app or website to sign in and order.</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:28px auto 0;">
<tr><td class="mm-ticket" align="center" bgcolor="#fff7e0" style="background:#fff7e0;border:2px dashed #e0b34a;border-radius:16px;padding:18px 36px 16px;">
<div style="font-size:12px;font-weight:700;letter-spacing:2px;color:#8a6a3a;">YOUR CODE</div>
<div class="mm-code" style="margin-top:6px;font-family:'Courier New',Consolas,monospace;font-size:40px;line-height:1.2;font-weight:800;letter-spacing:10px;color:{CHARCOAL};">{code}</div>
</td></tr>
</table>
<p style="margin:18px 0 0;font-size:14px;color:{MUTED};">This code expires in <b style="color:{INK};">{minutes} minutes</b>.</p>
<div style="margin:28px 0 0;height:1px;line-height:1px;font-size:1px;background:#efe4d3;">&nbsp;</div>
<p style="margin:20px 0 0;font-size:13px;line-height:1.6;color:{FAINT};">Didn't ask for this? You can safely ignore this email &mdash; no one can log in without the code.<br>Never share this code. Mr. Momo will never ask you for it.</p>
</td></tr>"""
    return _layout(f"Your code is {code}. It expires in {minutes} minutes.", body)


SIZES = {"half": "Half", "full": "Full"}


def order_ready_email(order_number: int, name: Optional[str], items: list, total: Optional[int]) -> str:
    """"Your order is ready": the order number big (it's what they show at the counter), what's
    in it at the prices saved on the order, and the cash to pay. `items` are order_payload's
    item dicts (name, size, qty, price); with no items/total those parts are left out."""
    rows = "".join(
        f"""<tr><td class="mm-line" style="padding:12px 16px;font-size:15px;border-bottom:1px solid #efe4d3;">{i['qty']} &times; {escape(i['name'])}"""
        + (f""" <span style="color:{FAINT};">({SIZES[i['size']]})</span>""" if i["size"] in SIZES else "")
        + f"""</td><td class="mm-line" align="right" style="padding:12px 16px;font-size:15px;font-weight:700;white-space:nowrap;border-bottom:1px solid #efe4d3;">&#8377;{i['price'] * i['qty']}</td></tr>"""
        for i in items)
    pay_row = "" if total is None else f"""<tr><td bgcolor="#fff7e0" style="background:#fff7e0;padding:14px 16px;font-size:15px;font-weight:800;">Pay at the counter</td>
<td bgcolor="#fff7e0" align="right" style="background:#fff7e0;padding:14px 16px;font-size:26px;font-weight:800;color:{CHARCOAL};white-space:nowrap;">&#8377;{total}</td></tr>"""
    bill = "" if not (rows or pay_row) else f"""<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:26px 0 0;border:1px solid #efe4d3;border-radius:14px;border-collapse:separate;overflow:hidden;text-align:left;">
{rows}{pay_row}
</table>"""
    body = f"""<tr><td class="mm-body" align="center" style="padding:32px 32px 28px;font-family:{FONT};">
<span style="display:inline-block;padding:6px 14px;border-radius:999px;background:#dcfce7;color:#166534;font-size:13px;font-weight:800;letter-spacing:1px;">&#10003; READY TO COLLECT</span>
<h1 class="mm-h1" style="margin:14px 0 0;font-size:28px;line-height:1.2;font-weight:800;color:{INK};">Your order is ready!</h1>
<p style="margin:10px 0 0;font-size:15px;line-height:1.6;color:{MUTED};">Hi {escape(name or "there")}, it's hot and waiting at the counter.<br>Show this number when you collect it.</p>
<table role="presentation" cellpadding="0" cellspacing="0" border="0" style="margin:24px auto 0;">
<tr><td class="mm-ticket" align="center" bgcolor="#f0fdf4" style="background:#f0fdf4;border:2px dashed {GREEN};border-radius:16px;padding:16px 56px 14px;">
<div style="font-size:12px;font-weight:700;letter-spacing:2px;color:#3f7a52;">YOUR ORDER</div>
<div class="mm-num" style="margin-top:2px;font-size:56px;line-height:1.1;font-weight:800;color:{CHARCOAL};">#{order_number}</div>
</td></tr>
</table>
{bill}
<p style="margin:16px 0 0;font-size:14px;color:{MUTED};"><b style="color:{INK};">Cash only</b> &mdash; no online payment needed.</p>
<div style="margin:24px 0 0;height:1px;line-height:1px;font-size:1px;background:#efe4d3;">&nbsp;</div>
<p style="margin:18px 0 0;font-size:13px;line-height:1.6;color:{FAINT};">Enjoy your food! After you collect it, you can rate it in My orders.</p>
</td></tr>"""
    pay = f"pay ₹{total} cash" if total is not None else "pay cash"
    return _layout(f"Collect it at the counter and {pay}.", body)
