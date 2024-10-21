import os
from os.path import dirname, join

setup_file = join(dirname(__file__), "..", "setup.py")

os.system(f"python {setup_file} bdist_wheel -d build/dist")
os.system(f"python {setup_file} sdist -d build/dist")
