import os
import sys
import tempfile

TMP = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/test.db"
os.environ["UPLOAD_DIR"] = f"{TMP}/uploads"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
