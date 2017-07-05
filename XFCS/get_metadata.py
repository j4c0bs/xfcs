import argparse
from collections import deque
import csv
import glob
import os
import re
from statistics import mean
import sys
import time

from .FCSFile.FCSFile import FCSFile

# ------------------------------------------------------------------------------
WIDTH = os.get_terminal_size()[0]
# ------------------------------------------------------------------------------
def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='fcsmetadata', description='Parse FCS Metadata')

    parser.add_argument('--input', '-i', metavar="fcs paths", nargs='+',
                        type=argparse.FileType('rb'), help="Input file(s)")

    parser.add_argument('--recursive', '-r', action='store_true', dest='recursive',
                        help='Enable recursive search of current directory.')

    parser.add_argument('--merge', '-m', action='store_true', dest='merge',
                        help='Merge all input files into one output file.')

    parser.add_argument('--limit', '-l', type=int, default=0,
                        help='Number of most recent files to parse.')

    parser.add_argument('--kw-filter', '-k', type=argparse.FileType('r'), dest='kw_filter',
                        help='Filter output with USER KeyWord preferences file.')

    parser.add_argument('--get-kw', '-g', action='store_true', dest='get_kw',
                        help='Generate user keyword text file.')

    parser.add_argument('--tidy', '-t', action='store_true',
                        help='Outputs CSV in tidy (long) format.')

    parser.add_argument('--output', '-o', type=argparse.FileType('w'),
                        default=sys.stdout, help='Output CSV filepath.')

    # parser.add_argument('--version', action='version', version=VERSION)
    return parser.parse_args()


# ------------------------------ KEYWORD PREFS ---------------------------------
def read_kw_prefs(kw_file):
    prefs = []
    with open(kw_file.name, 'r') as f:
        prefs = [line.strip() for line in f if line.strip() != '']
    return prefs

def write_kw_prefs(paths, meta_keys):
    dirout = os.path.commonpath(paths)
    fn = 'FCS_USER_KW.txt'
    fp = os.path.join(dirout, fn)

    with open(fp, 'w') as f:
        for kw in meta_keys:
            f.write("{}\n".format(kw))

    print('Text file generated: {}'.format(fp))
    print('-'*WIDTH)
    return fp

# ------------------------------- GET METADATA ---------------------------------
def load_metadata(paths, to_csv=True):
    """
        --> makes hashtable -> filepath : fcs file class instance
        meta_keys == all_keys w any new keys extended
        replaced -> meta_keys = ['FILEPATH'] with 'SRC_FILE'
    """

    xfcs = []
    meta_keys = ['SRC_FILE', 'CSV_CREATED']

    for fp in paths:
        fcs = FCSFile()
        fcs.load(open(fp, 'rb'))
        if to_csv:
            fcs.set_param('SRC_FILE', os.path.abspath(fp))
            fcs.set_param('CSV_CREATED', time.strftime('%m/%d/%y %H:%M:%S'))

        meta_keys.extend((mk for mk in fcs.all_keys if (mk and mk not in meta_keys)))
        xfcs.append(fcs)

    return xfcs, meta_keys


# ------------------------------- ADD $PX MEAN ---------------------------------
def find_mean_spx(user_kw_prefs):
    spx = re.compile(r'\$P\d+V_MEAN')
    spx_range = re.compile(r'\$P\d+V_MEAN_\d+$')
    user_spx_mean = []

    for kw in user_kw_prefs:
        kw_match = spx.match(kw)

        if kw_match:
            if spx_range.match(kw):
                mean_range = int(kw.rsplit('_', 1)[1])
            else:
                mean_range = 10

            user_spx_mean.append((kw, mean_range))

    return user_spx_mean


def add_mean(xfcs, user_kw_prefs):
    user_spx_mean = find_mean_spx(user_kw_prefs)

    if not user_spx_mean:
        return None

    for spx, mean_range in user_spx_mean:

        spx_key = spx.split('_', 1)[0]
        spx_data = [x.param(spx_key, get_digit=True) for x in xfcs]

        volt_mean = []
        v_queue = deque(maxlen=mean_range)

        for volt in spx_data:
            v_queue.append(volt)
            volt_mean.append(mean(v_queue))

        for x, volt in zip(xfcs, volt_mean):
            x.set_param(spx, volt)

    return [voltkw[0] for voltkw in user_spx_mean]

