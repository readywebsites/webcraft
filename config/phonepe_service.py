"""
PhonePe Payment Gateway Standard Checkout (v2) Service Module
=============================================================
Rebuilt to use the modern PhonePe Standard Checkout (v2) flow with OAuth 2.0:
1. Client ID + Client Secret + Client Version (1) authentication
2. Automated OAuth 2.0 Access Token retrieval and caching
3. Hosted Checkout Payment initiation (POST /checkout/v2/pay)
4. Strict Server-Side Order Status verification (GET /checkout/v2/order/{orderId}/status)
5. Server-to-server Webhook processing (event checkout.order.completed / checkout.order.failed)
"""

import os
import time
import json
import logging
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)

# In-memory OAuth token cache
_TOKEN_CACHE = {
    "access_token": None,
    "expires_at": 0,  # Unix timestamp
    "env": None
}


def get_phonepe_env_config():
    """
    Reads PhonePe credentials and environment configurations from environment variables.
    All sensitive credentials stay strictly backend-side.
    """
    # Auto-load .env from project root if PHONEPE_CLIENT_ID not in os.environ
    if not os.environ.get('PHONEPE_CLIENT_ID'):
        from pathlib import Path
        base_dir = Path(__file__).resolve().parent.parent
        env_file = base_dir / '.env'
        if env_file.exists():
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    env_mode = os.environ.get('PHONEPE_ENV', 'PRODUCTION').strip().upper()
    client_id = os.environ.get('PHONEPE_CLIENT_ID', '').strip()
    client_secret = os.environ.get('PHONEPE_CLIENT_SECRET', '').strip()
    client_version = os.environ.get('PHONEPE_CLIENT_VERSION', '1').strip()
    merchant_id = os.environ.get('PHONEPE_MERCHANT_ID', '').strip()
    backend_url = os.environ.get('BACKEND_URL', os.environ.get('DOMAIN', 'https://webcraft.biz499.com')).strip().rstrip('/')
    if not backend_url.startswith('http://') and not backend_url.startswith('https://'):
        backend_url = f"https://{backend_url}"

    is_production = (env_mode == 'PRODUCTION')

    if is_production:
        oauth_url = 'https://api.phonepe.com/apis/identity-manager/v1/oauth/token'
        pay_url = 'https://api.phonepe.com/apis/pg/checkout/v2/pay'
        status_url_template = 'https://api.phonepe.com/apis/pg/checkout/v2/order/{merchant_order_id}/status'
    else:
        oauth_url = 'https://api-preprod.phonepe.com/apis/pg-sandbox/v1/oauth/token'
        pay_url = 'https://api-preprod.phonepe.com/apis/pg-sandbox/checkout/v2/pay'
        status_url_template = 'https://api-preprod.phonepe.com/apis/pg-sandbox/checkout/v2/order/{merchant_order_id}/status'

    return {
        "env_mode": env_mode,
        "is_production": is_production,
        "client_id": client_id,
        "client_secret": client_secret,
        "client_version": client_version,
        "merchant_id": merchant_id,
        "backend_url": backend_url,
        "oauth_url": oauth_url,
        "pay_url": pay_url,
        "status_url_template": status_url_template,
    }


