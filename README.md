# 🏈 Dynasty Rankings Webscraper Project

This project scrapes **Dynasty Rankings** data for fantasy football players and stores it in a local SQLite database. It also provides a **REST API** to query the data and a **Streamlit dashboard** for visualizing player rankings.

---

## 🔧 Features

- 🔎 Web scraping using Selenium
- 🧱 Local SQLite database for persistent storage
- ⚡ REST API via FastAPI
- 📊 Interactive dashboard with Streamlit

---

## 🧪 Tech Stack

| Layer         | Tech              |
|---------------|-------------------|
| Web Scraper   | Python + Selenium |
| Database      | SQLite            |
| API           | FastAPI           |
| Dashboard     | Streamlit         |

---

## 🚀 Quickstart

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/KTC-Webscraping.git
cd KTC-Webscraping
```

### 2. Set up environment

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Run the scraper

```bash
python src/scraper.py
```

### 4. Run the FastAPI server

```bash
uvicorn src.api:app --reload
```

Visit: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) for Swagger UI.

### 5. Launch the Streamlit dashboard

```bash
streamlit run src/dashboard.py
```

---

## 🥪 Running Tests

```bash
pytest
```

Covers scraper, database, and API layers.

---

## 📌 API Docs

### `GET /rankings`
Retrieve all players with optional filters:
- `tier`: int (optional)
- `page`: int (optional)

### `GET /rankings/{name}`
Retrieve players by (partial, case-insensitive) name match.

### Example
```bash
curl http://127.0.0.1:8000/rankings?tier=1&page=1
```

---

## 📊 Example Dashboard Screenshot

_(Add Streamlit dashboard screenshot here)_

---

## 🚣 Future Roadmap

- [ ] Add historical tracking of player value
- [ ] Dockerize the project for portability
- [ ] Deploy dashboard via Streamlit Cloud or Hugging Face Spaces
- [ ] Integrate with a fantasy football app or fantasy API

---

## 📄 License

MIT

---

## 📃 Directory Structure

```
ktc-webscraping/
├── app/                # FastAPI app
│   └── main.py
├── dashboard/          # Streamlit app
│   └── app.py
├── data/               # Scraped raw data (optional CSVs or logs)
├── db/                 # SQLite database
│   └── ktc.db
├── src/                # Core logic
│   ├── scraper.py
│   ├── database.py
│   └── utils.py
├── tests/              # Unit tests
├── .env                # Environment variables (URLs, DB name)
├── requirements.txt
├── README.md
└── Dockerfile (optional)
```

---


