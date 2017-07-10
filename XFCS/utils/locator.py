"""File specific locators"""

import glob
import os
# ------------------------------------------------------------------------------
def locate_fcs_files(recursive=False):
    glob_loc = '[!.]*.fcs'
    if recursive:
        rec_loc_path = os.path.join(os.curdir, '**', glob_loc)
        glob_loc = rec_loc_path

    found = glob.glob(glob_loc, recursive=recursive)
    found.sort(key=lambda fp: os.path.basename(fp))
    return found
