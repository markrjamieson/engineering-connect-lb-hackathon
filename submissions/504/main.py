import os

from flask import Flask, jsonify

lb = Flask(__name__)


@lb.route("/", methods=["GET"])
def get_tasks():
    return jsonify({"message": "Hello World"})


if __name__ == "__main__":
    lb.run(debug=True, host="0.0.0.0", port=os.environ.get("PORT", 5000))
