from app import app

from flask.json import jsonify


LEVELS = [
    {
        "name": "Beginner",
        "elo": 1350,
        "description": "The assistant will play at an Elo rating of 1350. This is a good level for beginners.",
    },
    {
        "name": "Intermediate",
        "elo": 1500,
        "description": "The assistant will play at an Elo rating of 1500. This is a good level for intermediate players.",  # noqa
    },
    {
        "name": "Advanced",
        "elo": 2000,
        "description": "The assistant will play at an Elo rating of 2000. This is a good level for advanced players.",
    },
    {
        "name": "Expert",
        "elo": 2500,
        "description": "The assistant will play at an Elo rating of 2500. This is a good level for expert players.",
    },
    {
        "name": "Grandmaster",
        "elo": 2850,
        "description": "The assistant will play at an Elo rating of 2850. This is a good level for grandmasters.",
    },
]


@app.route("/api/levels", methods=["GET"])
def get_levels():
    return jsonify(LEVELS)
