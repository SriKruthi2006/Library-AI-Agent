# =============================================================================
#  Library AI Agent — Flask Backend
#  Powered by IBM watsonx.ai Granite Models
#  Author: Library AI Agent Project
# =============================================================================

import os
import io
import json
import uuid
import base64
import logging
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps

from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for
)
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# ── Load environment variables from .env ──────────────────────────────────────
load_dotenv()

# ── IBM watsonx.ai SDK ────────────────────────────────────────────────────────
try:
    from ibm_watsonx_ai import APIClient, Credentials
    from ibm_watsonx_ai.foundation_models import ModelInference
    from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
    from ibm_watsonx_ai.foundation_models.utils.enums import ModelTypes
    WATSONX_AVAILABLE = True
except ImportError:
    WATSONX_AVAILABLE = False

# ── QR Code ───────────────────────────────────────────────────────────────────
try:
    import qrcode
    from qrcode.image.pure import PyPNGImage
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# ── Models ────────────────────────────────────────────────────────────────────
from models import (
    db, User, Book, Author, Category, BookAuthor,
    BorrowRecord, Reservation, Review, Notification,
    Favorite, SearchHistory, Journal
)

# ── DB Folder ─────────────────────────────────────────────────────────────────
# Ensure the SQLite folder exists before any DB operation
_DB_DIR = Path(__file__).parent / "library"
_DB_DIR.mkdir(exist_ok=True)

# =============================================================================
#  AGENT INSTRUCTIONS
# =============================================================================
AGENT_INSTRUCTIONS = {

    # ── Persona & Tone ─────────────────────────────────────────────────────────
    "persona": (
        "You are Lexis, the intelligent AI librarian for the University Central Library. "
        "You are helpful, knowledgeable, warm, and concise. You speak in a professional yet "
        "friendly tone suitable for university students, researchers, and faculty. "
        "You never use slang, avoid very long responses, and always stay on topic."
    ),

    # ── Core Mission ───────────────────────────────────────────────────────────
    "mission": (
        "Your primary mission is to help students and researchers discover the best books, "
        "journals, research papers, and study resources for their courses and academic goals. "
        "You help with book recommendations, availability checks, reservations, borrowing history, "
        "and all library-related queries."
    ),

    # ── Recommendation Strategy ────────────────────────────────────────────────
    "recommendation_strategy": (
        "When recommending books: (1) Always match the user's course, semester, and subject. "
        "(2) Prefer books with high ratings and availability. (3) Include a mix of textbooks, "
        "reference books, and practical guides. (4) Mention the author, edition, and location. "
        "(5) Limit recommendations to 3–5 per response unless asked for more. "
        "(6) Briefly explain WHY each book is recommended."
    ),

    # ── Academic Specialisation ────────────────────────────────────────────────
    "academic_focus": (
        "You specialise in Computer Science, Engineering, Management, and Mathematics resources. "
        "You are familiar with standard university syllabi including B.Tech, M.Tech, MBA, MCA, "
        "B.Sc, and PhD programmes. You can align recommendations to semester requirements."
    ),

    # ── Language & Format Rules ────────────────────────────────────────────────
    "format_rules": (
        "Always use clear, structured responses. Use bullet points or numbered lists when "
        "listing books or steps. Keep responses under 350 words unless asked for details. "
        "For book recommendations include: Title, Author, Edition, and a one-line reason. "
        "For availability queries, always mention real-time status from the catalog."
    ),

    # ── Safety & Content Rules ─────────────────────────────────────────────────
    "safety_rules": (
        "Never provide answers unrelated to the library, academic resources, or learning. "
        "Do not discuss politics, religion, personal opinions, or non-academic topics. "
        "If asked something outside library scope, politely redirect to library topics. "
        "Never fabricate book ISBNs, authors, or availability data."
    ),

    # ── Summary Generation Instructions ───────────────────────────────────────
    "summary_instructions": (
        "When generating book summaries, write 3–5 sentences covering: (1) the main topic, "
        "(2) key chapters or concepts covered, (3) who the target audience is, and "
        "(4) why it is valuable. Keep it factual and engaging."
    ),

    # ── Greeting Message ───────────────────────────────────────────────────────
    "greeting": (
        "Hello! 👋 I'm **Lexis**, your AI Library Assistant. I can help you:\n"
        "• 📚 Find books, journals & research papers\n"
        "• 🎓 Get course-wise & subject-specific recommendations\n"
        "• 🔍 Check real-time book availability\n"
        "• 📖 Reserve books & manage your borrowing\n"
        "• ℹ️ Answer library rules, timings & service queries\n\n"
        "What would you like to explore today?"
    ),

    # ── Roadmap Generation Instructions ───────────────────────────────────────
    "roadmap_instructions": (
        "Generate a comprehensive learning roadmap with phases. For each phase list 3-5 specific "
        "books with titles and authors. Include: beginner resources, intermediate materials, "
        "advanced topics, and research papers."
    ),

    # ── Personalised Recommendation Instructions ───────────────────────────────
    "recommendation_instructions": (
        "Recommend books based on the student profile. Explain briefly why each book matches "
        "their course, semester, and learning goals."
    ),
}

# =============================================================================
#  Flask Application Setup
# =============================================================================
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(
    hours=int(os.getenv("SESSION_LIFETIME_HOURS", 24))
)
_default_db = "sqlite:///" + str(Path(__file__).parent / "library" / "library.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", _default_db)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["FINE_PER_DAY_INR"] = float(os.getenv("FINE_PER_DAY_INR", 2.0))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s"
)
logger = logging.getLogger(__name__)

# ── Initialise SQLAlchemy ─────────────────────────────────────────────────────
db.init_app(app)

# =============================================================================
#  Library Data Store — JSON fallback when DB is empty
# =============================================================================
DATA_PATH = Path(__file__).parent / "data" / "library_data.json"

def load_library_data() -> dict:
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not load library_data.json: %s", exc)
        return {"books": [], "journals": [], "courses": {}, "library_info": {
            "name": "University Central Library",
            "timings": {"weekdays": "8:00 AM – 10:00 PM", "saturday": "9:00 AM – 8:00 PM",
                        "sunday": "10:00 AM – 6:00 PM", "holidays": "Closed on public holidays"},
            "borrowing_rules": {
                "undergraduate": {"books": 4, "duration_days": 14, "renewals": 2},
                "postgraduate":  {"books": 6, "duration_days": 21, "renewals": 3},
                "faculty":       {"books": 10, "duration_days": 30, "renewals": 5},
            },
            "fines": {"per_day_inr": 2, "lost_book_fine": "Replacement cost + Rs. 200",
                      "damaged_book_fine": "50% of book price + Rs. 100"},
            "services": [], "contact": {"email": "library@university.edu", "phone": ""}
        }}

LIBRARY_DATA: dict = load_library_data()

# =============================================================================
#  IBM watsonx.ai Client
# =============================================================================
def get_watsonx_model():
    """Initialise IBM watsonx.ai model using env credentials."""
    if not WATSONX_AVAILABLE:
        raise RuntimeError("ibm-watsonx-ai package not installed")
    credentials = Credentials(
        url=os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
        api_key=os.getenv("IBM_API_KEY"),
    )
    client = APIClient(credentials)
    params = {
        GenParams.MAX_NEW_TOKENS:      600,
        GenParams.MIN_NEW_TOKENS:      30,
        GenParams.TEMPERATURE:         0.4,
        GenParams.TOP_P:               0.9,
        GenParams.TOP_K:               40,
        GenParams.REPETITION_PENALTY:  1.1,
        GenParams.STOP_SEQUENCES:      ["User:", "Human:", "---"],
    }
    model = ModelInference(
        model_id="ibm/granite-13b-chat-v2",
        params=params,
        credentials=credentials,
        project_id=os.getenv("WATSONX_PROJECT_ID"),
    )
    return model


# =============================================================================
#  Smart DB-backed Book Search
# =============================================================================
def search_books_db(query: str, limit: int = 12) -> list[dict]:
    """
    Smart SQLAlchemy search across title, authors, isbn, subjects,
    tags, courses, subcategory. Supports natural language — splits
    into keywords and scores each book. Falls back to JSON if DB empty.
    """
    try:
        total_in_db = db.session.query(Book).filter(Book.is_active == True).count()
    except Exception:
        total_in_db = 0

    if total_in_db == 0:
        # Graceful fallback to JSON data
        return _search_books_json(query, limit)

    q_lower  = query.lower().strip()
    keywords = [w for w in q_lower.split() if len(w) > 2]
    if not keywords:
        keywords = [q_lower] if q_lower else []

    scored: list[tuple[int, Book]] = []
    seen_ids: set[int] = set()

    for kw in keywords:
        like = f"%{kw}%"
        matches = (
            db.session.query(Book)
            .outerjoin(BookAuthor, Book.id == BookAuthor.book_id)
            .outerjoin(Author, BookAuthor.author_id == Author.id)
            .filter(Book.is_active == True)
            .filter(
                db.or_(
                    Book.title.ilike(like),
                    Book.isbn.ilike(like),
                    Book.subjects.ilike(like),
                    Book.tags.ilike(like),
                    Book.courses.ilike(like),
                    Book.subcategory.ilike(like),
                    Author.name.ilike(like),
                )
            )
            .distinct(Book.id)
            .all()
        )
        for book in matches:
            if book.id in seen_ids:
                # increment score for existing entry
                for i, (sc, b) in enumerate(scored):
                    if b.id == book.id:
                        scored[i] = (sc + 1, b)
                        break
            else:
                seen_ids.add(book.id)
                scored.append((1, book))

    scored.sort(key=lambda x: (-x[0], -(x[1].rating or 0)))
    return [b.to_dict() for _, b in scored[:limit]]


