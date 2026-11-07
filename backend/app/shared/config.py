"""App-wide settings read from the environment.

Most modules still read their own settings next to the code that uses them (auth.py, mailer.py,
push.py, otp.py), so each one can be read and tested on its own."""
import os

# Sites allowed to call the API: the Vercel site, local dev, and https://localhost for the Android app.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")]
