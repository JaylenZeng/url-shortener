# cli.py
import json
import os
from pathlib import Path

import typer
import httpx
from rich import print

app = typer.Typer()
CONFIG = Path.home() / ".shortener" / "config.json"
DEFAULT_URL = "https://your-demo.com"  


def load_config() -> dict:
    if CONFIG.exists():
        return json.loads(CONFIG.read_text())
    return {}

def save_config(data: dict):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data))
    CONFIG.chmod(0o600) 

def base_url() -> str:
    cfg = load_config()
    url = cfg.get("base_url") or os.getenv("SHORTENER_URL") or DEFAULT_URL
    return url.rstrip("/")

def load_token() -> str:
    token = load_config().get("token")
    if not token:
        print("[red]Not logged in. Run 'shortener login' first.[/red]")
        raise typer.Exit(1)
    return token

def auth_headers() -> dict:
    return {"Authorization": f"Bearer {load_token()}"}

@app.command()
def register(email: str):
    pw = typer.prompt("Password", hide_input=True, confirmation_prompt=True)
    resp = httpx.post(f"{base_url()}/auth/register", json={"email": email, "password": pw})
    if resp.status_code == 201:
        print("[green]Registered.[/green] Now run 'shortener login'.")
    else:
        print(f"[red]Failed:[/red] {resp.text}")
        raise typer.Exit(1)

@app.command()
def login(email: str):
    pw = typer.prompt("Password", hide_input=True)
    resp = httpx.post(f"{base_url()}/auth/login", json={"email": email, "password": pw})
    if resp.status_code == 200:
        cfg = load_config()
        cfg["token"] = resp.json()["access_token"]
        save_config(cfg)
        print("[green]Logged in.[/green]")
    else:
        print("[red]Login failed.[/red]")
        raise typer.Exit(1)

@app.command()
def create(url: str, alias: str = typer.Option(None, "--alias")):
    body = {"original_url": url}
    if alias:
        body["custom_alias"] = alias
    resp = httpx.post(f"{base_url()}/links", json=body, headers=auth_headers())
    print(resp.json())

@app.command()
def list():
    resp = httpx.get(f"{base_url()}/links", headers=auth_headers())
    for link in resp.json():
        print(f"{link['short_code']} -> {link['original_url']}")

@app.command()
def delete(link_id: int):
    resp = httpx.delete(f"{base_url()}/links/{link_id}", headers=auth_headers())
    if resp.status_code == 204:
        print("[green]Deleted.[/green]")
    else:
        print(f"[red]Failed:[/red] {resp.text}")

if __name__ == "__main__":
    app()