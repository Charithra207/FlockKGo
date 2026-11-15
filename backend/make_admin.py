"""
make_admin.py — Give an existing account admin rights (to review spots).

Usage (after signing up on the website):
    python make_admin.py you@example.com
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.database import SessionLocal  # noqa: E402
import app.models  # noqa: E402,F401
from app.models.user import User  # noqa: E402


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    email = sys.argv[1].strip().lower()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"No account with email {email}. Sign up on the site first.")
            sys.exit(1)
        user.is_admin = True
        db.commit()
        print(f"✓ {user.display_name} ({email}) is now an admin")
    finally:
        db.close()


if __name__ == "__main__":
    main()
