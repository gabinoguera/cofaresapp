from flask import Flask, render_template, request
from bigquery_client import get_products, generate_response

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        prompt = request.form["prompt"]
        products = get_products(prompt)
        response_text = generate_response(prompt, products)
        return render_template("results.html", prompt=prompt, products=products, response=response_text)
    return render_template("home.html")

if __name__ == "__main__":
    app.run(debug=True)