def get_phonepe_access_token(force_refresh=False):
    """
    Retrieves a valid PhonePe OAuth 2.0 Access Token.
    Reuses cached token if still valid (with a 5-minute safety buffer before expiration).
    """
    global _TOKEN_CACHE
    config = get_phonepe_env_config()
    current_time = time.time()

    # Check cache (keep 300s / 5 min buffer)
    if not force_refresh and _TOKEN_CACHE["access_token"] and _TOKEN_CACHE["env"] == config["env_mode"]:
        if current_time < (_TOKEN_CACHE["expires_at"] - 300):
            return _TOKEN_CACHE["access_token"]

    if not config["client_id"] or not config["client_secret"]:
        error_msg = "PhonePe credentials missing: PHONEPE_CLIENT_ID and PHONEPE_CLIENT_SECRET must be set in backend .env."
        logger.error(error_msg)
        raise ValueError(error_msg)

    post_data = urllib.parse.urlencode({
        'client_id': config["client_id"],
        'client_secret': config["client_secret"],
        'grant_type': 'client_credentials',
        'client_version': config["client_version"]
    }).encode('utf-8')

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }

    req = urllib.request.Request(config["oauth_url"], data=post_data, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            access_token = data.get('access_token')
            expires_in = int(data.get('expires_in', 3600))

            if not access_token:
                raise ValueError(f"PhonePe OAuth response did not include access_token: {data}")

            _TOKEN_CACHE["access_token"] = access_token
            _TOKEN_CACHE["expires_at"] = current_time + expires_in
            _TOKEN_CACHE["env"] = config["env_mode"]

            logger.info("Successfully fetched fresh PhonePe OAuth access token.")
            return access_token
    except urllib.error.HTTPError as err:
        err_body = err.read().decode('utf-8', errors='ignore')
        logger.error("PhonePe OAuth HTTP Error %s: %s | Body: %s", err.code, err.reason, err_body)
        raise RuntimeError(f"PhonePe OAuth token retrieval failed ({err.code}): {err_body}")
    except Exception as exc:
        logger.error("PhonePe OAuth connection error: %s", str(exc))
        raise RuntimeError(f"PhonePe OAuth connection error: {str(exc)}")


def create_phonepe_checkout_session(merchant_order_id, amount_in_rupees, redirect_url=None, meta_info=None):
    """
    Creates a hosted checkout payment session with PhonePe Standard Checkout API (POST /checkout/v2/pay).
    
    Parameters:
        merchant_order_id (str): Unique merchant transaction ID (e.g. TXN_...).
        amount_in_rupees (float|int): Order amount in INR.
        redirect_url (str, optional): Redirection URL where customer returns after payment.
        meta_info (dict, optional): Additional user-defined meta info (UDFs).

    Returns:
        dict: {
            "success": bool,
            "merchant_order_id": str,
            "phonepe_order_id": str,
            "redirect_url": str,
            "state": str,
            "raw_response": dict,
            "error": str (if success is False)
        }
    """
    config = get_phonepe_env_config()
    token = get_phonepe_access_token()

    if not redirect_url:
        redirect_url = f"{config['backend_url']}/preview?merchantTransactionId={merchant_order_id}"

    # Amount in paise (1 INR = 100 paise)
    amount_in_paise = int(round(float(amount_in_rupees) * 100))

    payload = {
        "merchantOrderId": str(merchant_order_id),
        "amount": amount_in_paise,
        "expireAfter": 1200,  # 20 minutes expiration
        "paymentFlow": {
            "type": "PG_CHECKOUT",
            "merchantUrls": {
                "redirectUrl": redirect_url
            }
        }
    }

    if meta_info and isinstance(meta_info, dict):
        payload["metaInfo"] = meta_info

    req_body = json.dumps(payload).encode('utf-8')
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'O-Bearer {token}'
    }

    req = urllib.request.Request(config["pay_url"], data=req_body, headers=headers, method='POST')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            logger.info("PhonePe Checkout V2 Pay Success for %s: %s", merchant_order_id, resp_data)

            order_id = resp_data.get('orderId') or resp_data.get('data', {}).get('orderId', '')
            state = resp_data.get('state') or resp_data.get('data', {}).get('state', 'PENDING')
            hosted_redirect_url = resp_data.get('redirectUrl') or resp_data.get('data', {}).get('redirectUrl', '')

            return {
                "success": True,
                "merchant_order_id": merchant_order_id,
                "phonepe_order_id": order_id,
                "redirect_url": hosted_redirect_url,
                "state": state,
                "raw_response": resp_data
            }
    except urllib.error.HTTPError as err:
        err_body = err.read().decode('utf-8', errors='ignore')
        logger.error("PhonePe Pay API HTTP Error %s: %s | Body: %s", err.code, err.reason, err_body)
        try:
            parsed_err = json.loads(err_body)
        except Exception:
            parsed_err = {"message": err_body}

        return {
            "success": False,
            "merchant_order_id": merchant_order_id,
            "error": f"PhonePe API Error ({err.code}): {err_body}",
            "parsed_error": parsed_err,
            "raw_response": parsed_err
        }
    except Exception as exc:
        logger.error("PhonePe Pay API exception for %s: %s", merchant_order_id, str(exc))
        return {
            "success": False,
            "merchant_order_id": merchant_order_id,
            "error": str(exc),
            "raw_response": {}
        }


def check_phonepe_order_status(merchant_order_id):
    """
    Independently queries PhonePe's official Order Status API server-to-server:
    GET /apis/pg/checkout/v2/order/{merchantOrderId}/status

    Returns:
        dict: {
            "success": bool,
            "status": "SUCCESS" | "FAILED" | "PENDING",
            "is_paid": bool,
            "state": str,
            "order_id": str,
            "amount": int (paise),
            "payment_details": list,
            "raw_response": dict,
            "error": str (if failed)
        }
    """
    config = get_phonepe_env_config()
    token = get_phonepe_access_token()

    status_url = config["status_url_template"].format(merchant_order_id=merchant_order_id)
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'O-Bearer {token}'
    }

    req = urllib.request.Request(status_url, headers=headers, method='GET')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp_data = json.loads(resp.read().decode('utf-8'))
            logger.info("PhonePe Order Status API response for %s: %s", merchant_order_id, resp_data)

            state = str(resp_data.get('state') or resp_data.get('code') or '').upper()
            order_id = resp_data.get('orderId') or ''
            amount = resp_data.get('amount') or 0
            payment_details = resp_data.get('paymentDetails') or []

            # Check successful completion
            if state in ['COMPLETED', 'SUCCESS', 'PAYMENT_SUCCESS']:
                status_val = 'SUCCESS'
                is_paid = True
            elif state in ['FAILED', 'PAYMENT_ERROR', 'PAYMENT_FAILED', 'CANCELLED', 'EXPIRED']:
                status_val = 'FAILED'
                is_paid = False
            else:
                status_val = 'PENDING'
                is_paid = False

            return {
                "success": True,
                "status": status_val,
                "is_paid": is_paid,
                "state": state,
                "order_id": order_id,
                "amount": amount,
                "payment_details": payment_details,
                "raw_response": resp_data
            }
    except urllib.error.HTTPError as err:
        err_body = err.read().decode('utf-8', errors='ignore')
        logger.error("PhonePe Status API HTTP Error %s: %s | Body: %s", err.code, err.reason, err_body)
        return {
            "success": False,
            "status": "PENDING",
            "is_paid": False,
            "state": "ERROR",
            "error": f"Status query error ({err.code}): {err_body}",
            "raw_response": {"error": err_body}
        }
    except Exception as exc:
        logger.error("PhonePe Status API exception for %s: %s", merchant_order_id, str(exc))
        return {
            "success": False,
            "status": "PENDING",
            "is_paid": False,
            "state": "ERROR",
            "error": str(exc),
            "raw_response": {"error": str(exc)}
        }
