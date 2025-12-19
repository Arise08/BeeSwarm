#!/usr/bin/env python3
"""
Simple Flask server to host the Interactive Content Editor locally.
Run this script and open http://localhost:5000 in your browser.
"""

from flask import Flask, send_from_directory, send_file
import os

app = Flask(__name__)

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.route('/')
def index():
    """Serve the main HTML file."""
    return send_file(os.path.join(BASE_DIR, 'index.html'))

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, images, etc.)."""
    return send_from_directory(BASE_DIR, filename)

@app.route('/health')
def health():
    """Health check endpoint."""
    return {'status': 'ok', 'message': 'Interactive Content Editor server is running'}

if __name__ == '__main__':
    print("=" * 60)
    print("Interactive Content Editor Server")
    print("=" * 60)
    print("\nStarting server...")
    print("Open your browser and navigate to: http://localhost:5000")
    print("\nPress Ctrl+C to stop the server.\n")
    print("=" * 60)
    
    # Run the Flask app
    # Set debug=True for development, host='0.0.0.0' to allow external access
    app.run(host='127.0.0.1', port=5000, debug=True)
