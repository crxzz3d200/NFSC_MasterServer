# DSPR

A simple video game car social website built with Python and static frontend assets.

## Features
- Create local accounts
- Login and logout
- Upload car images with captions
- Browse a shared social feed
- Styled layout with a custom DSPR logo

## Run the site
1. Open a terminal in the `DSPR` folder.
2. Run:

```bash
python3 server.py
```

3. Open `http://localhost:8000` in your browser.

## File structure
- `static/` — frontend assets (`index.html`, `styles.css`, `app.js`, `logo.svg`)
- `server.py` — backend Python HTTP server
- `data/` — user and post storage
- `uploads/` — uploaded image files
