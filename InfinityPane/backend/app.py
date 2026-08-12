from __future__ import annotations

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)

TEACHERS = [
    {"id": "T-001", "name": "Asha Patel", "subject": "Math"},
    {"id": "T-002", "name": "Rahul Mehta", "subject": "Computer Science"},
    {"id": "T-003", "name": "Mina Rao", "subject": "English"},
    {"id": "T-004", "name": "Priya Singh", "subject": "Physics"},
    {"id": "T-005", "name": "Ivan Arora", "subject": "Chemistry"},
]

SUBJECTS = [
    {"id": "S-101", "name": "Math"},
    {"id": "S-102", "name": "Computer Science"},
    {"id": "S-103", "name": "English"},
    {"id": "S-104", "name": "Physics"},
    {"id": "S-105", "name": "Chemistry"},
]

CLASSES = [
    {"id": "C-A", "name": "Computer Class A"},
    {"id": "C-B", "name": "Computer Class B"},
    {"id": "C-C", "name": "Science Class C"},
]


@app.get("/api/teachers")
def get_teachers():
    return jsonify(TEACHERS)


@app.get("/api/subjects")
def get_subjects():
    return jsonify(SUBJECTS)


@app.get("/api/classes")
def get_classes():
    return jsonify(CLASSES)


@app.get("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.get("/<path:path>")
def static_proxy(path: str):
    return send_from_directory(FRONTEND_DIR, path)


if __name__ == "__main__":
    app.run(debug=True)
