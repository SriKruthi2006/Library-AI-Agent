# =============================================================================
#  Library AI Agent — SQLAlchemy Database Models
#  Database: SQLite (swap URI for PostgreSQL in production)
# =============================================================================

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ─────────────────────────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    session_id    = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name          = db.Column(db.String(120), default="Guest")
    student_id    = db.Column(db.String(40), index=True)
    email         = db.Column(db.String(180), index=True)
    password_hash = db.Column(db.String(256))           # hashed password
    course        = db.Column(db.String(80))
    semester      = db.Column(db.String(10))
    department    = db.Column(db.String(100))
    learning_level= db.Column(db.String(40), default="undergraduate")
    career_goal   = db.Column(db.String(200))
    interests     = db.Column(db.Text)           # comma-separated
    reading_streak= db.Column(db.Integer, default=0)
    reading_goal  = db.Column(db.Integer, default=0)  # books/month
    is_admin      = db.Column(db.Boolean, default=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    last_active   = db.Column(db.DateTime, default=datetime.utcnow)

    borrows       = db.relationship("BorrowRecord",  back_populates="user", cascade="all, delete-orphan")
    reservations  = db.relationship("Reservation",   back_populates="user", cascade="all, delete-orphan")
    reviews       = db.relationship("Review",        back_populates="user", cascade="all, delete-orphan")
    notifications = db.relationship("Notification",  back_populates="user", cascade="all, delete-orphan")
    favorites     = db.relationship("Favorite",      back_populates="user", cascade="all, delete-orphan")
    search_history= db.relationship("SearchHistory", back_populates="user", cascade="all, delete-orphan")

    @property
    def is_registered(self):
        return bool(self.email and self.password_hash)

    def to_dict(self):
        return {
            "id": self.id, "session_id": self.session_id,
            "name": self.name, "student_id": self.student_id,
            "email": self.email, "course": self.course,
            "semester": self.semester, "department": self.department,
            "learning_level": self.learning_level, "career_goal": self.career_goal,
            "interests": self.interests, "reading_streak": self.reading_streak,
            "reading_goal": self.reading_goal, "is_admin": self.is_admin,
            "is_registered": self.is_registered,
            "created_at": self.created_at.strftime("%d %b %Y") if self.created_at else "",
        }


class Author(db.Model):
    __tablename__ = "authors"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False, index=True)

    books = db.relationship("BookAuthor", back_populates="author")


class Category(db.Model):
    __tablename__ = "categories"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    icon = db.Column(db.String(60), default="bi-folder")

    books = db.relationship("Book", back_populates="category_ref")


class Book(db.Model):
    __tablename__ = "books"
    id               = db.Column(db.Integer, primary_key=True)
    book_id          = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title            = db.Column(db.String(300), nullable=False)
    edition          = db.Column(db.String(80))
    publisher        = db.Column(db.String(200))
    year             = db.Column(db.Integer)
    isbn             = db.Column(db.String(30), index=True)
    category_id      = db.Column(db.Integer, db.ForeignKey("categories.id"))
    subcategory      = db.Column(db.String(120))
    subjects         = db.Column(db.Text)   # comma-separated
    courses          = db.Column(db.Text)   # comma-separated
    tags             = db.Column(db.Text)   # comma-separated
    location         = db.Column(db.String(100))
    shelf_number     = db.Column(db.String(40))
    total_copies     = db.Column(db.Integer, default=1)
    available_copies = db.Column(db.Integer, default=1)
    summary          = db.Column(db.Text)
    ai_summary       = db.Column(db.Text)
    rating           = db.Column(db.Float, default=4.0)
    cover_url        = db.Column(db.String(500))
    pdf_url          = db.Column(db.String(500))
    is_digital       = db.Column(db.Boolean, default=False)
    resource_type    = db.Column(db.String(40), default="book")  # book/journal/paper/ebook/thesis
    times_borrowed   = db.Column(db.Integer, default=0)
    is_active        = db.Column(db.Boolean, default=True)
    added_at         = db.Column(db.DateTime, default=datetime.utcnow)

    category_ref = db.relationship("Category",    back_populates="books")
    book_authors = db.relationship("BookAuthor",  back_populates="book",  cascade="all, delete-orphan")
    borrows      = db.relationship("BorrowRecord",back_populates="book",  cascade="all, delete-orphan")
    reservations = db.relationship("Reservation", back_populates="book",  cascade="all, delete-orphan")
    reviews      = db.relationship("Review",      back_populates="book",  cascade="all, delete-orphan")
    favorites    = db.relationship("Favorite",    back_populates="book",  cascade="all, delete-orphan")

    @property
    def authors_list(self):
        return [ba.author.name for ba in self.book_authors]

    @property
    def subjects_list(self):
        return [s.strip() for s in (self.subjects or "").split(",") if s.strip()]

    @property
    def courses_list(self):
        return [c.strip() for c in (self.courses or "").split(",") if c.strip()]

    @property
    def tags_list(self):
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def to_dict(self, include_authors=True):
        d = {
            "id":               self.book_id,
            "db_id":            self.id,
            "title":            self.title,
            "edition":          self.edition or "",
            "publisher":        self.publisher or "",
            "year":             self.year,
            "isbn":             self.isbn or "",
            "category":         self.category_ref.name if self.category_ref else "",
            "subcategory":      self.subcategory or "",
            "subjects":         self.subjects_list,
            "courses":          self.courses_list,
            "tags":             self.tags_list,
            "location":         self.location or "",
            "shelf_number":     self.shelf_number or "",
            "total_copies":     self.total_copies,
            "available_copies": self.available_copies,
            "summary":          self.summary or "",
            "ai_summary":       self.ai_summary or "",
            "rating":           self.rating,
            "cover_url":        self.cover_url or "",
            "pdf_url":          self.pdf_url or "",
            "is_digital":       self.is_digital,
            "resource_type":    self.resource_type,
            "times_borrowed":   self.times_borrowed,
            "added_at":         self.added_at.strftime("%Y-%m-%d") if self.added_at else "",
        }
        if include_authors:
            d["authors"] = self.authors_list
        return d


