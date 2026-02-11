from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask import abort

bp = Blueprint("users", __name__)


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
def index():
    repo = current_app.extensions["radius_repo"]
    repo.ensure_schema()
    users = repo.list_users()
    return render_template("users.html", users=users)


@bp.post("/users/create")
def create_user():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    expiration_in = (request.form.get("expiration") or "").strip()

    if not username:
        flash("Username is required.")
        return redirect(url_for("users.index"))

    if repo.user_exists(username):
        flash(f"User {username} already exists.")
        return redirect(url_for("users.index"))

    repo.upsert_radcheck(username, "Cleartext-Password", password)

    if expiration_in:
        try:
            exp = parse_expiration(expiration_in)
            repo.upsert_radcheck(username, "Expiration", exp)
        except ValueError as e:
            flash(str(e))
            return redirect(url_for("users.index"))

    flash(f"Created user {username}.")
    return redirect(url_for("users.index"))


@bp.post("/users/set_password")
def set_password():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not repo.user_exists(username):
        flash(f"User {username} does not exist.")
        return redirect(url_for("users.index"))

    repo.upsert_radcheck(username, "Cleartext-Password", password)
    flash(f"Updated password for {username}.")
    return redirect(url_for("users.index"))


@bp.post("/users/set_expiration")
def set_expiration():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    expiration_in = (request.form.get("expiration") or "").strip()

    if not repo.user_exists(username):
        flash(f"User {username} does not exist.")
        return redirect(url_for("users.index"))

    try:
        exp = parse_expiration(expiration_in)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("users.index"))

    repo.upsert_radcheck(username, "Expiration", exp)
    flash(f"Set expiration for {username} to {exp}.")
    return redirect(url_for("users.index"))


@bp.post("/users/clear_expiration")
def clear_expiration():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    repo.delete_radcheck_attr(username, "Expiration")
    flash(f"Cleared expiration for {username}.")
    return redirect(url_for("users.index"))


@bp.post("/users/delete")
def delete_user():
    repo = current_app.extensions["radius_repo"]
    username = (request.form.get("username") or "").strip()
    repo.delete_user(username)
    flash(f"Deleted user {username}.")
    return redirect(url_for("users.index"))


@bp.get("/users/<username>")
def edit_user(username: str):
    repo = current_app.extensions["radius_repo"]
    repo.ensure_schema()
    user = repo.get_user_details(username)
    if not user:
        abort(404)
    return render_template("user_edit.html", user=user)


@bp.post("/users/<username>/set_password")
def set_password_for_user(username: str):
    repo = current_app.extensions["radius_repo"]
    password = request.form.get("password") or ""
    if not repo.user_exists(username):
        abort(404)

    repo.upsert_radcheck(username, "Cleartext-Password", password)
    flash(f"Updated password for {username}.")
    return redirect(url_for("users.edit_user", username=username))


@bp.post("/users/<username>/set_expiration")
def set_expiration_for_user(username: str):
    repo = current_app.extensions["radius_repo"]
    expiration_in = (request.form.get("expiration") or "").strip()
    if not repo.user_exists(username):
        abort(404)

    try:
        exp = parse_expiration(expiration_in)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("users.edit_user", username=username))

    repo.upsert_radcheck(username, "Expiration", exp)
    flash(f"Set expiration for {username} to {exp}.")
    return redirect(url_for("users.edit_user", username=username))


@bp.post("/users/<username>/clear_expiration")
def clear_expiration_for_user(username: str):
    repo = current_app.extensions["radius_repo"]
    if not repo.user_exists(username):
        abort(404)

    repo.delete_radcheck_attr(username, "Expiration")
    flash(f"Cleared expiration for {username}.")
    return redirect(url_for("users.edit_user", username=username))


@bp.post("/users/<username>/delete")
def delete_user_for_user(username: str):
    repo = current_app.extensions["radius_repo"]
    repo.delete_user(username)
    flash(f"Deleted user {username}.")
    return redirect(url_for("users.index"))
