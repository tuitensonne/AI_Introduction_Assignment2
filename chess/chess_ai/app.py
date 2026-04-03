"""
app.py — entry point
Run: python app.py
Then open: http://localhost:5000
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from api.server import app

if __name__ == "__main__":
    print("Chess AI Lab")
    print("   Open: http://localhost:5000")
    app.run(debug=False, port=5000, host="0.0.0.0")
