"""Import CSV data into MongoDB Atlas (briecluster)."""
import csv
import os
import ast
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

client = MongoClient(os.environ['MONGO_URI'], serverSelectionTimeoutMS=10000)
db = client.Brie

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

GENRE_KEYS = [
    'crime', 'fantasy', 'young-adult', 'romance', 'comedy',
    'dystopia', 'action', 'historical', 'non-fiction',
    'science fiction', 'self-help',
]


def safe_int(val, default=-1):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def safe_float(val, default=-1.0):
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def parse_list(val):
    """Parse a string like "['word1', 'word2']" into a Python list."""
    if not val or val.strip() == '':
        return []
    try:
        result = ast.literal_eval(val)
        if isinstance(result, list):
            return result
    except (ValueError, SyntaxError):
        pass
    return []


def import_books():
    """Import final_1_combined.csv into the Books collection."""
    filepath = os.path.join(DATA_DIR, 'final_1_combined.csv')
    print(f'Importing Books from {filepath}...')

    docs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            genre_dissect = {}
            for key in GENRE_KEYS:
                col = key
                val = safe_float(row.get(col, '0'), 0.0)
                if val > 0:
                    genre_dissect[key] = val

            doc = {
                'id': safe_int(row['ID']),
                'title': row['Book Title'],
                'isbn': row['ISBN'],
                'rating': safe_float(row['Rating'], 0.0),
                'author': row['Author'],
                'language': row['Language'],
                'pages': safe_int(row['Pages']),
                'publication': row['Publication'],
                'pub_date': safe_int(row['Publish Date']),
                'pub_month': safe_int(row['Publish Month']),
                'pub_year': safe_int(row['Publish Year']),
                'genres': parse_list(row['Genres']),
                'image': row['Image'],
                'google_play_price': safe_float(row['Google Play']),
                'google_play_url': row['Google Play URL'],
                'barnes_and_noble_price': safe_float(row['Barnes and Noble']),
                'barnes_and_noble_url': row['Barnes and Noble URL'],
                'indie_price': safe_float(row['Indie Bound']),
                'indie_url': row['Indie Bound URL'],
                'amazon_price': safe_float(row['Amazon']),
                'amazon_url': row['Amazon URL'],
                'goodreads_desc': parse_list(row['GoodReads_Description']),
                'wiki_desc': parse_list(row['Wiki_Description']),
                'readgeek_desc': parse_list(row['Readgeek_Description']),
                'riffle_desc': parse_list(row['Riffle_Description']),
                'amazon_desc': parse_list(row['Amazon_Description']),
                'genre_dissect': genre_dissect,
            }
            docs.append(doc)

            if len(docs) >= 1000:
                db.Books.insert_many(docs)
                print(f'  inserted {len(docs)} books (total so far: ~{reader.line_num})')
                docs = []

    if docs:
        db.Books.insert_many(docs)

    count = db.Books.count_documents({})
    print(f'Books collection: {count} documents')


def import_similar_books():
    """Import sim_books_combined.csv into the Books_Similar collection."""
    filepath = os.path.join(DATA_DIR, 'sim_books_combined.csv')
    print(f'Importing Books_Similar from {filepath}...')

    docs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {'Id': safe_int(row['ID'])}
            for i in range(1, 11):
                doc[f'SIM{i}'] = safe_int(row[f'SIM{i}'])
            docs.append(doc)

            if len(docs) >= 1000:
                db.Books_Similar.insert_many(docs)
                print(f'  inserted {len(docs)} similar-book records')
                docs = []

    if docs:
        db.Books_Similar.insert_many(docs)

    count = db.Books_Similar.count_documents({})
    print(f'Books_Similar collection: {count} documents')


def import_goodreads_descriptions():
    """Import description.csv files from all batches into Books_GoodReads."""
    print('Building ISBN-to-ID lookup from Books collection...')
    isbn_to_id = {}
    for book in db.Books.find({}, {'id': 1, 'isbn': 1}):
        isbn_to_id[book['isbn']] = book['id']

    print(f'  Lookup has {len(isbn_to_id)} entries')

    batch_dirs = sorted(
        d for d in os.listdir(DATA_DIR)
        if d.startswith('batch_') and os.path.isdir(os.path.join(DATA_DIR, d))
    )

    docs = []
    seen_ids = set()

    for batch in batch_dirs:
        filepath = os.path.join(DATA_DIR, batch, 'description.csv')
        if not os.path.exists(filepath):
            continue

        print(f'  Reading {filepath}...')
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                isbn = row.get('ISBN', '')
                book_id = isbn_to_id.get(isbn)
                if book_id is None or book_id in seen_ids:
                    continue

                seen_ids.add(book_id)
                docs.append({
                    'id': book_id,
                    'goodreads_desc': row.get('GoodReads Description', ''),
                })

                if len(docs) >= 1000:
                    db.Books_GoodReads.insert_many(docs)
                    print(f'    inserted {len(docs)} descriptions')
                    docs = []

    if docs:
        db.Books_GoodReads.insert_many(docs)

    count = db.Books_GoodReads.count_documents({})
    print(f'Books_GoodReads collection: {count} documents')


def create_indexes():
    """Create indexes for common queries."""
    print('Creating indexes...')
    db.Books.create_index('id', unique=True)
    db.Books_Similar.create_index('Id', unique=True)
    db.Books_GoodReads.create_index('id', unique=True)
    print('Indexes created.')


if __name__ == '__main__':
    print('Dropping existing collections...')
    db.Books.drop()
    db.Books_Similar.drop()
    db.Books_GoodReads.drop()

    import_books()
    import_similar_books()
    import_goodreads_descriptions()
    create_indexes()
    print('\nDone!')
