import logging
from flask import Flask, request, jsonify
import time
import os

app = Flask(__name__)
books = []
bookID = 1
request_counter = 0

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure request-logger
request_logger = logging.getLogger('request-logger')
request_logger.setLevel(logging.INFO)
request_handler = logging.FileHandler('logs/requests.log')
request_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s: %(message)s | request #%(request_number)d', '%d-%m-%Y %H:%M:%S'))
request_logger.addHandler(request_handler)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s: %(message)s | request #%(request_number)d', '%d-%m-%Y %H:%M:%S'))
request_logger.addHandler(stream_handler)

# Configure books-logger
books_logger = logging.getLogger('books-logger')
books_logger.setLevel(logging.INFO)
books_handler = logging.FileHandler('logs/books.log')
books_handler.setFormatter(logging.Formatter('%(asctime)s.%(msecs)03d %(levelname)s: %(message)s | request #%(request_number)d', '%d-%m-%Y %H:%M:%S'))
books_logger.addHandler(books_handler)

# Function to update the request number in the logs
def update_request_number(logger, request_number):
    for handler in logger.handlers:
        handler.addFilter(lambda record: setattr(record, 'request_number', request_number) or True)

@app.before_request
def before_request():
    global request_counter
    request_counter += 1
    request.start_time = time.time()
    update_request_number(request_logger, request_counter)
    update_request_number(books_logger, request_counter)
    request_logger.info(f"Incoming request | #{request_counter} | resource: {request.path} | HTTP Verb {request.method.upper()}")

@app.after_request
def after_request(response):
    duration = int((time.time() - request.start_time) * 1000)
    request_logger.debug(f"request #{request_counter} duration: {duration}ms")
    return response

def log_error(logger, message, status_code):
    if status_code != 400:
        logger.error(message)

def checkHealth():
    return "OK", 200

def addBook():
    global bookID
    data = request.json
    title = data.get('title', '').lower()

    for book in books:
        if book['title'].lower() == title:
            error_message = f"Error: Book with the title [{data['title']}] already exists in the system"
            log_error(books_logger, error_message,409)
            return jsonify(errorMessage=error_message), 409

    year = data.get('year')
    if year < 1940 or year > 2100:
        error_message = f"Error: Can’t create new Book that its year [{year}] is not in the accepted range [1940 -> 2100]"
        log_error(books_logger, error_message,409)
        return jsonify(errorMessage=error_message), 409

    price = data.get('price')
    if price <= 0:
        error_message = "Error: Can’t create new Book with negative price"
        log_error(books_logger, error_message,409)
        return jsonify(errorMessage=error_message), 409

    newBook = {
        'id': bookID,
        'title': data['title'],
        'author': data['author'],
        'year': data['year'],
        'price': data['price'],
        'genres': data['genres']
    }

    books.append(newBook)
    books_logger.info(f"Creating new Book with Title [{data['title']}]")
    books_logger.debug(f"Currently there are {len(books) - 1} Books in the system. New Book will be assigned with id {bookID}")

    bookID += 1

    return jsonify(result=newBook['id']), 200

def filterBooks(author=None, priceMin=None, priceMax=None,
                yearMin=None, yearMax=None, genres=None):
    filteredBooks = books
    if author:
        filteredBooks = [book for book in filteredBooks if book['author'].lower() == author]
    if priceMin is not None:
        filteredBooks = [book for book in filteredBooks if book['price'] >= priceMin]
    if priceMax is not None:
        filteredBooks = [book for book in filteredBooks if book['price'] <= priceMax]
    if yearMin is not None:
        filteredBooks = [book for book in filteredBooks if book['year'] >= yearMin]
    if yearMax is not None:
        filteredBooks = [book for book in filteredBooks if book['year'] <= yearMax]
    if genres and genres[0]:
        filteredBooks = [book for book in filteredBooks if any(genre in book['genres'] for genre in genres)]

    return filteredBooks

