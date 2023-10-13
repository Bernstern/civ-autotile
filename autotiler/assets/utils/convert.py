# Go through every file in this directory, if the file type is .webp, convert it to .jpg and remove
#   everything after the first underscore in the filename.

import os
import sys

for filename in os.listdir("."):
    if filename.endswith(".webp"):
        new_filename = filename.split("_")[0] + ".jpg"
        os.system(f"ren {filename} {new_filename}")

    # then lowercase every filename
    os.system(f"ren {filename} {filename.lower()}")
