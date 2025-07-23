import os
from backend import app


if __name__ == "__main__":
    # Use environment variables for production configuration
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    app.run(debug=debug_mode, host=host, port=port)