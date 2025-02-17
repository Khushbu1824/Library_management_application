from flask import Flask, render_template, request, redirect, flash, session, url_for, jsonify, make_response
from bcrypt import hashpw, gensalt, checkpw
from models import initialize_db, Book, Membership, Admin, Transaction, db
from datetime import datetime
from weasyprint import HTML
import json 

app = Flask(__name__)
app.secret_key = "12345"
# Initialize the database when the app starts
initialize_db()

@app.route('/')
def home():
    return render_template("home.html")

from peewee import fn

@app.route('/admin/2703')
def admin():
    try:
        # Ensure database connection is open
        if db.is_closed():
            db.connect()

        # Calculate the total number of books by summing up the number of available books from the Book table
        total_books = Book.select(fn.SUM(Book.num_books_available)).scalar()

        # Calculate the total number of members by counting the rows in the Membership table
        total_members = Membership.select().count()

        # Calculate the total number of borrowed books by counting the transactions in the Transaction table
        borrowed_books = Transaction.select().where(Transaction.status == 'borrowed').count()

        # Return the data to the template
        return render_template('admin.html', total_books=total_books, total_members=total_members, borrowed_books=borrowed_books)
    except Exception as e:
        return render_template('admin.html', error=str(e))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        membership = Membership.get_or_none(Membership.email == email)

        if membership:
            stored_hash = membership.password

            entered_password_encoded = password.encode('utf-8')

            # Decode the stored hash from memoryview to bytes if needed
            if isinstance(stored_hash, memoryview):
                stored_hash = bytes(stored_hash)  # Convert memoryview to bytes

            if checkpw(entered_password_encoded, stored_hash):
                session['user_id'] = membership.membership_id  # Store user_id in session
                return redirect(url_for('bookslist', membership_id=membership.membership_id))
            else:
                error_message = 'Incorrect password'
        else:
            error_message = 'User not found'

        return render_template('login.html', error_message=error_message)

    return render_template('login.html')

