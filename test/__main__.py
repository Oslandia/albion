import os
import re

for f in os.listdir(os.path.dirname(__file__)):
    if re.match('^[a-z].*\.py', f):
        print(f)