def _search_books_json(query: str, limit: int = 12) -> list[dict]:
    """Keyword search against the fallback JSON catalog."""
    q_lower  = query.lower()
    keywords = [w for w in q_lower.split() if len(w) > 2]
    scored: list[tuple[int, dict]] = []
    for book in LIBRARY_DATA.get("books", []):
        score = 0
        blob = " ".join([
            book.get("title", "").lower(),
            " ".join(book.get("authors", [])).lower(),
            book.get("category", "").lower(),
            book.get("subcategory", "").lower(),
            " ".join(book.get("subjects", [])),
            " ".join(book.get("tags", [])),
            " ".join(book.get("courses", [])),
            book.get("isbn", ""),
        ])
        for kw in keywords:
            if kw in blob:
                score += 1
        if score > 0:
            scored.append((score, book))
    scored.sort(key=lambda x: (-x[0], -x[1].get("rating", 0)))
    return [b for _, b in scored[:limit]]


# =============================================================================
#  Personalised Recommendations
# =============================================================================
def get_personalized_recommendations(user: User) -> dict:
    """Build recommendation buckets from DB data; falls back to JSON."""
    try:
        db_count = db.session.query(Book).filter(Book.is_active == True).count()
    except Exception:
        db_count = 0

    if db_count == 0:
        return _recommendations_from_json(user)

    course = user.course or ""

    # for_you — top-rated books matching the user's course
    for_you_q = db.session.query(Book).filter(Book.is_active == True)
    if course:
        for_you_q = for_you_q.filter(Book.courses.ilike(f"%{course}%"))
    for_you = (
        for_you_q.order_by(Book.rating.desc()).limit(6).all()
    )

    # trending — most borrowed
    trending = (
        db.session.query(Book)
        .filter(Book.is_active == True)
        .order_by(Book.times_borrowed.desc())
        .limit(6)
        .all()
    )

    # new_arrivals — most recently added
    new_arrivals = (
        db.session.query(Book)
        .filter(Book.is_active == True)
        .order_by(Book.added_at.desc())
        .limit(6)
        .all()
    )

    # most_borrowed (same as trending but explicit label)
    most_borrowed = trending[:4]

    # continue_learning — based on user's recent search history
    recent_terms: list[str] = []
    try:
        history_rows = (
            db.session.query(SearchHistory)
            .filter(SearchHistory.user_id == user.id)
            .order_by(SearchHistory.searched_at.desc())
            .limit(5)
            .all()
        )
        recent_terms = [h.query for h in history_rows if h.query]
    except Exception:
        pass

    continue_books: list[Book] = []
    seen_ids: set[int] = set()
    for term in recent_terms:
        results = search_books_db(term, limit=3)
        for r in results:
            db_id = r.get("db_id")
            if db_id and db_id not in seen_ids:
                seen_ids.add(db_id)
                continue_books.append(r)
        if len(continue_books) >= 6:
            break

    return {
        "for_you":          [b.to_dict() for b in for_you],
        "trending":         [b.to_dict() for b in trending],
        "new_arrivals":     [b.to_dict() for b in new_arrivals],
        "most_borrowed":    [b.to_dict() for b in most_borrowed],
        "continue_learning": continue_books[:6],
    }


def _recommendations_from_json(user: User) -> dict:
    """Fallback recommendations from JSON catalog."""
    books  = LIBRARY_DATA.get("books", [])
    course = user.course or ""

    for_you = sorted(
        [b for b in books if not course or any(course.lower() in c.lower() for c in b.get("courses", []))],
        key=lambda b: -b.get("rating", 0)
    )[:6]

    trending = sorted(books, key=lambda b: -b.get("rating", 0))[:6]
    new_arrivals = books[-6:][::-1]

    return {
        "for_you":           for_you,
        "trending":          trending,
        "new_arrivals":      new_arrivals,
        "most_borrowed":     trending[:4],
        "continue_learning": for_you[:4],
    }


# =============================================================================
#  Helper — catalog context for LLM
# =============================================================================
def build_catalog_context(books: list[dict]) -> str:
    lines = []
    for b in books:
        avail = f"{b.get('available_copies', 0)}/{b.get('total_copies', 0)} copies available"
        authors = b.get("authors", [])
        authors_str = ", ".join(authors) if isinstance(authors, list) else str(authors)
        lines.append(
            f"• [{b.get('id', '')}] \"{b.get('title', '')}\" by {authors_str} "
            f"({b.get('edition', '')}, {b.get('year', '')}) — "
            f"{b.get('category', '')}/{b.get('subcategory', '')} — "
            f"{avail} — Location: {b.get('location', '')} — Rating: {b.get('rating', 0)}/5"
        )
    return "\n".join(lines)


def build_library_info_context() -> str:
    info = LIBRARY_DATA.get("library_info", {})
    t    = info.get("timings", {})
    br   = info.get("borrowing_rules", {})
    f    = info.get("fines", {})
    ug   = br.get("undergraduate", {})
    pg   = br.get("postgraduate", {})
    return (
        f"Library: {info.get('name', 'University Central Library')}\n"
        f"Timings: Weekdays {t.get('weekdays','')}, Saturday {t.get('saturday','')}, Sunday {t.get('sunday','')}\n"
        f"Borrowing: UG={ug.get('books',4)} books/{ug.get('duration_days',14)} days, "
        f"PG={pg.get('books',6)} books/{pg.get('duration_days',21)} days\n"
        f"Fines: Rs. {f.get('per_day_inr',2)}/day overdue, Lost: {f.get('lost_book_fine','')}\n"
        f"Services: {', '.join(info.get('services', [])[:6])} …\n"
        f"Contact: {info.get('contact', {}).get('email','')}, {info.get('contact', {}).get('phone','')}"
    )


# =============================================================================
#  Core LLM Call
# =============================================================================
def query_granite(user_message: str, chat_history: list[dict],
                  extra_context: str = "") -> str:
    inst = AGENT_INSTRUCTIONS
    system_block = (
        f"{inst['persona']}\n\n"
        f"MISSION: {inst['mission']}\n\n"
        f"RECOMMENDATION STRATEGY: {inst['recommendation_strategy']}\n\n"
        f"ACADEMIC FOCUS: {inst['academic_focus']}\n\n"
        f"FORMAT: {inst['format_rules']}\n\n"
        f"SAFETY: {inst['safety_rules']}"
    )
    library_ctx   = build_library_info_context()
    context_block = f"LIBRARY INFORMATION:\n{library_ctx}"
    if extra_context:
        context_block += f"\n\nRELEVANT CATALOG ENTRIES:\n{extra_context}"

    history_block = ""
    for turn in chat_history[-6:]:
        role = "User" if turn["role"] == "user" else "Lexis"
        history_block += f"{role}: {turn['content']}\n"

    prompt = (
        f"<<SYS>>\n{system_block}\n\n{context_block}\n<</SYS>>\n\n"
        f"{history_block}"
        f"User: {user_message}\n"
        f"Lexis:"
    )
    try:
        model  = get_watsonx_model()
        result = model.generate_text(prompt=prompt)
        answer = result.strip()
        for prefix in ["Lexis:", "Assistant:", "AI:"]:
            if answer.startswith(prefix):
                answer = answer[len(prefix):].strip()
        return answer if answer else _fallback_response(user_message)
    except Exception as exc:
        logger.error("watsonx.ai error: %s", exc)
        return _fallback_response(user_message)


def _fallback_response(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["timing", "hour", "open", "close", "time"]):
        t = LIBRARY_DATA.get("library_info", {}).get("timings", {})
        return (
            f"📅 **Library Hours**\n"
            f"- Weekdays: {t.get('weekdays','')}\n"
            f"- Saturday: {t.get('saturday','')}\n"
            f"- Sunday: {t.get('sunday','')}\n"
            f"- Holidays: {t.get('holidays','')}"
        )
    if any(w in q for w in ["borrow", "issue", "fine", "renew"]):
        br = LIBRARY_DATA.get("library_info", {}).get("borrowing_rules", {})
        f  = LIBRARY_DATA.get("library_info", {}).get("fines", {})
        ug = br.get("undergraduate", {})
        pg = br.get("postgraduate", {})
        return (
            f"📋 **Borrowing Rules**\n"
            f"- UG: {ug.get('books',4)} books, {ug.get('duration_days',14)} days\n"
            f"- PG: {pg.get('books',6)} books, {pg.get('duration_days',21)} days\n"
            f"- Fine: Rs. {f.get('per_day_inr',2)}/day overdue"
        )
    books = _search_books_json(query, limit=4)
    if books:
        lines = ["📚 **Relevant Books Found**\n"]
        for b in books:
            authors = b.get("authors", [])
            first_author = authors[0] if authors else "Unknown"
            lines.append(
                f"**{b['title']}** by {first_author}  \n"
                f"  _{b.get('edition','')} · {b.get('location','')} · "
                f"{'✅ Available' if b.get('available_copies', 0) > 0 else '❌ Unavailable'}_"
            )
        return "\n".join(lines)
    return (
        "I'm here to help with book recommendations and library services. "
        "Could you please tell me your course, subject, or what kind of resource you're looking for?"
    )


