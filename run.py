import os
import sys
from backend import app


if __name__ == "__main__":
    # Use environment variables for production configuration
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    host = os.getenv('HOST', '0.0.0.0')
    
    # Check for command line argument for port
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number. Using default port 5000.")
            port = 5000
    else:
        port = int(os.getenv('PORT', 5000))
    
    app.run(debug=debug_mode, host=host, port=port)
