# 📚 Library AI Agent
### Powered by IBM watsonx.ai Granite Models

An intelligent, full-stack AI-powered library assistant built with **Python Flask** and **IBM watsonx.ai**. It provides personalised book recommendations, real-time catalog search, reservation management, and natural-language library assistance — all through a modern, responsive web interface.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Chat Librarian** | Natural language Q&A using IBM Granite via watsonx.ai |
| 📚 **Smart Book Search** | Semantic search across title, author, subject, course |
| 🎓 **Course-wise Recommendations** | Semester-aligned book suggestions |
| 🔍 **Real-time Availability** | Live copies available / unavailable status |
| 📖 **AI Book Summaries** | Granite-generated academic summaries on demand |
| 🔖 **Reservations & Waitlist** | Reserve books; see waitlist position |
| 👤 **User Profiles** | Course + semester personalisation |
| 🌙 **Dark Mode** | Full light / dark theme toggle |
| 📱 **Mobile Responsive** | Bootstrap 5, works on all screen sizes |
| 📰 **Journal Access** | IEEE, Springer, Elsevier, ACM journal listing |
| ℹ️ **Library Info** | Timings, borrowing rules, fines, services |

---

## 🗂️ Project Structure



```text
Library-AI-Agent/
├── app.py                  # Main Flask application
├── models.py               # Database models
├── requirements.txt        # Project dependencies
├── README.md               # Project documentation
├── LICENSE                 # License file
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
│
├── data/
│   └── library_data.json   # Library books and journal data
│
├── library/
│   └── library.db          # SQLite database
│
├── modules/                # Helper modules
│
├── templates/
│   ├── index.html
│   └── admin_panel.html
│
└── static/
    ├── css/
    │   └── style.css
    ├── js/
       └── app.js
    
```


---

## 🚀 Quick Start

### 1. Clone & enter the project

```bash
git clone <your-repo>
cd library-agent
```

### 2. Create a Python virtual environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials:

```env
IBM_API_KEY=your_ibm_cloud_api_key_here
WATSONX_PROJECT_ID=your_watsonx_project_id_here
WATSONX_URL=https://us-south.ml.cloud.ibm.com
```

### 5. Run the application

```bash
python app.py
```

Open your browser at **http://localhost:5000**

---

## 🔑 Getting IBM watsonx.ai Credentials

