import os
import logging
import resend

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")


def get_resend_credentials():
    """Chiave Resend diretta da RESEND_API_KEY (ex-connettore Replit rimosso)."""
    return RESEND_API_KEY, None


def send_verification_email(to_email: str, verification_link: str, user_name: str = None):
    api_key, from_email = get_resend_credentials()
    
    if not api_key:
        api_key = RESEND_API_KEY
    
    if not api_key:
        logger.error("No Resend API key available")
        return False
    
    from_email = "Amazon Ads Manager <noreply@anonimapublishing.online>"
    
    resend.api_key = api_key
    
    subject = "Verifica la tua email - Amazon Ads Manager"
    greeting = f"Ciao {user_name}," if user_name else "Ciao,"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 30px; 
                background-color: #f5a623; 
                color: #1a1a2e; 
                text-decoration: none; 
                border-radius: 8px;
                font-weight: bold;
            }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Benvenuto su Amazon Ads Manager!</h2>
            <p>{greeting}</p>
            <p>Grazie per esserti registrato. Per completare la registrazione e attivare il tuo account, clicca sul pulsante qui sotto:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}" class="button">Verifica Email</a>
            </p>
            <p>Oppure copia e incolla questo link nel tuo browser:</p>
            <p style="word-break: break-all; color: #666;">{verification_link}</p>
            <p>Questo link scade tra 24 ore.</p>
            <div class="footer">
                <p>Se non hai richiesto questa registrazione, ignora questa email.</p>
                <p>Amazon Ads Manager Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        logger.info(f"Verification email sent to {to_email}: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {to_email}: {e}")
        return False


def send_affiliate_referral_notification(
    affiliate_email: str,
    affiliate_code: str,
    commission: float,
    amount_paid: float,
    tier: str,
):
    api_key, _ = get_resend_credentials()
    if not api_key:
        api_key = RESEND_API_KEY
    if not api_key:
        logger.error("No Resend API key available")
        return False

    from_email = "Essentia Suite <noreply@anonimapublishing.online>"
    resend.api_key = api_key

    tier_label = "Diamond" if tier == "diamond" else "Platinum"
    commission_rate = "20%" if tier == "diamond" else "10%"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; background: #f4f4f4; }}
            .container {{ max-width: 600px; margin: 20px auto; padding: 30px; background: white; border-radius: 8px; }}
            .badge {{ display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: bold;
                      background: {'#7c3aed' if tier == 'diamond' else '#0284c7'}; color: white; }}
            .amount {{ font-size: 32px; font-weight: bold; color: #00D4FF; }}
            .footer {{ margin-top: 24px; font-size: 12px; color: #888; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🎉 Nuovo Referral Affiliazione!</h2>
            <p>Un nuovo acquisto è stato registrato tramite il tuo link affiliato.</p>
            <table style="width:100%; border-collapse:collapse; margin: 16px 0;">
                <tr><td style="padding:6px 0; color:#666;">Codice affiliato:</td><td><strong>{affiliate_code}</strong> <span class="badge">{tier_label} {commission_rate}</span></td></tr>
                <tr><td style="padding:6px 0; color:#666;">Affiliato:</td><td>{affiliate_email}</td></tr>
                <tr><td style="padding:6px 0; color:#666;">Importo pagato:</td><td>${amount_paid:.2f}</td></tr>
                <tr><td style="padding:6px 0; color:#666;">Commissione maturata:</td><td class="amount">${commission:.2f}</td></tr>
            </table>
            <p>La commissione è in stato <strong>In attesa</strong> e andrà pagata manualmente dall'admin.</p>
            <div class="footer">Essentia Suite — Dashboard Admin: <a href="https://essentia-ads.io/admin">essentia-ads.io/admin</a></div>
        </div>
    </body>
    </html>
    """

    from backend.app.core.config import settings
    admin_email = settings.ADMIN_EMAIL

    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [admin_email],
            "subject": f"💰 Nuovo Referral {affiliate_code} — ${commission:.2f} commissione",
            "html": html_content
        })
        logger.info(f"Affiliate notification sent: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to send affiliate notification: {e}")
        return False


def send_password_reset_email(to_email: str, reset_link: str, user_name: str = None):
    api_key, from_email = get_resend_credentials()
    
    if not api_key:
        api_key = RESEND_API_KEY
    
    if not api_key:
        logger.error("No Resend API key available")
        return False
    
    from_email = "Amazon Ads Manager <noreply@anonimapublishing.online>"
    
    resend.api_key = api_key
    
    subject = "Reset Password - Amazon Ads Manager"
    greeting = f"Ciao {user_name}," if user_name else "Ciao,"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .button {{ 
                display: inline-block; 
                padding: 12px 30px; 
                background-color: #f5a623; 
                color: #1a1a2e; 
                text-decoration: none; 
                border-radius: 8px;
                font-weight: bold;
            }}
            .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Reset Password</h2>
            <p>{greeting}</p>
            <p>Hai richiesto il reset della password. Clicca sul pulsante qui sotto per creare una nuova password:</p>
            <p style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" class="button">Reset Password</a>
            </p>
            <p>Oppure copia e incolla questo link nel tuo browser:</p>
            <p style="word-break: break-all; color: #666;">{reset_link}</p>
            <p>Questo link scade tra 1 ora.</p>
            <div class="footer">
                <p>Se non hai richiesto il reset della password, ignora questa email.</p>
                <p>Amazon Ads Manager Team</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    try:
        result = resend.Emails.send({
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_content
        })
        logger.info(f"Password reset email sent to {to_email}: {result}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {to_email}: {e}")
        return False
