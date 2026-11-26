"""Optional guide-answer wording only. Local code owns all appointment actions."""
import re
import httpx

from app.config import get_settings
from app.services.assistant_provider import ProviderResult, RuleBasedProvider


class CloudflareProvider:
    def reply(self, message, context):
        local = RuleBasedProvider().reply(message, context)
        settings = get_settings()
        token = settings.cloudflare_api_token.get_secret_value()
        if local.proposed_action or not local.citations or not token or not re.fullmatch(r"[a-fA-F0-9]{32}", settings.cloudflare_account_id):
            return local
        # Send public synthetic guide facts only, never patient identifiers,
        # appointment history, user messages or executable action instructions.
        try:
            response = httpx.post(
                f"https://api.cloudflare.com/client/v4/accounts/{settings.cloudflare_account_id}/ai/run/{settings.cloudflare_model}",
                headers={"Authorization": f"Bearer {token}"}, timeout=8,
                json={"messages": [
                    {"role": "system", "content": "Rewrite the supplied clinic information clearly in at most three sentences. Preserve all facts, numbers and restrictions. Add no medical advice or new facts."},
                    {"role": "user", "content": local.reply}], "max_tokens": 220, "temperature": 0},
            )
            response.raise_for_status()
            body = response.json()
            reply = body.get("result", {}).get("response")
            if not body.get("success") or not isinstance(reply, str) or not 1 <= len(reply.strip()) <= 1200:
                return local
            # Conservatively preserve numeric facts and disallow added numbers.
            if set(re.findall(r"\d+", reply)) != set(re.findall(r"\d+", local.reply)):
                return local
            return ProviderResult(reply=reply.strip(), citations=local.citations)
        except (httpx.HTTPError, ValueError, TypeError, AttributeError):
            return local
