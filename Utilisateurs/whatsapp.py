import logging
import os
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

WHATSAPP_API_VERSION = "v18.0"
WHATSAPP_API_BASE = "https://graph.facebook.com"


def _env_bool(key, default=False):
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes", "on")


def envoyer_whatsapp(destinataire: str, message: str) -> None:
    token = os.environ.get("WHATSAPP_TOKEN", "")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")

    if not token or not phone_number_id:
        logger.warning(
            "WHATSAPP_TOKEN ou WHATSAPP_PHONE_NUMBER_ID non definis. "
            "Aucun message envoye a %s.",
            destinataire,
        )
        return

    url = (
        f"{WHATSAPP_API_BASE}/{WHATSAPP_API_VERSION}"
        f"/{phone_number_id}/messages"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": destinataire.lstrip("+"),
        "type": "text",
        "text": {"body": message},
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        logger.info("WhatsApp envoye a %s (status=%s)", destinataire, resp.status_code)
    except requests.RequestException as e:
        logger.error("Echec WhatsApp vers %s : %s", destinataire, e)


def notifier_livreur_whatsapp(telephone: str, commande) -> None:
    if not telephone or not telephone.startswith("+"):
        logger.warning("Telephone invalide pour WhatsApp : %s", telephone)
        return

    if _env_bool("WHATSAPP_DISABLE", False):
        logger.info("WhatsApp desactive via WHATSAPP_DISABLE=True")
        return

    message = (
        f"\U0001f4e6 *Nouvelle commande attribuée !*\n\n"
        f"Ticket : {commande.ticket}\n"
        f"Client : {commande.fullname or commande.user.username}\n"
        f"Téléphone : {commande.telephone}\n"
        f"Adresse : {commande.adresse or commande.ville or '—'}\n"
        f"Montant : {commande.total_price:,.0f} FCFA\n\n"
        f"Connectez-vous à votre tableau de bord livreur."
    )
    envoyer_whatsapp(telephone, message)