# =============================================================================
#  before_request — ensure session + DB user record
# =============================================================================
@app.before_request
def ensure_session():
    """Assign a persistent session ID and get-or-create the User in DB."""
    if "session_id" not in session:
        session["session_id"] = str(uuid.uuid4())
        session["chat_history"] = []

    sid = session["session_id"]

    # Lazy DB user resolution — skip for static assets
    if request.path.startswith("/static"):
        return

    try:
        user = User.query.filter_by(session_id=sid).first()
        if not user:
            user = User(session_id=sid, name="Guest")
            db.session.add(user)
            db.session.commit()
        else:
            user.last_active = datetime.utcnow()
            db.session.commit()
        # Sync session profile from DB
        session["user_profile"] = {
            "name":       user.name,
            "course":     user.course or "",
            "semester":   user.semester or "",
            "student_id": user.student_id or "",
            "email":      user.email or "",
            "is_admin":   user.is_admin,
        }
    except Exception as exc:
        logger.warning("DB user lookup failed: %s", exc)
        if "user_profile" not in session:
            session["user_profile"] = {
                "name": "Guest", "course": "", "semester": "",
                "student_id": "", "email": "", "is_admin": False,
            }


def _get_current_user() -> "User | None":
    sid = session.get("session_id")
    if not sid:
        return None
    try:
        return User.query.filter_by(session_id=sid).first()
    except Exception:
        return None


def _login_required(f):
    """Decorator: returns 401 JSON if no authenticated user."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = _get_current_user()
        if not user or user.name == "Guest":
            return jsonify({"error": "Authentication required", "auth_required": True}), 401
        return f(*args, **kwargs)
    return wrapper


def _admin_required(f):
    """Decorator: returns 403 JSON if user is not admin."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = _get_current_user()
        if not user or not user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        return f(*args, **kwargs)
    return wrapper


def _compute_fine(record: BorrowRecord) -> float:
    """Calculate overdue fine for a borrow record (Rs/day)."""
    if record.status in ("returned",) or not record.due_date:
        return record.fine_amount or 0.0
    now = datetime.utcnow()
    if now > record.due_date:
        days_late = (now - record.due_date).days
        return days_late * app.config["FINE_PER_DAY_INR"]
    return 0.0


def _notify(user_id: int, notif_type: str, title: str, message: str, book_id: int = None):
    """Helper to create a notification without raising."""
    try:
        n = Notification(
            user_id=user_id, type=notif_type,
            title=title, message=message, book_id=book_id
        )
        db.session.add(n)
        db.session.commit()
    except Exception as exc:
        logger.warning("Notify failed: %s", exc)


# =============================================================================
#  Error Handlers
# =============================================================================
@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(403)
def forbidden(e):
    return jsonify({"error": "Forbidden"}), 403


@app.errorhandler(500)
def server_error(e):
    return jsonify({"error": "Internal server error"}), 500


# =============================================================================
#  EXISTING ROUTES — preserved exactly
# =============================================================================

# ── Home ──────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template(
        "index.html",
        greeting=AGENT_INSTRUCTIONS["greeting"],
        institution=LIBRARY_DATA.get("library_info", {}).get("name", "University Central Library"),
    )


# ── Chat API ──────────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    data         = request.get_json(silent=True) or {}
    user_message = (data.get("message") or "").strip()
    if not user_message:
        return jsonify({"error": "Empty message"}), 400

    profile = session.get("user_profile", {})
    history = session.get("chat_history", [])
    user    = _get_current_user()

    # Save search query to SearchHistory
    if user:
        try:
            sh = SearchHistory(user_id=user.id, query=user_message)
            db.session.add(sh)
            user.last_active = datetime.utcnow()
            db.session.commit()
        except Exception as exc:
            logger.warning("SearchHistory save failed: %s", exc)

    # Context enrichment via DB search
    relevant_books = search_books_db(user_message, limit=6)

    # Merge course-specific books if available
    course = profile.get("course", "")
    if course:
        course_books = search_books_db(course, limit=6)
        seen_ids = {b.get("id") for b in relevant_books}
        for b in course_books:
            if b.get("id") not in seen_ids:
                relevant_books.append(b)
                seen_ids.add(b.get("id"))

    extra_context = build_catalog_context(relevant_books[:8]) if relevant_books else ""
    reply = query_granite(user_message, history, extra_context)

    history.append({"role": "user",      "content": user_message})
    history.append({"role": "assistant", "content": reply})
    session["chat_history"] = history[-20:]

    book_cards = []
    for book in relevant_books[:4]:
        authors = book.get("authors", [])
        book_cards.append({
            "id":               book.get("id"),
            "title":            book.get("title"),
            "authors":          authors,
            "edition":          book.get("edition", ""),
            "category":         book.get("category", ""),
            "location":         book.get("location", ""),
            "available":        book.get("available_copies", 0) > 0,
            "available_copies": book.get("available_copies", 0),
            "total_copies":     book.get("total_copies", 0),
            "rating":           book.get("rating", 0),
            "summary":          book.get("summary", ""),
        })

    return jsonify({
        "reply":      reply,
        "book_cards": book_cards,
        "timestamp":  datetime.now().strftime("%H:%M"),
    })


# ── Book Search API ───────────────────────────────────────────────────────────
@app.route("/api/search")
def search_api():
    query  = request.args.get("q", "").strip()
    course = request.args.get("course", "")
    if not query and not course:
        return jsonify({"results": [], "count": 0})

    search_term = course if (course and not query) else query
    results     = search_books_db(search_term, limit=12)

    # Log to SearchHistory
    user = _get_current_user()
    if user and search_term:
        try:
            sh = SearchHistory(user_id=user.id, query=search_term, results=len(results))
            db.session.add(sh)
            db.session.commit()
        except Exception:
            pass

    return jsonify({"results": results, "count": len(results)})


# ── Book Detail API ───────────────────────────────────────────────────────────
@app.route("/api/book/<book_id>")
def book_detail(book_id: str):
    # Try DB first
    book_obj = None
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
    except Exception:
        pass

    if book_obj:
        book = book_obj.to_dict()
        similar_objs = (
            Book.query
            .filter(Book.subcategory == book_obj.subcategory, Book.book_id != book_id, Book.is_active == True)
            .order_by(Book.rating.desc())
            .limit(4)
            .all()
        )
        similar = [
            {"id": b.book_id, "title": b.title, "authors": b.authors_list,
             "available": b.available_copies > 0, "rating": b.rating}
            for b in similar_objs
        ]
        user       = _get_current_user()
        session_id = session.get("session_id", "")
        user_reserved = False
        waitlist_count = 0
        if user:
            try:
                res = Reservation.query.filter_by(
                    user_id=user.id, book_id=book_obj.id, status="pending"
                ).first()
                user_reserved  = res is not None
                waitlist_count = Reservation.query.filter_by(
                    book_id=book_obj.id, status="pending"
                ).count()
            except Exception:
                pass
        return jsonify({**book, "similar_books": similar,
                        "waitlist_count": waitlist_count, "user_reserved": user_reserved})

    # Fallback to JSON
    book = next((b for b in LIBRARY_DATA.get("books", []) if b["id"] == book_id), None)
    if not book:
        return jsonify({"error": "Book not found"}), 404
    similar = [
        {"id": b["id"], "title": b["title"], "authors": b["authors"],
         "available": b["available_copies"] > 0, "rating": b["rating"]}
        for b in LIBRARY_DATA["books"]
        if b["subcategory"] == book["subcategory"] and b["id"] != book_id
    ][:4]
    return jsonify({**book, "similar_books": similar, "waitlist_count": 0, "user_reserved": False})


# ── Reserve / Cancel Reservation ─────────────────────────────────────────────
@app.route("/api/reserve/<book_id>", methods=["POST"])
def reserve_book(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Session not found"}), 400

    book_obj = None
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
    except Exception:
        pass

    if not book_obj:
        # JSON fallback check
        if not any(b["id"] == book_id for b in LIBRARY_DATA.get("books", [])):
            return jsonify({"error": "Book not found"}), 404
        due_date = (datetime.now() + timedelta(days=14)).strftime("%d %b %Y")
        return jsonify({"message": f"✅ Reserved! Estimated due date: {due_date}",
                        "reserved": True, "position": 1})

    try:
        existing = Reservation.query.filter_by(
            user_id=user.id, book_id=book_obj.id, status="pending"
        ).first()
        if existing:
            return jsonify({"message": "Already reserved", "reserved": True})

        position = Reservation.query.filter_by(book_id=book_obj.id, status="pending").count() + 1
        expires  = datetime.utcnow() + timedelta(days=3)
        res = Reservation(
            user_id=user.id, book_id=book_obj.id,
            expires_at=expires, position=position
        )
        db.session.add(res)
        db.session.commit()
        due_date = (datetime.now() + timedelta(days=14)).strftime("%d %b %Y")
        return jsonify({
            "message":  f"✅ Reserved! Estimated due date: {due_date}",
            "reserved": True,
            "position": position,
        })
    except Exception as exc:
        logger.error("Reserve error: %s", exc)
        return jsonify({"error": "Reservation failed"}), 500


@app.route("/api/reserve/<book_id>", methods=["DELETE"])
def cancel_reservation(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"message": "Reservation cancelled", "reserved": False})
    try:
        book_obj = Book.query.filter_by(book_id=book_id).first()
        if book_obj:
            res = Reservation.query.filter_by(
                user_id=user.id, book_id=book_obj.id, status="pending"
            ).first()
            if res:
                res.status = "cancelled"
                db.session.commit()
    except Exception as exc:
        logger.warning("Cancel reservation error: %s", exc)
    return jsonify({"message": "Reservation cancelled", "reserved": False})