@app.route('/admin/login/2703', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = Admin.get_or_none(Admin.username == username)

        if admin:
            stored_hash = admin.password

            entered_password_encoded = password.encode('utf-8')

            if isinstance(stored_hash, memoryview):
                stored_hash = bytes(stored_hash)


            if checkpw(entered_password_encoded, stored_hash):
                session['admin_logged_in'] = True  # Set session variable
                session['user_type'] = 'admin' #Set user type to admin in session
                return redirect(url_for('librarian_books'))  # Redirect to admin dashboard
            else:
                flash("Invalid username or password")
                return render_template('admin_login.html')  # Re-render login form
        else:
            flash("Invalid username or password")
            return render_template('admin_login.html')

    return render_template('admin-login.html')

@app.route('/books')
def books():
    # Retrieve all books from the database
    books_list = Book.select()
    authors = Book.select(Book.authors).distinct().scalars()
    genres = Book.select(Book.genre).distinct().scalars()
    return render_template("books.html", books=books_list, authors=authors, genres=genres)

@app.route('/books/<int:membership_id>')
def bookslist(membership_id):
    # Retrieve all books from the database
    books_list = Book.select()
    authors = Book.select(Book.authors).distinct().scalars()
    genres = Book.select(Book.genre).distinct().scalars()
    return render_template("books.html", books=books_list, authors=authors, genres=genres, membership_id=membership_id)

@app.route('/add-book', methods=['GET', 'POST'])
def add_book():
    if request.method == 'POST':
        try:
            if db.is_closed():
                db.connect()

            title = request.form['title']
            authors = request.form['authors']
            average_rating = request.form.get('average_rating')
            isbn = request.form['isbn']
            isbn13 = request.form['isbn13']
            language_code = request.form['language_code']
            num_pages = request.form['num_pages']
            ratings_count = request.form.get('ratings_count')
            text_reviews_count = request.form.get('text_reviews_count')
            publication_date_str = request.form['publication_date']

            try:
                publication_date = datetime.strptime(publication_date_str, '%Y-%m-%d').date()
            except ValueError:
                flash("Invalid publication date format!", "danger")
                return render_template('add-book.html')

            publisher = request.form['publisher']
            genre = request.form['genre']
            book_image = request.form['book_image']
            likes = request.form.get('likes')

            with db.atomic():
                Book.create(
                    title=title,
                    authors=authors,
                    average_rating=float(average_rating) if average_rating else 0.0,
                    isbn=isbn,
                    isbn13=isbn13,
                    language_code=language_code,
                    num_pages=int(num_pages) if num_pages else 0,  # Replace None with 0
                    ratings_count=int(ratings_count) if ratings_count else 0,  # Replace None with 0
                    text_reviews_count=int(text_reviews_count) if text_reviews_count else 0,  # Replace None with 0
                    publication_date=publication_date,
                    publisher=publisher,
                    genre=genre,
                    likes=int(likes) if likes else 0,
                    book_image=book_image
                )

            flash("Book added successfully!", "success")
            return redirect(url_for('books'))

        except Exception as e:
            flash(f"Error adding book: {str(e)}", "danger")
            print(f"Error: {e}")
            return render_template('add-book.html')

        finally:
            if not db.is_closed():
                db.close()

    return render_template('add-book.html')

@app.route('/edit-book/<int:book_id>', methods=['GET', 'POST'])
def edit_book(book_id):
    try:
        book = Book.get(Book.book_id == book_id)  # Fetch the book FIRST
    except Book.DoesNotExist:
        flash("Book not found!", "danger")
        return redirect(url_for('books'))  # Redirect to books list, not home

    if request.method == 'POST':
        book.title = request.form['title']
        book.authors = request.form['authors']
        book.average_rating = request.form['average_rating']
        book.isbn = request.form['isbn']
        book.isbn13 = request.form['isbn13']
        book.language_code = request.form['language_code']
        book.num_pages = request.form['num_pages']
        book.ratings_count = request.form['ratings_count']
        book.text_reviews_count = request.form['text_reviews_count']
        try:  # Handle potential date parsing errors
            book.publication_date = datetime.strptime(request.form['publication_date'], '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid publication date format!", "danger")
            return render_template('edit-book.html', book=book) #re-render the form with error

        book.publisher = request.form['publisher']
        book.genre = request.form['genre']
        book.likes = request.form['likes']
        book.book_image = request.form['book_image']

        book.save()
        flash("Book updated successfully!", "success")
        return redirect(url_for('books'))  # Redirect back to the book list

    return render_template('edit-book.html', book=book)

@app.route('/librarian_books')
def librarian_books():
    books_ls = Book.select()
    return render_template('librarian-books.html', books=books_ls)

@app.route('/delete-book/<int:book_id>')
def delete_book(book_id):
    book = Book.get_or_none(Book.book_id == book_id)

    if book is None:
        return "Book not found", 404

    book.delete_instance()  # Delete the book
    return redirect(url_for('librarian_books'))

@app.route('/transactions', methods=['POST'])
def transactions():
    issued_books_json = request.form.get("issuedBooks")

    if issued_books_json:
        try:
            issued_books = json.loads(issued_books_json)  # Crucial: Parse the JSON string
            book_ids = [book["bookId"] for book in issued_books]

            books_data = Book.select().where(Book.book_id.in_(book_ids)) #Query database

            book_list = [{"title": book.title, "isbn": book.isbn} for book in books_data] #Create list of book details
            
            return render_template("transactions.html", issued_books=book_list)  # Pass data to template
        except json.JSONDecodeError:
            return "Invalid JSON data", 400  # Handle JSON parsing errors
    else:
        return "No books issued", 400 #Handle no books issued error

    return jsonify({"success": False, "message": "No books issued!"})

@app.route("/new-membership")
def create_membership_form():
    return render_template("create-membership.html")

@app.route("/register", methods=["POST"])
def register():
    try:
        if db.is_closed():
            db.connect()
        # Retrieve form data
        name = request.form["name"]
        dob = datetime.strptime(request.form["dob"], "%Y-%m-%d").date()
        email = request.form["email"]
        contact_no = request.form["contact_no"]
        password = request.form["password"]  # Store securely in production!
        address = request.form["address"]
        membership_type = request.form["membership_type"]
        membership_start_date = datetime.strptime(request.form["membership_start_date"], "%Y-%m-%d").date()
        membership_expiry_date = datetime.strptime(request.form["membership_expiry_date"], "%Y-%m-%d").date()

        hashed_password_bytes = hashpw(password.encode('utf-8'), gensalt()) 

        print(f"Attempting to insert: {name}, {email}, {contact_no}")
        # Insert into database
        with db.atomic():  # Ensures transaction safety
            Membership.create(
                name=name,
                dob=dob,
                email=email,
                contact_no=contact_no,
                password=hashed_password_bytes,
                address=address,
                membership_type=membership_type,
                membership_start_date=membership_start_date,
                membership_expiry_date=membership_expiry_date,
                status="Active"
            )
        print("Data Inserted Successfully!")  # Debugging

        return redirect("/new-membership")

    except Exception as e:
        print(f"Database Error: {e}")  # Debugging
        return redirect("/new-membership")
    
    finally:
        if not db.is_closed():
            db.close()  # Close connection after operation

@app.route('/members')
def members():
    members_ls = Membership.select()
    return render_template('members.html', members=members_ls)

@app.route('/delete-member/<int:membership_id>')
def delete_member(membership_id):
    member = Membership.get_or_none(Membership.membership_id == membership_id)  # Assuming your Member model has a member_id

    if member is None:
        return "Member not found", 404

    member.delete_instance()
    return redirect(url_for('members')) 

@app.route('/edit-member/<int:member_id>', methods=['GET', 'POST'])
def edit_member(member_id):
    try:
        member = Membership.get(Membership.membership_id == member_id)  # Correct way to get the member
    except Membership.DoesNotExist:  # Correct exception to catch
        flash("Member not found!", "danger")
        return redirect(url_for('members'))  # Redirect to the correct route

    if request.method == 'POST':
        member.name = request.form['name']  # Access attributes through the member object
        try:
            member.dob = datetime.strptime(request.form['dob'], '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date of birth format!", "danger")
            return render_template('edit-member.html', member=member)  # Pass the member object

        member.email = request.form['email']
        member.contact_no = request.form['contact_no']
        member.address = request.form['address']
        member.status = request.form['status']

        if 'password' in request.form and request.form['password']:
            new_password = request.form['password']
            hashed_password_bytes = hashpw(new_password.encode('utf-8'), gensalt())
            member.password = hashed_password_bytes

        member.save()
        flash("Member updated successfully!", "success")
        return redirect(url_for('members'))  # Redirect to the correct route

    return render_template('edit-member.html', member=member) 

@app.route('/membership-renewal/<int:id>', methods=['GET', 'POST'])
def membership_renewal(id):
    try:
        membership = Membership.get_by_id(id)
    except Membership.DoesNotExist:
        flash("Membership record not found.")
        return redirect(url_for('books'))

    if request.method == 'GET':
        return render_template('membership-renewal.html', membership=membership)

    elif request.method == 'POST':
        try:
            new_expiry_date_str = request.form.get('new_expiry_date')
            new_expiry_date = datetime.strptime(new_expiry_date_str, '%Y-%m-%d').date() # Corrected line

            membership.membership_expiry_date = new_expiry_date
            membership.save()
            flash("Membership updated successfully!")
            return redirect(url_for('books'))

        except ValueError:
            flash("Invalid date format. Please use YYYY-MM-DD.")
            return render_template('membership-renewal.html', membership=membership)
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            return render_template('membership-renewal.html', membership=membership)

@app.route('/issued_books/<int:membership_id>')
def issued_books(membership_id):
    return render_template("success-page.html", membership_id=membership_id)

@app.route("/download/<int:membership_id>", methods=["POST"])
def download_pdf(membership_id):
    try:
        membership = Membership.get_by_id(membership_id)

        # Retrieve issued books from form input
        issued_books_json = request.form.get("issued_books")
        if not issued_books_json:
            return "No books provided", 400

        try:
            issued_books = json.loads(issued_books_json)
        except json.JSONDecodeError:
            return "Invalid JSON data", 400

        html = HTML(string=render_template("print/invoice.html", membership=membership, issued_books=issued_books))
        response = make_response(html.write_pdf())

        response.headers["Content-Type"] = "application/pdf"
        response.headers["Content-Disposition"] = f'attachment; filename="issued_books_{membership_id}.pdf"'

        return response

    except Membership.DoesNotExist:
        return "Membership not found", 404
    except Exception as e:
        return f"An error occurred: {str(e)}", 500
        
if __name__ == '__main__':
    app.run(debug=True)

@app.route("/issue-book/<int:membership_id>", methods=["POST"])
def issue_book_form(membership_id):
    issued_books_json = request.form.get("issuedBooks")
    issued_books = []  # Initialize an empty list

    if issued_books_json:
        try:
            issued_books = json.loads(issued_books_json)
        except json.JSONDecodeError:
            return "Invalid JSON data", 400

    membership = Membership.get_by_id(membership_id)

    # Now pass the potentially populated issued_books list to the template
    return render_template("transactions.html", membership=membership, issued_books=issued_books, membership_id=membership_id)

@app.route("/process-transaction", methods=["POST"])
def process_transaction():
    try:
        if db.is_closed():
            db.connect()
        
        print("Form Data:", request.form)

        user_id = int(request.form["membership_id"])  # Ensure integer conversion
        issue_date = datetime.strptime(request.form["issue_date"], "%Y-%m-%d").date()
        return_date = datetime.strptime(request.form["return_date"], "%Y-%m-%d").date()
        status = request.form["status"]

        book_ids = request.form.getlist("book_ids")  # Get a list of selected book IDs
        print(f"Membership ID: {user_id}")
        print(f"Book IDs: {book_ids}")
        print(f"Issue Date: {issue_date}")
        print(f"Return Date: {return_date}")
        print(f"Status: {status}")


        if not book_ids:
            return "No books selected", 400  # Handle case if no book is selected

        issued_books_list = []
        # Insert transactions for each selected book
        with db.atomic():
            for book_id in book_ids:
                book_id = int(book_id)  # Ensure integer conversion
                print(f"Attempting to insert: {book_id}, {user_id}, {issue_date}")
                book = Book.get_by_id(book_id)  # Assuming Book has a `get_by_id` method
                book_title = book.title
                isbn = book.isbn
                Transaction.create(
                    user_id=user_id,
                    book_id=book_id,
                    title = book_title,
                    isbn = isbn,
                    issue_date=issue_date,
                    return_date=return_date,
                    status=status
                )

                issued_books_list.append({
                    "book_id": book_id,
                    "title": book_title,
                    "authors": book.authors,
                    "isbn": isbn
                })

        print("Data Inserted Successfully!")
        return render_template("success-page.html", membership_id=user_id, issued_books=issued_books_list)

    except Exception as e:
        print(f"Error: {e}")
        return redirect(url_for('books'))

    finally:
        if not db.is_closed():
            db.close()

@app.route("/return-books/<int:membership_id>")
def return_books(membership_id):
    if db.is_closed():
        db.connect()

    # Fetch books borrowed by the user
    transactions = (
        Transaction.select(Transaction.transaction_id, Book.book_id, Book.title, Book.authors)
        .join(Book)
        .where((Transaction.user_id == membership_id) & (Transaction.status == "Issued"))
    )

    books = [
        {"transaction_id": t.transaction_id, "book_id": t.book.book_id, "title": t.book.title, "author": t.book.authors}
        for t in transactions
    ]

    db.close()

    return render_template("return-books.html", books=books)



from datetime import datetime

@app.route("/return-book", methods=["POST"])
def return_book():
    try:
        transaction_id = request.form.get("transaction_id")
        liked = request.form.get("liked") == "true"
        book_id = request.form.get("book_id")
        rating = int(request.form.get("rating", 0))  # Get the rating (0 if not provided)

        if db.is_closed():
            db.connect()

        # Fetch the transaction details to get the return date
        transaction = Transaction.select().where(Transaction.transaction_id == transaction_id).first()

        if not transaction:
            db.close()
            return jsonify({"success": False, "message": "Transaction not found."})

        # Get the return date from the transaction and convert it to datetime
        return_date = transaction.return_date
        if isinstance(return_date, datetime):
            return_date = return_date.date()  # Ensure it's a date object
        return_date = datetime.combine(return_date, datetime.min.time())  # Convert to datetime

        current_date = datetime.now()

        # Initialize fine variable
        fine = 0

        # Check if the return date has passed
        if return_date < current_date:
            # Calculate the number of days the book is overdue
            overdue_days = (current_date - return_date).days

            # Fine is calculated as 100 + (overdue_days * 10)
            fine = 100 + (overdue_days * 10)

        # Delete the transaction (return the book)
        deleted_rows = Transaction.delete().where(Transaction.transaction_id == transaction_id).execute()

        if deleted_rows > 0:
            # Update the number of available books
            Book.update(num_books_available=Book.num_books_available + 1).where(Book.book_id == book_id).execute()

            # If the book was liked, increment the like count
            if liked:
                Book.update(likes=Book.likes + 1).where(Book.book_id == book_id).execute()

            # If the rating is provided, update the rating count and average rating
            if rating > 0:
                book = Book.get(Book.book_id == book_id)

                # Calculate new average rating
                new_rating_count = book.ratings_count + 1
                new_total_rating = (book.average_rating * book.ratings_count) + rating
                new_average_rating = new_total_rating / new_rating_count

                # Update ratings count and average rating in the Book table
                Book.update(
                    ratings_count=new_rating_count,
                    average_rating=new_average_rating
                ).where(Book.book_id == book_id).execute()

            db.close()

            return jsonify({"success": True, "message": "Book returned successfully.", "fine": fine})
        else:
            db.close()
            return jsonify({"success": False, "message": "Transaction not found."})

    except Exception as e:
        db.close()
        return jsonify({"success": False, "message": str(e)})


if __name__ == '__main__':
    app.run(debug=True)