### Step 1 — IBM Cloud Account
1. Go to [cloud.ibm.com](https://cloud.ibm.com) and create a free account.
2. From the navigation: **Manage → Access (IAM) → API Keys**
3. Click **Create an IBM Cloud API key** — copy and save it.

### Step 2 — watsonx.ai Project
1. Go to [dataplatform.cloud.ibm.com](https://dataplatform.cloud.ibm.com)
2. Click **New project → Create an empty project**
3. After creation, go to **Manage → General → Project ID** — copy it.
4. In the project, go to **Manage → Services → Associate service** and add a **Watson Machine Learning** instance.

### Step 3 — Set the URL
Use the URL matching your IBM Cloud region:
- **Dallas (US)**:     `https://us-south.ml.cloud.ibm.com`
- **Frankfurt (EU)**:  `https://eu-de.ml.cloud.ibm.com`
- **London (UK)**:     `https://eu-gb.ml.cloud.ibm.com`
- **Tokyo (JP)**:      `https://jp-tok.ml.cloud.ibm.com`

---

## 🧠 Customising Agent Behaviour

The `AGENT_INSTRUCTIONS` dictionary in [`app.py`](app.py) controls everything about the AI agent:

```python
AGENT_INSTRUCTIONS = {
    "persona":                   "...",  # Agent name, tone, style
    "mission":                   "...",  # Core purpose
    "recommendation_strategy":   "...",  # How to select & present books
    "academic_focus":            "...",  # Specialised domains
    "format_rules":              "...",  # Response length, structure
    "safety_rules":              "...",  # Off-topic guardrails
    "summary_instructions":      "...",  # Book summary generation
    "greeting":                  "...",  # Welcome message
}
```

Just edit the strings to change the agent's personality, specialisation, or rules.

---

## 🤖 IBM Granite Model Configuration

The model is configured in `get_watsonx_model()` in `app.py`:

```python
params = {
    GenParams.MAX_NEW_TOKENS:     600,    # Response length
    GenParams.TEMPERATURE:        0.4,    # Creativity (0=deterministic, 1=creative)
    GenParams.TOP_P:              0.9,    # Nucleus sampling
    GenParams.TOP_K:              40,     # Top-K sampling
    GenParams.REPETITION_PENALTY: 1.1,    # Reduce repetition
}
model_id = "ibm/granite-13b-chat-v2"     # Swap for other Granite variants
```

**Available IBM Granite Models** (via watsonx.ai):
| Model ID | Description |
|---|---|
| `ibm/granite-13b-chat-v2` | General-purpose chat (default) |
| `ibm/granite-13b-instruct-v2` | Instruction following |
| `ibm/granite-3-8b-instruct` | Granite 3 — compact & fast |
| `ibm/granite-3-2b-instruct` | Granite 3 — ultra-fast |

---

## 📊 API Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Main application UI |
| `/api/chat` | POST | Send a message to the AI librarian |
| `/api/search?q=` | GET | Search books by keyword |
| `/api/search?course=` | GET | Browse books by course |
| `/api/book/<id>` | GET | Get book detail + similar books |
| `/api/summary/<id>` | GET | Generate AI summary for a book |
| `/api/reserve/<id>` | POST | Reserve a book |
| `/api/reserve/<id>` | DELETE | Cancel reservation |
| `/api/profile` | GET/POST | Get / save user profile |
| `/api/history` | GET | Get borrowing history |
| `/api/library-info` | GET | Library timings, rules, services |
| `/api/courses` | GET | Available courses + journals |
| `/api/stats` | GET | Dashboard statistics |
| `/api/clear-chat` | POST | Clear session chat history |

---

## 🌍 Production Deployment

### Option 1 — Gunicorn (Linux/macOS)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Option 2 — Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
```

```bash
docker build -t library-ai-agent .
docker run -p 5000:5000 --env-file .env library-ai-agent
```

### Option 3 — IBM Code Engine / Cloud Foundry

```bash
# Install IBM Cloud CLI, then:
ibmcloud cf push library-ai-agent
```

### Security Checklist for Production

- [ ] Set `FLASK_DEBUG=False`
- [ ] Use a strong random `FLASK_SECRET_KEY`
- [ ] Serve behind NGINX / Gunicorn (never expose `app.run()` directly)
- [ ] Store secrets in environment variables or a vault (never hardcode)
- [ ] Enable HTTPS (use Let's Encrypt or a managed cert)
- [ ] Replace the in-memory data store with PostgreSQL / Redis
- [ ] Add rate limiting (e.g., Flask-Limiter)
- [ ] Add authentication (e.g., Flask-Login + LDAP for university SSO)

---

## 🔧 Extending the Application

### Add More Books
Edit [`data/library_data.json`](data/library_data.json) — each book entry follows:

```json
{
  "id": "B026",
  "title": "...",
  "authors": ["Author Name"],
  "edition": "1st Edition",
  "publisher": "...",
  "year": 2024,
  "isbn": "978-...",
  "category": "Computer Science",
  "subcategory": "...",
  "subjects": ["keyword1", "keyword2"],
  "courses": ["B.Tech CSE"],
  "location": "Section A, Shelf X",
  "total_copies": 3,
  "available_copies": 2,
  "summary": "...",
  "rating": 4.5,
  "tags": ["tag1", "tag2"]
}
```

### Add a Database (SQLite example)

```python
# Replace the JSON-based LIBRARY_DATA with SQLAlchemy models:
from flask_sqlalchemy import SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///library.db'
db = SQLAlchemy(app)
```

---

## 📋 Requirements

```
Flask==3.0.3
Flask-Session==0.8.0
python-dotenv==1.0.1
ibm-watsonx-ai==1.5.14
requests==2.32.3
Werkzeug==3.0.3
gunicorn==22.0.0
python-dateutil==2.9.0
```

---

## 📜 License

MIT License — free to use, modify, and deploy.

---

## 🙏 Acknowledgements

This project was developed using the following technologies and platforms:

- IBM watsonx.ai™ – AI Studio for building and deploying generative AI applications
- IBM Granite Foundation Models – Large Language Models powering the AI assistant
- IBM Cloud – Secure cloud platform for AI services and deployment
- Flask – Lightweight Python web framework
- Bootstrap 5 – Responsive front-end framework
- Render – Cloud hosting and deployment platform

*Built with 💙 for students, researchers, and libraries.*
