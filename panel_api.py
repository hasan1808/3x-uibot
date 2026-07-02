import requests
import json
from datetime import datetime


class PanelAPI:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.token = None
        self.inbound_id = 1
        self._login(username, password)

    def _login(self, username, password):
        url = f"{self.base_url}/login"
        data = {"username": username, "password": password}
        resp = self.session.post(url, data=data)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("success"):
            raise Exception("Login failed: " + result.get("msg", "Unknown error"))
        self.token = result["token"]
        self.session.headers.update({"Cookie": f"session={self.token}"})

    def _get(self, path, params=None):
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path, data=None):
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, data=data)
        resp.raise_for_status()
        return resp.json()

    def get_inbounds(self):
        result = self._get("/api/inbounds")
        if result.get("success"):
            return result.get("obj", [])
        return []

    def get_inbound(self, inbound_id=None):
        iid = inbound_id or self.inbound_id
        result = self._get(f"/api/inbounds/{iid}")
        if result.get("success"):
            return result.get("obj")
        return None

    def get_clients(self, inbound_id=None):
        inbound = self.get_inbound(inbound_id)
        if not inbound:
            return []
        return inbound.get("clientStats", [])

    def get_client_info(self, email):
        inbounds = self.get_inbounds()
        for inbound in inbounds:
            for client in inbound.get("clientStats", []):
                if client.get("email") == email:
                    return {
                        "inbound": inbound,
                        "client": client,
                        "settings": self._parse_settings(inbound.get("settings", "")),
                    }
        return None

    def _parse_settings(self, settings_str):
        if not settings_str:
            return {}
        try:
            return json.loads(settings_str)
        except:
            return {}

    def find_client_by_email(self, email):
        inbounds = self.get_inbounds()
        for inbound in inbounds:
            settings = self._parse_settings(inbound.get("settings", ""))
            for client in settings.get("clients", []):
                if client.get("email") == email:
                    stats = None
                    for cs in inbound.get("clientStats", []):
                        if cs.get("email") == email:
                            stats = cs
                            break
                    return {
                        "inbound": inbound,
                        "client": client,
                        "stats": stats,
                    }
        return None

    def get_client_by_telegram_id(self, telegram_id):
        inbounds = self.get_inbounds()
        for inbound in inbounds:
            settings = self._parse_settings(inbound.get("settings", ""))
            for client in settings.get("clients", []):
                if client.get("subId") == str(telegram_id):
                    stats = None
                    for cs in inbound.get("clientStats", []):
                        if cs.get("email") == client.get("email"):
                            stats = cs
                            break
                    return {
                        "inbound": inbound,
                        "client": client,
                        "stats": stats,
                    }
        return None

    def get_all_clients(self):
        inbounds = self.get_inbounds()
        all_clients = []
        for inbound in inbounds:
            settings = self._parse_settings(inbound.get("settings", ""))
            for client in settings.get("clients", []):
                stats = None
                for cs in inbound.get("clientStats", []):
                    if cs.get("email") == client.get("email"):
                        stats = cs
                        break
                all_clients.append({
                    "inbound": inbound,
                    "client": client,
                    "stats": stats,
                })
        return all_clients


def format_bytes(bytes_val):
    if bytes_val is None or bytes_val == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while bytes_val >= 1024 and i < len(units) - 1:
        bytes_val /= 1024
        i += 1
    return f"{bytes_val:.2f} {units[i]}"


def format_expiry(expiry):
    if not expiry or expiry == 0:
        return "نامحدود"
    try:
        dt = datetime.fromtimestamp(expiry / 1000)
        now = datetime.now()
        delta = dt - now
        days = delta.days
        if days < 0:
            return "منقضی شده"
        return f"{dt.strftime('%Y-%m-%d')} ({days} روز باقیمانده)"
    except:
        return "نامشخص"
