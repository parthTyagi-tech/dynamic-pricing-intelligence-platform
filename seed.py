import sys
import os

if __name__ == "__main__":
    # Adjust working directory to backend
    backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
    os.chdir(backend_path)
    # Add backend folder to python search path
    sys.path.insert(0, backend_path)
    
    # Import and run backend seed module
    import seed
    seed.seed_database()