# ── User Profile ──────────────────────────────────────────────────────────────
@app.route("/api/profile", methods=["GET", "POST"])
def profile():
    user = _get_current_user()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        profile_data = {
            "name":       data.get("name", "Student"),
            "course":     data.get("course", ""),
            "semester":   data.get("semester", ""),
            "student_id": data.get("student_id", ""),
            "email":      data.get("email", ""),
        }
        session["user_profile"] = profile_data
        if user:
            try:
                user.name       = profile_data["name"]
                user.course     = profile_data["course"]
                user.semester   = profile_data["semester"]
                user.student_id = profile_data["student_id"]
                user.email      = profile_data["email"]
                if data.get("department"):
                    user.department = data["department"]
                if data.get("learning_level"):
                    user.learning_level = data["learning_level"]
                if data.get("career_goal"):
                    user.career_goal = data["career_goal"]
                if data.get("interests"):
                    user.interests = data["interests"]
                if data.get("reading_goal") is not None:
                    user.reading_goal = int(data["reading_goal"])
                db.session.commit()
            except Exception as exc:
                logger.warning("Profile DB save failed: %s", exc)
        return jsonify({"message": "Profile saved", "profile": profile_data})

    if user:
        return jsonify(user.to_dict())
    return jsonify(session.get("user_profile", {}))


# ── Borrowing History ─────────────────────────────────────────────────────────
@app.route("/api/history")
def borrow_history():
    user = _get_current_user()
    if not user:
        return jsonify({"history": [], "count": 0})
    try:
        records = (
            BorrowRecord.query
            .filter_by(user_id=user.id)
            .order_by(BorrowRecord.borrow_date.desc())
            .all()
        )
        # Update overdue status and compute fines on the fly
        now = datetime.utcnow()
        changed = False
        for r in records:
            if r.status == "borrowed" and r.due_date and r.due_date < now:
                r.status = "overdue"
                r.fine_amount = _compute_fine(r)
                changed = True
        if changed:
            db.session.commit()
        result = []
        for r in records:
            d = r.to_dict()
            d["fine_amount"] = _compute_fine(r)
            result.append(d)
        total_fine = sum(r.fine_amount for r in records if not r.fine_paid and r.fine_amount > 0)
        return jsonify({"history": result, "count": len(result), "total_fine_due": round(total_fine, 2)})
    except Exception as exc:
        logger.error("History error: %s", exc)
        return jsonify({"history": [], "count": 0})


# ── AI Book Summary ───────────────────────────────────────────────────────────
@app.route("/api/summary/<book_id>")
def ai_summary(book_id: str):
    book_obj = None
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
    except Exception:
        pass

    if book_obj:
        if book_obj.ai_summary:
            return jsonify({"summary": book_obj.ai_summary, "ai_generated": True})
        title    = book_obj.title
        authors  = ", ".join(book_obj.authors_list)
        edition  = book_obj.edition or ""
        category = (book_obj.category_ref.name if book_obj.category_ref else "") + " / " + (book_obj.subcategory or "")
        subjects = ", ".join(book_obj.subjects_list)
        existing_summary = book_obj.summary or ""
    else:
        book = next((b for b in LIBRARY_DATA.get("books", []) if b["id"] == book_id), None)
        if not book:
            return jsonify({"error": "Book not found"}), 404
        title    = book["title"]
        authors  = ", ".join(book["authors"])
        edition  = book.get("edition", "")
        category = f"{book.get('category','')} / {book.get('subcategory','')}"
        subjects = ", ".join(book.get("subjects", []))
        existing_summary = book.get("summary", "")

    inst   = AGENT_INSTRUCTIONS
    prompt = (
        f"<<SYS>>\n{inst['persona']}\n{inst['summary_instructions']}\n<</SYS>>\n\n"
        f"Generate an academic summary for the following book:\n"
        f"Title: {title}\nAuthors: {authors}\nEdition: {edition}\n"
        f"Category: {category}\nSubjects: {subjects}\n\nSummary:"
    )
    try:
        model   = get_watsonx_model()
        summary = model.generate_text(prompt=prompt).strip()
        if book_obj and summary:
            try:
                book_obj.ai_summary = summary
                db.session.commit()
            except Exception:
                pass
        return jsonify({"summary": summary or existing_summary, "ai_generated": True})
    except Exception as exc:
        logger.warning("AI summary fallback: %s", exc)
        return jsonify({"summary": existing_summary, "ai_generated": False})


# ── Library Info ──────────────────────────────────────────────────────────────
@app.route("/api/library-info")
def library_info():
    return jsonify(LIBRARY_DATA.get("library_info", {}))


# ── Available Courses ─────────────────────────────────────────────────────────
@app.route("/api/courses")
def courses():
    journals = []
    try:
        db_journals = Journal.query.all()
        if db_journals:
            journals = [j.to_dict() for j in db_journals]
        else:
            journals = LIBRARY_DATA.get("journals", [])
    except Exception:
        journals = LIBRARY_DATA.get("journals", [])

    return jsonify({
        "courses":  list(LIBRARY_DATA.get("courses", {}).keys()),
        "journals": journals,
    })


# ── Stats / Dashboard ─────────────────────────────────────────────────────────
@app.route("/api/stats")
def stats():
    try:
        total_titles     = db.session.query(Book).filter(Book.is_active == True).count()
        if total_titles == 0:
            raise ValueError("empty db")
        total_copies     = db.session.query(db.func.sum(Book.total_copies)).scalar() or 0
        available_copies = db.session.query(db.func.sum(Book.available_copies)).scalar() or 0
        total_journals   = db.session.query(Journal).count()
        total_users      = db.session.query(User).count()
        active_borrows   = db.session.query(BorrowRecord).filter(
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).count()

        cat_rows = (
            db.session.query(Category.name, db.func.count(Book.id))
            .join(Book, Book.category_id == Category.id)
            .filter(Book.is_active == True)
            .group_by(Category.name)
            .all()
        )
        categories = {row[0]: row[1] for row in cat_rows}

        return jsonify({
            "total_titles":       total_titles,
            "total_copies":       int(total_copies),
            "available_copies":   int(available_copies),
            "unavailable_copies": int(total_copies) - int(available_copies),
            "categories":         categories,
            "total_journals":     total_journals,
            "total_users":        total_users,
            "active_borrows":     active_borrows,
        })
    except Exception:
        # Fallback to JSON stats
        books     = LIBRARY_DATA.get("books", [])
        total     = len(books)
        available = sum(b.get("available_copies", 0) for b in books)
        total_cop = sum(b.get("total_copies", 0) for b in books)
        categories: dict = {}
        for b in books:
            categories[b.get("category", "Other")] = categories.get(b.get("category", "Other"), 0) + 1
        return jsonify({
            "total_titles":       total,
            "total_copies":       total_cop,
            "available_copies":   available,
            "unavailable_copies": total_cop - available,
            "categories":         categories,
            "total_journals":     len(LIBRARY_DATA.get("journals", [])),
            "total_users":        0,
            "active_borrows":     0,
        })


# ── Clear Chat ────────────────────────────────────────────────────────────────
@app.route("/api/clear-chat", methods=["POST"])
def clear_chat():
    session["chat_history"] = []
    return jsonify({"message": "Chat cleared"})


# =============================================================================
#  NEW ROUTES
# =============================================================================

# ── Personalised Recommendations ─────────────────────────────────────────────
@app.route("/api/recommendations")
def recommendations():
    user = _get_current_user()
    if not user:
        user = User(session_id="anonymous", name="Guest", course="")
    recs = get_personalized_recommendations(user)
    return jsonify(recs)


# ── AI Learning Roadmap ───────────────────────────────────────────────────────
@app.route("/api/roadmap")
def roadmap():
    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "topic parameter required"}), 400

    books = search_books_db(topic, limit=8)
    inst  = AGENT_INSTRUCTIONS

    prompt = (
        f"<<SYS>>\n{inst['persona']}\n\n"
        f"ROADMAP INSTRUCTIONS: {inst['roadmap_instructions']}\n<</SYS>>\n\n"
        f"Generate a comprehensive learning roadmap for the topic: \"{topic}\"\n\n"
        f"Available library books on this topic:\n"
        f"{build_catalog_context(books)}\n\n"
        f"Roadmap:"
    )
    try:
        model      = get_watsonx_model()
        roadmap_md = model.generate_text(prompt=prompt).strip()
    except Exception as exc:
        logger.warning("Roadmap AI fallback: %s", exc)
        roadmap_md = (
            f"## Learning Roadmap: {topic}\n\n"
            f"**Phase 1 – Foundations**\nStart with introductory books listed below.\n\n"
            f"**Phase 2 – Core Concepts**\nProgress to intermediate materials.\n\n"
            f"**Phase 3 – Advanced Topics**\nExplore research papers and advanced references.\n\n"
            f"**Phase 4 – Research**\nConsult journals and thesis resources in the library."
        )
    return jsonify({"topic": topic, "roadmap": roadmap_md, "books": books})