def getTotalBooks():
    author = request.args.get('author', '').lower()
    priceMin = request.args.get('price-bigger-than', type=int)
    priceMax = request.args.get('price-less-than', type=int)
    yearMin = request.args.get('year-bigger-than', type=int)
    yearMax = request.args.get('year-less-than', type=int)
    genres = request.args.get('genres', '').split(',')

    filteredBooks = filterBooks(author, priceMin, priceMax, yearMin, yearMax, genres)
    books_logger.info(f"Total Books found for requested filters is {len(filteredBooks)}")
    return jsonify(result=len(filteredBooks)), 200

def getBooksList():
    author = request.args.get('author', '').lower()
    priceMin = request.args.get('price-bigger-than', type=int)
    priceMax = request.args.get('price-less-than', type=int)
    yearMin = request.args.get('year-bigger-than', type=int)
    yearMax = request.args.get('year-less-than', type=int)
    genres = request.args.get('genres', '').split(',')

    filteredBooks = filterBooks(author, priceMin, priceMax, yearMin, yearMax, genres)
    filteredBooks.sort(key=lambda x: x['title'].lower())
    books_logger.info(f"Total Books found for requested filters is {len(filteredBooks)}")
    return jsonify(result=filteredBooks), 200

def getSingleBook():
    bookID = request.args.get('id', type=int)
    for book in books:
        if book['id'] == bookID:
            books_logger.debug(f"Fetching book id {bookID} details")
            return jsonify(result=book), 200
    error_message = f"Error: no such Book with id {bookID}"
    log_error(books_logger, error_message,404)
    return jsonify(errorMessage=error_message), 404

def updateBookPrice():
    bookID = request.args.get('id', type=int)
    newPrice = request.args.get('price', type=int)

    for book in books:
        if book['id'] == bookID:
            if newPrice < 0:
                error_message = f"Error: price update for book [{bookID}] must be a positive integer"
                log_error(books_logger, error_message,409)
                return jsonify(errorMessage=error_message), 409
            oldPrice = book['price']
            book['price'] = newPrice
            books_logger.info(f"Update Book id [{bookID}] price to {newPrice}")
            books_logger.debug(f"Book [{book['title']}] price change: {oldPrice} --> {newPrice}")
            return jsonify(result=oldPrice), 200
    error_message = f"Error: no such Book with id {bookID}"
    log_error(books_logger, error_message,404)
    return jsonify(errorMessage=error_message), 404

def deleteBook():
    bookID = request.args.get('id', type=int)
    for book in books:
        if book['id'] == bookID:
            books_logger.info(f"Removing book [{book['title']}]")
            books.remove(book)
            books_logger.debug(f"After removing book [{book['title']}] id: [{bookID}] there are {len(books)} books in the system")
            return jsonify(result=len(books)), 200
    error_message = f"Error: no such Book with id {bookID}"
    log_error(books_logger, error_message,404)
    return jsonify(errorMessage=error_message), 404

@app.route('/logs/level', methods=['GET'])
def get_log_level():
    logger_name = request.args.get('logger-name')
    if logger_name == 'request-logger':
        level = logging.getLevelName(request_logger.level)
    elif logger_name == 'books-logger':
        level = logging.getLevelName(books_logger.level)
    else:
        return 'Logger not found', 404
    return level, 200

@app.route('/logs/level', methods=['PUT'])
def set_log_level():
    logger_name = request.args.get('logger-name')
    logger_level = request.args.get('logger-level').upper()
    level = getattr(logging, logger_level, None)
    if not isinstance(level, int):
        return 'Invalid log level', 400

    if logger_name == 'request-logger':
        request_logger.setLevel(level)
    elif logger_name == 'books-logger':
        books_logger.setLevel(level)
    else:
        return 'Logger not found', 404
    return logger_level, 200

app.add_url_rule('/books/health', 'checkHealth', checkHealth, methods=['GET'])
app.add_url_rule('/book', 'addBook', addBook, methods=['POST'])
app.add_url_rule('/books/total', 'getTotalBooks', getTotalBooks, methods=['GET'])
app.add_url_rule('/books', 'getBooksList', getBooksList, methods=['GET'])
app.add_url_rule('/book', 'getSingleBook', getSingleBook, methods=['GET'])
app.add_url_rule('/book', 'updateBookPrice', updateBookPrice, methods=['PUT'])
app.add_url_rule('/book', 'deleteBook', deleteBook, methods=['DELETE'])

if __name__ == '__main__':
    app.run(port=8574)
