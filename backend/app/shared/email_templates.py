"""HTML versions of the emails Mr. Momo sends (the plain-text body always goes along too).

Email clients are not browsers: Gmail strips <style> blocks in many cases and ignores web fonts,
so everything here is table layout with inline styles, system fonts and hex colours (the
stall's poster colours, as in frontend/src/styles/index.css). The logo is loaded from the
public website, so it shows only when the client loads images; the alt text covers the rest.
"""
import os
from html import escape

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