# ── Renew Borrowed Book ───────────────────────────────────────────────────────
@app.route("/api/books/<book_id>/renew", methods=["POST"])
def renew_book(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        book_obj = Book.query.filter_by(book_id=book_id).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404

        record = BorrowRecord.query.filter_by(
            user_id=user.id, book_id=book_obj.id, status="borrowed"
        ).first()
        if not record:
            record = BorrowRecord.query.filter_by(
                user_id=user.id, book_id=book_obj.id, status="overdue"
            ).first()
        if not record:
            return jsonify({"error": "No active borrow record found"}), 404

        level = user.learning_level or "undergraduate"
        rules = LIBRARY_DATA.get("library_info", {}).get("borrowing_rules", {})
        if "postgraduate" in level or level in ("postgraduate", "faculty"):
            max_renewals = rules.get("postgraduate", {}).get("renewals", 3)
            ext_days     = rules.get("postgraduate", {}).get("duration_days", 21)
        else:
            max_renewals = rules.get("undergraduate", {}).get("renewals", 2)
            ext_days     = rules.get("undergraduate", {}).get("duration_days", 14)

        if record.renewed_count >= max_renewals:
            return jsonify({"error": f"Maximum renewals ({max_renewals}) reached"}), 400

        record.renewed_count += 1
        record.due_date       = (record.due_date or datetime.utcnow()) + timedelta(days=ext_days)
        record.status         = "borrowed"
        db.session.commit()

        return jsonify({
            "message":      f"✅ Renewed for {ext_days} more days",
            "new_due_date": record.due_date.strftime("%d %b %Y"),
            "renewed_count": record.renewed_count,
        })
    except Exception as exc:
        logger.error("Renew error: %s", exc)
        return jsonify({"error": "Renewal failed"}), 500


# ── QR Code for Book ──────────────────────────────────────────────────────────
@app.route("/api/books/<book_id>/qr")
def book_qr(book_id: str):
    if not QR_AVAILABLE:
        return jsonify({"error": "qrcode library not installed"}), 501

    book_url = request.host_url.rstrip("/") + f"/api/book/{book_id}"
    try:
        qr = qrcode.QRCode(version=1, box_size=8, border=4)
        qr.add_data(book_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode("utf-8")
        return jsonify({"qr_code": f"data:image/png;base64,{encoded}", "url": book_url})
    except Exception as exc:
        logger.error("QR generation error: %s", exc)
        return jsonify({"error": "QR generation failed"}), 500


# ── Notifications ─────────────────────────────────────────────────────────────
@app.route("/api/notifications")
def get_notifications():
    user = _get_current_user()
    if not user:
        return jsonify({"notifications": [], "unread_count": 0})
    try:
        notifs = (
            Notification.query
            .filter_by(user_id=user.id)
            .order_by(Notification.created_at.desc())
            .limit(50)
            .all()
        )
        unread = sum(1 for n in notifs if not n.is_read)
        return jsonify({"notifications": [n.to_dict() for n in notifs], "unread_count": unread})
    except Exception as exc:
        logger.error("Notifications error: %s", exc)
        return jsonify({"notifications": [], "unread_count": 0})


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
def mark_notification_read(notif_id: int):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        notif = Notification.query.filter_by(id=notif_id, user_id=user.id).first()
        if not notif:
            return jsonify({"error": "Notification not found"}), 404
        notif.is_read = True
        db.session.commit()
        return jsonify({"message": "Marked as read"})
    except Exception as exc:
        logger.error("Mark read error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Favorites ─────────────────────────────────────────────────────────────────
@app.route("/api/favorites")
def get_favorites():
    user = _get_current_user()
    if not user:
        return jsonify({"favorites": []})
    try:
        favs = Favorite.query.filter_by(user_id=user.id).order_by(Favorite.added_at.desc()).all()
        result = []
        for fav in favs:
            if fav.book:
                d = fav.book.to_dict()
                d["favorited_at"] = fav.added_at.strftime("%d %b %Y") if fav.added_at else ""
                result.append(d)
        return jsonify({"favorites": result})
    except Exception as exc:
        logger.error("Favorites error: %s", exc)
        return jsonify({"favorites": []})


@app.route("/api/favorites/<book_id>", methods=["POST"])
def add_favorite(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404
        existing = Favorite.query.filter_by(user_id=user.id, book_id=book_obj.id).first()
        if existing:
            return jsonify({"message": "Already in favorites", "favorited": True})
        fav = Favorite(user_id=user.id, book_id=book_obj.id)
        db.session.add(fav)
        db.session.commit()
        return jsonify({"message": "Added to favorites", "favorited": True})
    except Exception as exc:
        logger.error("Add favorite error: %s", exc)
        return jsonify({"error": "Failed"}), 500


@app.route("/api/favorites/<book_id>", methods=["DELETE"])
def remove_favorite(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        book_obj = Book.query.filter_by(book_id=book_id).first()
        if book_obj:
            fav = Favorite.query.filter_by(user_id=user.id, book_id=book_obj.id).first()
            if fav:
                db.session.delete(fav)
                db.session.commit()
        return jsonify({"message": "Removed from favorites", "favorited": False})
    except Exception as exc:
        logger.error("Remove favorite error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Borrow a Book ─────────────────────────────────────────────────────────────
@app.route("/api/borrow/<book_id>", methods=["POST"])
def borrow_book(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated", "auth_required": True}), 401
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404
        if book_obj.available_copies <= 0:
            return jsonify({"error": "No copies available. Please reserve instead."}), 400

        active = BorrowRecord.query.filter(
            BorrowRecord.user_id == user.id,
            BorrowRecord.book_id == book_obj.id,
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).first()
        if active:
            return jsonify({"error": "You already have this book borrowed"}), 400

        # Check borrowing limit
        level = user.learning_level or "undergraduate"
        rules = LIBRARY_DATA.get("library_info", {}).get("borrowing_rules", {})
        if level == "faculty":
            rule_key  = "faculty"
            duration  = rules.get("faculty", {}).get("duration_days", 30)
            max_books = rules.get("faculty", {}).get("books", 10)
        elif level in ("postgraduate", "research"):
            rule_key  = "postgraduate"
            duration  = rules.get("postgraduate", {}).get("duration_days", 21)
            max_books = rules.get("postgraduate", {}).get("books", 6)
        else:
            rule_key  = "undergraduate"
            duration  = rules.get("undergraduate", {}).get("duration_days", 14)
            max_books = rules.get("undergraduate", {}).get("books", 4)

        current_borrows = BorrowRecord.query.filter(
            BorrowRecord.user_id == user.id,
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).count()
        if current_borrows >= max_books:
            return jsonify({"error": f"Borrowing limit of {max_books} books reached for {rule_key} level"}), 400

        due_date = datetime.utcnow() + timedelta(days=duration)
        record   = BorrowRecord(
            user_id=user.id, book_id=book_obj.id,
            borrow_date=datetime.utcnow(), due_date=due_date, status="borrowed"
        )
        book_obj.available_copies -= 1
        book_obj.times_borrowed   = (book_obj.times_borrowed or 0) + 1
        db.session.add(record)
        db.session.commit()

        # Notification: due date reminder
        _notify(user.id, "due_date",
                f"Book Borrowed: {book_obj.title}",
                f"Due date: {due_date.strftime('%d %b %Y')}. Return on time to avoid fines.",
                book_obj.id)

        return jsonify({
            "message":   f"✅ Book borrowed! Due: {due_date.strftime('%d %b %Y')}",
            "due_date":  due_date.strftime("%d %b %Y"),
            "borrow_id": record.id,
        })
    except Exception as exc:
        logger.error("Borrow error: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Borrow failed"}), 500


# ── Return a Book ─────────────────────────────────────────────────────────────
@app.route("/api/return/<book_id>", methods=["POST"])
def return_book(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated", "auth_required": True}), 401
    try:
        book_obj = Book.query.filter_by(book_id=book_id).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404

        record = BorrowRecord.query.filter(
            BorrowRecord.user_id  == user.id,
            BorrowRecord.book_id  == book_obj.id,
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).first()
        if not record:
            return jsonify({"error": "No active borrow record found"}), 404

        now = datetime.utcnow()
        record.return_date = now
        record.status      = "returned"

        # Fine calculation: FINE_PER_DAY_INR / day after due date
        fine = 0.0
        if record.due_date and now > record.due_date:
            days_late  = (now - record.due_date).days
            fine       = days_late * app.config["FINE_PER_DAY_INR"]
            record.fine_amount = fine

        book_obj.available_copies = min(
            (book_obj.available_copies or 0) + 1, book_obj.total_copies or 1
        )
        db.session.commit()

        # Notify next reservation holder if any
        next_res = Reservation.query.filter_by(
            book_id=book_obj.id, status="pending"
        ).order_by(Reservation.reserved_at).first()
        if next_res:
            _notify(next_res.user_id, "reservation",
                    f"Book Available: {book_obj.title}",
                    f"A copy of '{book_obj.title}' is now available. Visit the library to collect it.",
                    book_obj.id)
            next_res.notified = True
            db.session.commit()

        if fine > 0:
            _notify(user.id, "fine",
                    f"Fine Due: Rs. {fine:.0f}",
                    f"You have a fine of Rs. {fine:.0f} for late return of '{book_obj.title}'.",
                    book_obj.id)

        msg = "✅ Book returned successfully!"
        if fine > 0:
            msg += f" Fine due: Rs. {fine:.0f}"
        return jsonify({"message": msg, "fine_amount": fine, "return_date": now.strftime("%d %b %Y")})
    except Exception as exc:
        logger.error("Return error: %s", exc)
        db.session.rollback()
        return jsonify({"error": "Return failed"}), 500


# ── Submit Review ─────────────────────────────────────────────────────────────
@app.route("/api/books/<book_id>/review", methods=["POST"])
def submit_review(book_id: str):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    data   = request.get_json(silent=True) or {}
    rating  = data.get("rating")
    comment = data.get("comment", "")
    if rating is None or not (1 <= int(rating) <= 5):
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    try:
        book_obj = Book.query.filter_by(book_id=book_id, is_active=True).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404
        existing = Review.query.filter_by(user_id=user.id, book_id=book_obj.id).first()
        if existing:
            existing.rating  = int(rating)
            existing.comment = comment
        else:
            review = Review(
                user_id=user.id, book_id=book_obj.id,
                rating=int(rating), comment=comment
            )
            db.session.add(review)
        # Recompute average rating
        db.session.flush()
        avg = db.session.query(db.func.avg(Review.rating)).filter_by(book_id=book_obj.id).scalar()
        if avg:
            book_obj.rating = round(float(avg), 1)
        db.session.commit()
        return jsonify({"message": "Review submitted", "new_rating": book_obj.rating})
    except Exception as exc:
        logger.error("Review error: %s", exc)
        return jsonify({"error": "Review failed"}), 500


# ── Digital Resources ─────────────────────────────────────────────────────────
@app.route("/api/digital")
def digital_resources():
    try:
        resources = (
            Book.query
            .filter(Book.is_active == True, Book.is_digital == True)
            .order_by(Book.rating.desc())
            .all()
        )
        if resources:
            return jsonify({"resources": [b.to_dict() for b in resources], "count": len(resources)})
    except Exception:
        pass
    # JSON fallback — no digital flag in JSON, return empty
    return jsonify({"resources": [], "count": 0})


# ── Analytics ─────────────────────────────────────────────────────────────────
@app.route("/api/analytics")
def analytics():
    user = _get_current_user()
    if not user or not user.is_admin:
        return jsonify({"error": "Forbidden"}), 403
    try:
        total_books   = db.session.query(Book).filter(Book.is_active == True).count()
        total_users   = db.session.query(User).count()
        total_borrows = db.session.query(BorrowRecord).count()
        active_borrows= db.session.query(BorrowRecord).filter(
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).count()
        overdue_count = db.session.query(BorrowRecord).filter_by(status="overdue").count()
        total_fines   = db.session.query(db.func.sum(BorrowRecord.fine_amount)).scalar() or 0

        top_books = (
            db.session.query(Book.title, Book.times_borrowed)
            .filter(Book.is_active == True)
            .order_by(Book.times_borrowed.desc())
            .limit(10)
            .all()
        )
        return jsonify({
            "total_books":    total_books,
            "total_users":    total_users,
            "total_borrows":  total_borrows,
            "active_borrows": active_borrows,
            "overdue_count":  overdue_count,
            "total_fines":    round(float(total_fines), 2),
            "top_books":      [{"title": t, "times_borrowed": tb} for t, tb in top_books],
        })
    except Exception as exc:
        logger.error("Analytics error: %s", exc)
        return jsonify({"error": "Analytics unavailable"}), 500


# ── Search Suggestions / Autocomplete ────────────────────────────────────────
@app.route("/api/search/suggestions")
def search_suggestions():
    q = request.args.get("q", "").strip()
    if not q or len(q) < 2:
        return jsonify({"suggestions": []})
    like = f"%{q}%"
    suggestions = []
    try:
        titles = (
            Book.query
            .filter(Book.is_active == True, Book.title.ilike(like))
            .with_entities(Book.title)
            .limit(5)
            .all()
        )
        suggestions += [t[0] for t in titles]

        authors = (
            Author.query
            .filter(Author.name.ilike(like))
            .with_entities(Author.name)
            .limit(3)
            .all()
        )
        suggestions += [a[0] for a in authors]
    except Exception:
        # JSON fallback
        for b in LIBRARY_DATA.get("books", []):
            if q.lower() in b.get("title", "").lower():
                suggestions.append(b["title"])
            for a in b.get("authors", []):
                if q.lower() in a.lower() and a not in suggestions:
                    suggestions.append(a)
            if len(suggestions) >= 8:
                break

    return jsonify({"suggestions": list(dict.fromkeys(suggestions))[:8]})


# ── List Reservations for current user ───────────────────────────────────────
@app.route("/api/reservations")
def list_reservations():
    user = _get_current_user()
    if not user:
        return jsonify({"reservations": []})
    try:
        recs = (
            Reservation.query
            .filter_by(user_id=user.id)
            .filter(Reservation.status.in_(["pending", "approved"]))
            .order_by(Reservation.reserved_at.desc())
            .all()
        )
        return jsonify({"reservations": [r.to_dict() for r in recs]})
    except Exception as exc:
        logger.error("List reservations error: %s", exc)
        return jsonify({"reservations": []})


# ── Cancel reservation ────────────────────────────────────────────────────────
@app.route("/api/reservations/<int:res_id>", methods=["DELETE"])
def cancel_reservation_by_id(res_id: int):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        res = Reservation.query.filter_by(id=res_id, user_id=user.id).first()
        if not res:
            return jsonify({"error": "Reservation not found"}), 404
        res.status = "cancelled"
        db.session.commit()
        return jsonify({"message": "Reservation cancelled"})
    except Exception as exc:
        logger.error("Cancel reservation error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Mark all notifications read ───────────────────────────────────────────────
@app.route("/api/notifications/read-all", methods=["POST"])
def mark_all_notifications_read():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
        db.session.commit()
        return jsonify({"message": "All notifications marked as read"})
    except Exception as exc:
        logger.error("Mark all read error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Pay a fine ────────────────────────────────────────────────────────────────
@app.route("/api/fines/<int:borrow_id>/pay", methods=["POST"])
def pay_fine(borrow_id: int):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    try:
        record = BorrowRecord.query.filter_by(id=borrow_id, user_id=user.id).first()
        if not record:
            return jsonify({"error": "Borrow record not found"}), 404
        if record.fine_amount <= 0:
            return jsonify({"message": "No fine to pay"}), 200
        if record.fine_paid:
            return jsonify({"message": "Fine already paid"}), 200
        record.fine_paid = True
        db.session.commit()
        return jsonify({"message": f"✅ Fine of Rs. {record.fine_amount:.0f} marked as paid"})
    except Exception as exc:
        logger.error("Pay fine error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Auth: Register ────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name     = (data.get("name") or "").strip()
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    student_id = (data.get("student_id") or "").strip()

    if not name or not email or not password:
        return jsonify({"error": "Name, email and password are required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    try:
        existing = User.query.filter_by(email=email).first()
        if existing:
            return jsonify({"error": "Email already registered"}), 409

        # Upgrade the current guest session user if exists
        user = _get_current_user()
        if not user:
            sid  = session.get("session_id", str(uuid.uuid4()))
            user = User(session_id=sid)
            db.session.add(user)

        if user.name != "Guest" and user.email and user.email != email:
            # Already registered user, create fresh
            new_sid  = str(uuid.uuid4())
            user = User(session_id=new_sid)
            db.session.add(user)
            session["session_id"] = new_sid

        user.name          = name
        user.email         = email
        user.student_id    = student_id
        user.password_hash = generate_password_hash(password)
        if data.get("course"):     user.course     = data["course"]
        if data.get("semester"):   user.semester   = data["semester"]
        if data.get("department"): user.department = data["department"]
        db.session.commit()

        session["user_profile"] = {
            "name":       user.name, "email": user.email,
            "student_id": user.student_id, "course": user.course or "",
            "semester":   user.semester or "", "is_admin": user.is_admin,
        }
        return jsonify({"message": "Registration successful", "user": user.to_dict()}), 201
    except Exception as exc:
        db.session.rollback()
        logger.error("Register error: %s", exc)
        return jsonify({"error": "Registration failed"}), 500


# ── Auth: Login ───────────────────────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    data     = request.get_json(silent=True) or {}
    email    = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    try:
        user = User.query.filter_by(email=email).first()
        if not user or not user.password_hash:
            return jsonify({"error": "Invalid email or password"}), 401
        if not check_password_hash(user.password_hash, password):
            return jsonify({"error": "Invalid email or password"}), 401

        # Transfer session to this user
        session["session_id"] = user.session_id
        user.last_active = datetime.utcnow()
        db.session.commit()

        session["user_profile"] = {
            "name":       user.name, "email": user.email,
            "student_id": user.student_id or "", "course": user.course or "",
            "semester":   user.semester or "", "is_admin": user.is_admin,
        }
        return jsonify({"message": "Login successful", "user": user.to_dict()})
    except Exception as exc:
        logger.error("Login error: %s", exc)
        return jsonify({"error": "Login failed"}), 500


# ── Auth: Logout ──────────────────────────────────────────────────────────────
@app.route("/api/auth/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out successfully"})


# ── Auth: Status ──────────────────────────────────────────────────────────────
@app.route("/api/auth/status")
def auth_status():
    user = _get_current_user()
    if user and user.email:
        return jsonify({
            "authenticated": True,
            "user": user.to_dict(),
        })
    return jsonify({"authenticated": False})


# ── DB Seed from JSON ─────────────────────────────────────────────────────────
@app.route("/api/admin/seed", methods=["POST"])
@_admin_required
def seed_database():
    """Seed database from library_data.json (admin only, idempotent)."""
    try:
        added_books = 0
        added_authors = 0
        added_cats  = 0
        added_journals = 0

        for book_data in LIBRARY_DATA.get("books", []):
            if Book.query.filter_by(book_id=book_data["id"]).first():
                continue  # already exists

            cat_name = book_data.get("category", "General")
            category = Category.query.filter_by(name=cat_name).first()
            if not category:
                category = Category(name=cat_name)
                db.session.add(category)
                db.session.flush()
                added_cats += 1

            book = Book(
                book_id          = book_data["id"],
                title            = book_data["title"],
                edition          = book_data.get("edition"),
                publisher        = book_data.get("publisher"),
                year             = book_data.get("year"),
                isbn             = book_data.get("isbn"),
                category_id      = category.id,
                subcategory      = book_data.get("subcategory"),
                subjects         = ", ".join(book_data.get("subjects", [])),
                courses          = ", ".join(book_data.get("courses", [])),
                tags             = ", ".join(book_data.get("tags", [])),
                location         = book_data.get("location"),
                shelf_number     = book_data.get("shelf_number"),
                total_copies     = book_data.get("total_copies", 1),
                available_copies = book_data.get("available_copies", book_data.get("total_copies", 1)),
                summary          = book_data.get("summary"),
                rating           = book_data.get("rating", 4.0),
                cover_url        = book_data.get("cover_url"),
                pdf_url          = book_data.get("pdf_url"),
                is_digital       = book_data.get("is_digital", False),
                resource_type    = book_data.get("resource_type", "book"),
            )
            db.session.add(book)
            db.session.flush()
            added_books += 1

            for i, author_name in enumerate(book_data.get("authors", [])):
                author = Author.query.filter_by(name=author_name).first()
                if not author:
                    author = Author(name=author_name)
                    db.session.add(author)
                    db.session.flush()
                    added_authors += 1
                ba = BookAuthor(book_id=book.id, author_id=author.id, order=i)
                db.session.add(ba)

        for j_data in LIBRARY_DATA.get("journals", []):
            if Journal.query.filter_by(title=j_data["title"]).first():
                continue
            journal = Journal(
                title          = j_data["title"],
                publisher      = j_data.get("publisher"),
                access         = j_data.get("access"),
                url            = j_data.get("url"),
                subjects       = ", ".join(j_data.get("subjects", [])),
                impact_factor  = j_data.get("impact_factor"),
                is_open_access = j_data.get("is_open_access", False),
            )
            db.session.add(journal)
            added_journals += 1

        db.session.commit()
        return jsonify({
            "message": "Seed complete",
            "added_books": added_books, "added_authors": added_authors,
            "added_categories": added_cats, "added_journals": added_journals,
        })
    except Exception as exc:
        db.session.rollback()
        logger.error("Seed error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# =============================================================================
#  ADMIN ROUTES
# =============================================================================

def _require_admin():
    """Return (user, error_response) — error_response is None if OK."""
    user = _get_current_user()
    if not user or not user.is_admin:
        return user, (jsonify({"error": "Forbidden"}), 403)
    return user, None


@app.route("/admin/")
def admin_panel():
    user, err = _require_admin()
    if err:
        return redirect(url_for("index"))
    return render_template("admin_panel.html")


@app.route("/api/admin/books", methods=["GET"])
def admin_list_books():
    _, err = _require_admin()
    if err:
        return err
    try:
        page     = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        books    = Book.query.order_by(Book.added_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify({
            "books": [b.to_dict() for b in books.items],
            "total": books.total,
            "page":  books.page,
            "pages": books.pages,
        })
    except Exception as exc:
        logger.error("Admin list books error: %s", exc)
        return jsonify({"error": "Failed"}), 500


@app.route("/api/admin/books", methods=["POST"])
def admin_add_book():
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        # Resolve or create category
        cat_name = data.get("category", "General")
        category = Category.query.filter_by(name=cat_name).first()
        if not category:
            category = Category(name=cat_name)
            db.session.add(category)
            db.session.flush()

        book_id_str = data.get("book_id") or f"B{Book.query.count() + 1:04d}"
        book = Book(
            book_id          = book_id_str,
            title            = data.get("title", "Untitled"),
            edition          = data.get("edition"),
            publisher        = data.get("publisher"),
            year             = data.get("year"),
            isbn             = data.get("isbn"),
            category_id      = category.id,
            subcategory      = data.get("subcategory"),
            subjects         = data.get("subjects"),
            courses          = data.get("courses"),
            tags             = data.get("tags"),
            location         = data.get("location"),
            shelf_number     = data.get("shelf_number"),
            total_copies     = data.get("total_copies", 1),
            available_copies = data.get("available_copies", data.get("total_copies", 1)),
            summary          = data.get("summary"),
            rating           = data.get("rating", 4.0),
            cover_url        = data.get("cover_url"),
            pdf_url          = data.get("pdf_url"),
            is_digital       = data.get("is_digital", False),
            resource_type    = data.get("resource_type", "book"),
        )
        db.session.add(book)
        db.session.flush()

        for author_name in (data.get("authors") or []):
            author = Author.query.filter_by(name=author_name).first()
            if not author:
                author = Author(name=author_name)
                db.session.add(author)
                db.session.flush()
            ba = BookAuthor(book_id=book.id, author_id=author.id)
            db.session.add(ba)

        db.session.commit()
        return jsonify({"message": "Book added", "book": book.to_dict()}), 201
    except Exception as exc:
        db.session.rollback()
        logger.error("Admin add book error: %s", exc)
        return jsonify({"error": "Failed to add book"}), 500


@app.route("/api/admin/books/<int:book_db_id>", methods=["PUT"])
def admin_edit_book(book_db_id: int):
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        book = db.session.get(Book, book_db_id)
        if not book:
            return jsonify({"error": "Book not found"}), 404
        for field in ("title", "edition", "publisher", "year", "isbn", "subcategory",
                      "subjects", "courses", "tags", "location", "shelf_number",
                      "total_copies", "available_copies", "summary", "rating",
                      "cover_url", "pdf_url", "is_digital", "resource_type", "is_active"):
            if field in data:
                setattr(book, field, data[field])
        if "category" in data:
            cat = Category.query.filter_by(name=data["category"]).first()
            if not cat:
                cat = Category(name=data["category"])
                db.session.add(cat)
                db.session.flush()
            book.category_id = cat.id
        db.session.commit()
        return jsonify({"message": "Book updated", "book": book.to_dict()})
    except Exception as exc:
        db.session.rollback()
        logger.error("Admin edit book error: %s", exc)
        return jsonify({"error": "Failed to update book"}), 500


@app.route("/api/admin/books/<int:book_db_id>", methods=["DELETE"])
def admin_delete_book(book_db_id: int):
    _, err = _require_admin()
    if err:
        return err
    try:
        book = db.session.get(Book, book_db_id)
        if not book:
            return jsonify({"error": "Book not found"}), 404
        book.is_active = False   # soft delete
        db.session.commit()
        return jsonify({"message": "Book deleted"})
    except Exception as exc:
        db.session.rollback()
        logger.error("Admin delete book error: %s", exc)
        return jsonify({"error": "Failed to delete book"}), 500


@app.route("/api/admin/users")
def admin_list_users():
    _, err = _require_admin()
    if err:
        return err
    try:
        page     = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        users    = User.query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify({
            "users": [u.to_dict() for u in users.items],
            "total": users.total,
            "page":  users.page,
            "pages": users.pages,
        })
    except Exception as exc:
        logger.error("Admin users error: %s", exc)
        return jsonify({"error": "Failed"}), 500


@app.route("/api/admin/borrows")
def admin_list_borrows():
    _, err = _require_admin()
    if err:
        return err
    try:
        status   = request.args.get("status")
        page     = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        q = BorrowRecord.query
        if status:
            q = q.filter_by(status=status)
        records = q.order_by(BorrowRecord.borrow_date.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify({
            "borrows": [r.to_dict() for r in records.items],
            "total":   records.total,
            "page":    records.page,
            "pages":   records.pages,
        })
    except Exception as exc:
        logger.error("Admin borrows error: %s", exc)
        return jsonify({"error": "Failed"}), 500


@app.route("/api/admin/reports")
def admin_reports():
    _, err = _require_admin()
    if err:
        return err
    try:
        total_books      = db.session.query(Book).filter(Book.is_active == True).count()
        total_users      = db.session.query(User).count()
        total_borrows    = db.session.query(BorrowRecord).count()
        returned         = db.session.query(BorrowRecord).filter_by(status="returned").count()
        overdue          = db.session.query(BorrowRecord).filter_by(status="overdue").count()
        active           = db.session.query(BorrowRecord).filter_by(status="borrowed").count()
        total_fines      = db.session.query(db.func.sum(BorrowRecord.fine_amount)).scalar() or 0
        unpaid_fines     = db.session.query(db.func.sum(BorrowRecord.fine_amount)).filter_by(
            fine_paid=False
        ).scalar() or 0
        total_reservations = db.session.query(Reservation).count()
        total_reviews      = db.session.query(Review).count()
        avg_rating         = db.session.query(db.func.avg(Book.rating)).scalar() or 0

        return jsonify({
            "total_books":         total_books,
            "total_users":         total_users,
            "total_borrows":       total_borrows,
            "returned":            returned,
            "overdue":             overdue,
            "active_borrows":      active,
            "total_fines_inr":     round(float(total_fines), 2),
            "unpaid_fines_inr":    round(float(unpaid_fines), 2),
            "total_reservations":  total_reservations,
            "total_reviews":       total_reviews,
            "avg_book_rating":     round(float(avg_rating), 2),
            "generated_at":        datetime.utcnow().strftime("%d %b %Y %H:%M UTC"),
        })
    except Exception as exc:
        logger.error("Admin reports error: %s", exc)
        return jsonify({"error": "Report generation failed"}), 500


# ── Admin: Promote user to admin ──────────────────────────────────────────────
@app.route("/api/admin/users/<int:user_id>/promote", methods=["POST"])
def admin_promote_user(user_id: int):
    _, err = _require_admin()
    if err:
        return err
    try:
        target = db.session.get(User, user_id)
        if not target:
            return jsonify({"error": "User not found"}), 404
        target.is_admin = True
        db.session.commit()
        return jsonify({"message": f"User {target.name} promoted to admin"})
    except Exception as exc:
        logger.error("Promote user error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Admin: Borrow on behalf ───────────────────────────────────────────────────
@app.route("/api/admin/borrow", methods=["POST"])
def admin_borrow():
    _, err = _require_admin()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        target_user = User.query.filter_by(student_id=data.get("student_id")).first()
        if not target_user:
            target_user = db.session.get(User, data.get("user_id"))
        if not target_user:
            return jsonify({"error": "User not found"}), 404

        book_obj = Book.query.filter_by(book_id=data.get("book_id"), is_active=True).first()
        if not book_obj:
            return jsonify({"error": "Book not found"}), 404
        if book_obj.available_copies <= 0:
            return jsonify({"error": "No copies available"}), 400

        active = BorrowRecord.query.filter(
            BorrowRecord.user_id == target_user.id,
            BorrowRecord.book_id == book_obj.id,
            BorrowRecord.status.in_(["borrowed", "overdue"])
        ).first()
        if active:
            return jsonify({"error": "User already has this book"}), 400

        duration = int(data.get("duration_days", 14))
        due_date = datetime.utcnow() + timedelta(days=duration)
        record = BorrowRecord(
            user_id=target_user.id, book_id=book_obj.id,
            borrow_date=datetime.utcnow(), due_date=due_date, status="borrowed"
        )
        book_obj.available_copies -= 1
        book_obj.times_borrowed = (book_obj.times_borrowed or 0) + 1
        db.session.add(record)
        db.session.commit()
        return jsonify({
            "message": f"✅ Issued to {target_user.name}. Due: {due_date.strftime('%d %b %Y')}",
            "borrow_id": record.id,
        }), 201
    except Exception as exc:
        db.session.rollback()
        logger.error("Admin borrow error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Admin: Return on behalf ───────────────────────────────────────────────────
@app.route("/api/admin/return/<int:borrow_id>", methods=["POST"])
def admin_return(borrow_id: int):
    _, err = _require_admin()
    if err:
        return err
    try:
        record = db.session.get(BorrowRecord, borrow_id)
        if not record:
            return jsonify({"error": "Borrow record not found"}), 404
        if record.status == "returned":
            return jsonify({"message": "Already returned"}), 200

        now = datetime.utcnow()
        record.return_date = now
        record.status = "returned"
        fine = 0.0
        if record.due_date and now > record.due_date:
            days_late = (now - record.due_date).days
            fine = days_late * app.config["FINE_PER_DAY_INR"]
            record.fine_amount = fine

        book_obj = record.book
        if book_obj:
            book_obj.available_copies = min(
                (book_obj.available_copies or 0) + 1, book_obj.total_copies or 1
            )
        db.session.commit()

        msg = "✅ Book returned."
        if fine > 0:
            msg += f" Fine: Rs. {fine:.0f}"
        return jsonify({"message": msg, "fine_amount": fine})
    except Exception as exc:
        db.session.rollback()
        logger.error("Admin return error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# ── Admin: Overdue check & notification sweep ────────────────────────────────
@app.route("/api/admin/overdue-check", methods=["POST"])
def admin_overdue_check():
    _, err = _require_admin()
    if err:
        return err
    try:
        now = datetime.utcnow()
        overdue_records = BorrowRecord.query.filter(
            BorrowRecord.status == "borrowed",
            BorrowRecord.due_date < now
        ).all()
        updated = 0
        for r in overdue_records:
            r.status = "overdue"
            r.fine_amount = _compute_fine(r)
            _notify(r.user_id, "fine",
                    f"Overdue Book: {r.book.title if r.book else 'Unknown'}",
                    f"Your book is overdue. Fine: Rs. {r.fine_amount:.0f}. Please return immediately.",
                    r.book_id)
            updated += 1
        db.session.commit()
        return jsonify({"message": f"Updated {updated} overdue records"})
    except Exception as exc:
        db.session.rollback()
        logger.error("Overdue check error: %s", exc)
        return jsonify({"error": "Failed"}), 500


# =============================================================================
#  Entry Point
# =============================================================================
def _init_db():
    """Create tables and auto-seed from JSON if DB is empty."""
    with app.app_context():
        db.create_all()
        logger.info("✅ Database tables verified/created")
        # Auto-seed if books table is empty
        if Book.query.count() == 0:
            logger.info("📚 Seeding database from library_data.json…")
            try:
                added = 0
                for book_data in LIBRARY_DATA.get("books", []):
                    cat_name = book_data.get("category", "General")
                    category = Category.query.filter_by(name=cat_name).first()
                    if not category:
                        category = Category(name=cat_name)
                        db.session.add(category)
                        db.session.flush()

                    book = Book(
                        book_id          = book_data["id"],
                        title            = book_data["title"],
                        edition          = book_data.get("edition"),
                        publisher        = book_data.get("publisher"),
                        year             = book_data.get("year"),
                        isbn             = book_data.get("isbn"),
                        category_id      = category.id,
                        subcategory      = book_data.get("subcategory"),
                        subjects         = ", ".join(book_data.get("subjects", [])),
                        courses          = ", ".join(book_data.get("courses", [])),
                        tags             = ", ".join(book_data.get("tags", [])),
                        location         = book_data.get("location"),
                        shelf_number     = book_data.get("shelf_number"),
                        total_copies     = book_data.get("total_copies", 1),
                        available_copies = book_data.get("available_copies", book_data.get("total_copies", 1)),
                        summary          = book_data.get("summary"),
                        rating           = book_data.get("rating", 4.0),
                        cover_url        = book_data.get("cover_url"),
                        pdf_url          = book_data.get("pdf_url"),
                        is_digital       = book_data.get("is_digital", False),
                        resource_type    = book_data.get("resource_type", "book"),
                    )
                    db.session.add(book)
                    db.session.flush()
                    added += 1

                    for i, author_name in enumerate(book_data.get("authors", [])):
                        author = Author.query.filter_by(name=author_name).first()
                        if not author:
                            author = Author(name=author_name)
                            db.session.add(author)
                            db.session.flush()
                        ba = BookAuthor(book_id=book.id, author_id=author.id, order=i)
                        db.session.add(ba)

                for j_data in LIBRARY_DATA.get("journals", []):
                    journal = Journal(
                        title          = j_data["title"],
                        publisher      = j_data.get("publisher"),
                        access         = j_data.get("access"),
                        url            = j_data.get("url"),
                        subjects       = ", ".join(j_data.get("subjects", [])),
                        impact_factor  = j_data.get("impact_factor"),
                        is_open_access = j_data.get("is_open_access", False),
                    )
                    db.session.add(journal)

                db.session.commit()
                logger.info("✅ Seeded %d books from JSON", added)
            except Exception as exc:
                db.session.rollback()
                logger.error("Auto-seed failed: %s", exc)


if __name__ == "__main__":
    _init_db()
    port  = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    logger.info("🚀 Library AI Agent starting on http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
