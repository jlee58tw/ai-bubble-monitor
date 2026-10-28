import sys
from common import db
con = db()
for r in con.execute(sys.argv[1]).fetchall():
    print(r)