# ------------------------------ FILEPATH GROUP --------------------------------

# def filepath_filter(paths, limit=0):
#     cleaned = [fp for fp in paths if not fp.startswith('.')]
#     cleaned.sort(key=lambda fn: os.path.getctime(fn))
#     return cleaned[-limit:]

# def rec_locator(xdir):
#     found = glob.glob('{}/**/*.fcs'.format(xdir), recursive=True)
#     return [os.path.abspath(fp) for fp in found]

def locate_fcs_files(recursive=False):
    glob_loc = '[!.]*.fcs'
    if recursive:
        rec_loc_path = os.path.join(os.curdir, '**', glob_loc)
        glob_loc = rec_loc_path

    found = glob.glob(glob_loc, recursive=recursive)
    return sorted(found, key=lambda fp: os.path.basename(fp))


# ------------------------------------------------------------------------------

# def prep_tidy_data(xfcs, spx_keys):
#     all_rows = [spx_keys]
#     for x in xfcs:
#         all_rows.append([x.param(key) for key in spx_keys])
#     return all_rows
# def prep_wide_data(xfcs, spx_keys):
#     all_rows = []
#
#     for key in spx_keys:
#         key_row = [key]
#         key_row.extend([x.param(key) for x in xfcs])
#         all_rows.append(key_row)
#     return all_rows
# def write_csv_file(all_rows, csv_file):
#     writer = csv.writer(csv_file, dialect='excel')
#     writer.writerows(all_rows)

# ------------------------------------------------------------------------------
def write_tidy_csv(xfcs, spx_keys, csv_file):
    writer = csv.writer(csv_file, dialect='excel')
    writer.writerow(spx_keys)

    for x in xfcs:
        writer.writerow([x.param(key) for key in spx_keys])


def write_wide_csv(fcs_files, spx_keys, csv_file):
    writer = csv.writer(csv_file, dialect='excel')

    for key in spx_keys:
        key_row = [key]
        vals = (fcs.param(key) for fcs in fcs_files)
        key_row.extend(vals)
        writer.writerow(key_row)


# ------------------------------------------------------------------------------
def write_metadata(args, xfcs, meta_keys):
    # >>> check user kw prefs
    if args.kw_filter:
        user_kw_prefs = read_kw_prefs(args.kw_filter)
        voltkw = add_mean(xfcs, user_kw_prefs)
        spx_keys = user_kw_prefs
    else:
        spx_keys = meta_keys


    if args.tidy:
        write_tidy_csv(xfcs, spx_keys, args.output)
    else:
        write_wide_csv(xfcs, spx_keys, args.output)

    print('csv generated: {}'.format(args.output.name))

# ------------------------------------------------------------------------------
def collect_filepaths(args):
    if args.input:
        input_paths = [infile.name for infile in args.input if infile.name.lower().endswith('.fcs')]
    else:
        input_paths = locate_fcs_files(recursive=args.recursive)

    if args.limit:
        input_paths.sort(key=lambda fn: os.path.getctime(fn))
        input_paths = input_paths[-args.limit:]

    return input_paths


def main():
    """
        xfcs --> list of meta dicts
        spx_keys --> all_keys in order + any new keys at end
            ---> FILEPATH / SRC_FILE as first key
    """

    args = parse_arguments()
    paths = collect_filepaths(args)
    print('>>> fcs files located:', len(paths))
    xfcs, meta_keys = load_metadata(paths)

    if args.get_kw:
        write_kw_prefs(paths, meta_keys)

    elif args.output.name != '<stdout>':
        write_metadata(args, xfcs, meta_keys)

    else:
        print('>>> # meta_keys:', len(meta_keys))


# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print()
    # start = time.time()
    main()

    # end = time.time()
    # print('-'*WIDTH)
    # print('Total time {:.5f} sec for {} files'.format(end-start, total_found))
    # print('Ave time per file: {:.5f} sec'.format((end-start)/total_found))
    # print('-'*WIDTH)
    # print()