class BookAuthor(db.Model):
    __tablename__ = "book_authors"
    id        = db.Column(db.Integer, primary_key=True)
    book_id   = db.Column(db.Integer, db.ForeignKey("books.id"),   nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=False)
    order     = db.Column(db.Integer, default=0)

    book   = db.relationship("Book",   back_populates="book_authors")
    author = db.relationship("Author", back_populates="books")


class BorrowRecord(db.Model):
    __tablename__ = "borrow_records"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id      = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    borrow_date  = db.Column(db.DateTime, default=datetime.utcnow)
    due_date     = db.Column(db.DateTime)
    return_date  = db.Column(db.DateTime)
    status       = db.Column(db.String(20), default="borrowed")   # borrowed/returned/overdue
    renewed_count= db.Column(db.Integer, default=0)
    fine_amount  = db.Column(db.Float, default=0.0)
    fine_paid    = db.Column(db.Boolean, default=False)
    reading_progress = db.Column(db.Integer, default=0)  # 0-100 %

    user = db.relationship("User", back_populates="borrows")
    book = db.relationship("Book", back_populates="borrows")

    def to_dict(self):
        return {
            "id":           self.id,
            "book_id":      self.book.book_id if self.book else "",
            "title":        self.book.title if self.book else "",
            "authors":      self.book.authors_list if self.book else [],
            "borrow_date":  self.borrow_date.strftime("%d %b %Y") if self.borrow_date else "",
            "due_date":     self.due_date.strftime("%d %b %Y") if self.due_date else "",
            "return_date":  self.return_date.strftime("%d %b %Y") if self.return_date else "",
            "status":       self.status,
            "renewed_count":self.renewed_count,
            "fine_amount":  self.fine_amount,
            "fine_paid":    self.fine_paid,
            "reading_progress": self.reading_progress,
            "is_overdue":   self.status == "overdue",
        }


class Reservation(db.Model):
    __tablename__ = "reservations"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id      = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    reserved_at  = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at   = db.Column(db.DateTime)
    status       = db.Column(db.String(20), default="pending")   # pending/approved/cancelled/fulfilled
    position     = db.Column(db.Integer, default=1)
    notified     = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="reservations")
    book = db.relationship("Book", back_populates="reservations")

    def to_dict(self):
        return {
            "id":          self.id,
            "book_id":     self.book.book_id if self.book else "",
            "title":       self.book.title if self.book else "",
            "authors":     self.book.authors_list if self.book else [],
            "reserved_at": self.reserved_at.strftime("%d %b %Y") if self.reserved_at else "",
            "expires_at":  self.expires_at.strftime("%d %b %Y") if self.expires_at else "",
            "status":      self.status,
            "position":    self.position,
        }


class Review(db.Model):
    __tablename__ = "reviews"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id    = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    rating     = db.Column(db.Integer)   # 1–5
    comment    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="reviews")
    book = db.relationship("Book", back_populates="reviews")


class Notification(db.Model):
    __tablename__ = "notifications"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    type       = db.Column(db.String(40))   # due_date/reservation/fine/recommendation/new_arrival
    title      = db.Column(db.String(200))
    message    = db.Column(db.Text)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    book_id    = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=True)

    user = db.relationship("User", back_populates="notifications")

    def to_dict(self):
        return {
            "id":         self.id,
            "type":       self.type,
            "title":      self.title,
            "message":    self.message,
            "is_read":    self.is_read,
            "created_at": self.created_at.strftime("%d %b %Y %H:%M") if self.created_at else "",
            "book_id":    self.book_id,
        }


class Favorite(db.Model):
    __tablename__ = "favorites"
    id      = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey("books.id"), nullable=False)
    added_at= db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="favorites")
    book = db.relationship("Book", back_populates="favorites")


class SearchHistory(db.Model):
    __tablename__ = "search_history"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    query      = db.Column(db.String(300))
    results    = db.Column(db.Integer, default=0)
    searched_at= db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", back_populates="search_history")


class Journal(db.Model):
    __tablename__ = "journals"
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(300), nullable=False)
    publisher  = db.Column(db.String(200))
    access     = db.Column(db.String(100))
    url        = db.Column(db.String(500))
    subjects   = db.Column(db.Text)
    impact_factor = db.Column(db.Float)
    is_open_access= db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id, "title": self.title,
            "publisher": self.publisher, "access": self.access,
            "url": self.url,
            "subjects": [s.strip() for s in (self.subjects or "").split(",") if s.strip()],
            "impact_factor": self.impact_factor,
            "is_open_access": self.is_open_access,
        }
