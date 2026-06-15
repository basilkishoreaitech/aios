import click
import httpx
import os
import sys

API_URL = "http://localhost:8000/api"
TOKEN_FILE = ".cli_token"

def get_headers():
    headers = {"Content-Type": "application/json"}
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
        headers["Authorization"] = f"Bearer {token}"
    return headers

@click.group()
def cli():
    """AIOS (Agentic Incident Operating System) Terminal Operator CLI."""
    pass

@cli.command()
@click.option("--username", default="engineer", help="Username for AIOS login")
@click.option("--password", default="aios-eng-2026", help="Password for AIOS login")
def login(username, password):
    """Authenticate SRE session and cache access token locally."""
    try:
        r = httpx.post(f"{API_URL}/auth/login", json={"username": username, "password": password})
        if r.status_code == 200:
            res = r.json()
            with open(TOKEN_FILE, "w") as f:
                f.write(res["access_token"])
            click.echo(click.style(f"✅ Successfully authenticated as {res['display_name']} ({res['role']})", fg="green"))
        else:
            click.echo(click.style(f"❌ Authentication failed: {r.text}", fg="red"), err=True)
    except Exception as e:
        click.echo(click.style(f"❌ Connection failed: {e}", fg="red"), err=True)

@cli.command()
@click.argument("question")
def query(question):
    """Run interactive natural language queries across SRE KB and DB."""
    try:
        headers = get_headers()
        r = httpx.post(f"{API_URL}/query", json={"question": question}, headers=headers)
        if r.status_code == 200:
            res = r.json()
            click.echo(click.style("\n=== AIOS RESPONSE ===", fg="green", bold=True))
            click.echo(res["answer"])
            
            click.echo(click.style("\n📄 Grounding Citations:", fg="cyan", bold=True))
            for i, cit in enumerate(res.get("citations", []), 1):
                click.echo(f"  [{i}] {cit['title']} ({cit['category']}) - relevance: {cit['relevance']:.2f}")
                
            click.echo(click.style(f"\nConfidence: {res['confidence'] * 100:.0f}%", fg="yellow"))
        elif r.status_code == 401:
            click.echo(click.style("❌ Unauthorized: Please login first using 'python cli.py login'", fg="red"), err=True)
        else:
            click.echo(f"Error: {r.text}", err=True)
    except Exception as e:
        click.echo(f"Connection failed: {e}", err=True)

@cli.command()
@click.argument("incident_id")
@click.argument("action_id")
def approve(incident_id, action_id):
    """Approve a pending recommended action (RBAC checked)."""
    try:
        headers = get_headers()
        r = httpx.post(
            f"{API_URL}/action/{action_id}/approve",
            json={"incident_id": incident_id, "decision": "approve"},
            headers=headers
        )
        if r.status_code == 200:
            res = r.json()
            click.echo(click.style(f"✅ Action executed: {res['message']}", fg="green"))
        elif r.status_code == 401:
            click.echo(click.style("❌ Unauthorized: Please login first using 'python cli.py login'", fg="red"), err=True)
        else:
            err_msg = r.json().get("detail", "Permission denied")
            click.echo(click.style(f"❌ Approval failed: {err_msg}", fg="red"), err=True)
    except Exception as e:
        click.echo(f"Connection failed: {e}", err=True)

if __name__ == "__main__":
    cli()
