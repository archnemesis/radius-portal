from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask import abort, g, session

from radius_portal.utils.codes import generate_code

bp = Blueprint("users", __name__)


def _stash_code(username: str, code: str) -> None:
    pending = session.get("pending_codes", {})
    pending[username] = code
    session["pending_codes"] = pending


def _pop_code(username: str) -> str | None:
    pending = session.get("pending_codes", {})
    code = pending.pop(username, None)
    session["pending_codes"] = pending
    return code


def parse_expiration(s: str) -> str:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%b %d %Y %H:%M:%S")  # FreeRADIUS Expiration format
        except ValueError:
            continue
    raise ValueError("Invalid expiration format. Use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS.")


@bp.get("/")
def front_page():
    now = datetime.now()
    default_exp = now + timedelta(days=5)
    default_exp_str = default_exp.strftime("%Y-%m-%d %H:%M:%S")
    return render_template("create_user.html", default_expiration=default_exp_str)


@bp.get("/admin/users")
def admin_users_list():
    repo = current_app.extensions["radius_repo"]
    repo.ensure_schema()
    users = repo.list_users()
    return render_template("users.html", users=users)


@bp.post("/users/create")
def create_user():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    expiration_in = (request.form.get("expiration") or "").strip()

    if not username:
        flash("Username is required.")
        return redirect(url_for("users.index"))

    if repo.user_exists(username):
        flash(f"User {username} already exists.")
        return redirect(url_for("users.index"))

    code = generate_code(8)
    repo.upsert_radcheck(username, "Cleartext-Password", code)

    if expiration_in:
        try:
            exp = parse_expiration(expiration_in)
            repo.upsert_radcheck(username, "Expiration", exp)
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("users.index"))
    else:
        flash("Expiration is required.")
        return redirect(url_for("users.index"))

    actor = getattr(g, "remote_user", "unkown")
    
    repo.upsert_user_meta_on_create(
        username=username,
        actor=actor,
        note=None
    )

    repo.insert_audit_event(
        actor=actor,
        action="CREATE_USER",
        target_username=username,
        detail={"expiration_set": bool(expiration_in)}
    )

    _stash_code(username, code)
    return redirect(url_for("users.show_code", username=username))


@bp.get("/users/<username>/code")
def show_code(username: str):
    code = _pop_code(username)
    if not code:
        return redirect(url_for("users.front_page"))

    return render_template("code_reveal.html", username=username, code=code)


@bp.post("/admin/users/delete")
def delete_user():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    repo.delete_user(username)
    flash(f"Deleted user {username}.")
    return redirect(url_for("users.index"))


@bp.get("/admin/users/<username>")
def edit_user(username: str):
    repo = current_app.extensions["radius_repo"]
    repo.ensure_schema()
    user = repo.get_user_details(username)
    if not user:
        abort(404)

    meta = repo.get_user_meta(username)
    audit = repo.list_audit_events(username, limit=25)

    return render_template("user_edit.html", user=user, meta=meta, audit=audit)


@bp.post("/admin/users/<username>/delete")
def delete_user_for_user(username: str):
    repo = current_app.extensions["radius_repo"]
    repo.delete_user(username)

    actor = getattr(g, "remote_user", "unknown")
    repo.insert_audit_event(
        actor=actor,
        action="DELETE_USER",
        target_username=username,
        detail={},
    )

    flash(f"Deleted user {username}.")
    return redirect(url_for("users.index"))
