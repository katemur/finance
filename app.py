aimport os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
#export API_KEY=pk_f367572d687e46619133a8bf2af13a3c
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # receiving symbol and sum of shares from the database
    rows = db.execute(
        "SELECT symbol, SUM(shares) AS shares FROM transactions WHERE user_id=? GROUP BY symbol HAVING (SUM(shares)) > 0", session["user_id"])
    # receiving user's cash from the database
    cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
    cash = cash[0]["cash"]
    # counting the cost of all stocks
    total_stock = 0
    # gettting required information from lookup and stocks total for the table
    stocks = []
    for stock in rows:
        if stock.get("shares") == 0:
            continue
        quote = lookup(stock.get("symbol"))
        price = quote.get("price")
        st_total = price * stock.get("shares")
        stock["name"] = quote.get("name")
        stock["price"] = usd(price)
        stock["total"] = usd(st_total)
        stocks.append(stock)
        total_stock += st_total
    # counting the total of cash and stocks
    total = usd(total_stock + cash)
    cash = usd(cash)
    return render_template("index.html", stocks=stocks, cash=cash, total=total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # setting variables
        symbol = request.form.get("symbol")
        shares = request.form.get("shares")
        # check if the number of shares is negative
        try:
            shares = int(shares)
        except ValueError:
            return apology("must provide positive number of shares", 400)
        if int(shares) < 1:
            return apology("must provide positive number of shares", 400)
        quote = lookup(symbol)
        # check if the stock symbol is valid
        if not quote:
            return apology("Invalid symbol", 400)
        price = quote["price"]
        symb = quote["symbol"]
        name = quote["name"]
        time = datetime.now()
        # getting user's balance
        cash = db.execute("SELECT cash FROM users WHERE id= ?", session["user_id"])
        balance = cash[0]["cash"]
        new_balance = balance - int(shares) * price
        # check if user has given a number od shares
        if not shares:
            return apology("must provide number of shares", 400)
        # check if the user has enough cash to afford it and return an apology if the user can't afford it
        elif int(shares) * price > balance:
            return apology("Can't afford", 400)
        else:
            # run a SQL statement on database to purchase stock
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES(?, ?, ?, ?, ?)",
                       session["user_id"], symb, int(shares), price, time)
        # update cash to reflect purchased stock
            db.execute("UPDATE users SET cash = ? WHERE id = ?", new_balance, session["user_id"])
        # flash a success message
            flash("Successfully bought!")
        # Redirect user to home page
            return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # recieving symbol and sum of shares from the database
    rows = db.execute("SELECT symbol, shares, price, time FROM transactions WHERE user_id=?", session["user_id"])
    stocks = []
    for stock in rows:
        if stock.get("shares") == 0:
            continue
        stock["price"] = usd(stock["price"])
        stocks.append(stock)
    return render_template("history.html", stocks=stocks)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        symb = request.form.get("symbol")
        quote = lookup(symb)
        if not symb:
            return apology("Missing symbol", 400)
        elif not quote:
            return apology("Enter a valid stock symbol", 400)
        # if user didn't provide a stock quote

        else:
            symbol = quote["symbol"]
            name = quote["name"]
            price = usd(quote["price"])
            return render_template("quoted.html", symbol=symbol, name=name, price=price)
    else:
        # User reached route via GET (as by submitting a form via GET)
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        # hashing the password
        hashed_password = generate_password_hash(password, method="pbkdf2:sha256", salt_length=8)
        # Ensure username was submitted
        if not username:
            return apology("must provide username", 400)
        # Ensure password was submitted
        elif not password:
            return apology("must provide password", 400)
        # Ensure username doesn't exist
        elif len(rows) != 0:
            return apology("username already exists", 400)
        # Ensure confirmation was submitted
        elif not confirmation:
            return apology("must provide password confirmation", 400)
        # ensure confirmation matches password
        elif password != confirmation:
            return apology("Confirmation and password don't match", 400)
        else:
            # add the user to the database
            register = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashed_password)
            # login the user
            session["user_id"] = register
            # redirect user to homepage
            return redirect("/")
    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("registration.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # User reached route via POST
    if request.method == "POST":
        # setting variables
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))
        quote = lookup(symbol)
        # search if the user has that number of shares
        share_check = db.execute("SELECT SUM(shares) as has_shares FROM transactions WHERE user_id=?", session["user_id"])
        # check if the user has given a valid symbol
        if not symbol or not quote:
            return apology("must provide a valid symbol", 400)
        # check if the user provided a valid number of shares
        elif not shares or shares < 0:
            return apology("must provide valid number of shares")
        # check if the user has enough shares to sell
        elif not share_check or share_check[0]["has_shares"] < shares:
            return apology("Not enough shares to sell", 400)
        else:
            # run SQL statement on database to sell stocks
            price = quote["price"]
            symb = quote["symbol"]
            time = datetime.now()
            shares = -shares
            cash = db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])
            cash = cash[0]["cash"]
            new_balance = cash - shares * price
            db.execute("INSERT INTO transactions (user_id, symbol, shares, price, time) VALUES (?, ?, ?, ?, ?)",
                       session["user_id"], symb, shares, price, time)
            # update cash to reflect sold stocks
            db.execute("UPDATE users SET cash=? WHERE id=?", new_balance, session["user_id"])
            # flash a success message
            flash("Successfully sold!")
            return redirect("/")
        # User reached route via GET
    else:
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id=? GROUP BY symbol", session["user_id"])
        return render_template("sell.html", symbols=symbols)
