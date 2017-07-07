#!/usr/bin/env python3

import argparse
from collections import deque
import csv
from itertools import compress
import os
import re
from statistics import mean
import sys
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.utils.locator import locate_fcs_files
from XFCS.utils.check_filename import valid_filename
from XFCS.version import VERSION

# ------------------------------------------------------------------------------
def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='fcsmetadata', description='Parse FCS Metadata')

    parser.add_argument('--input', '-i', metavar="fcs paths", nargs='+',
                        type=argparse.FileType('rb'), help="Input file(s)")

    parser.add_argument('--recursive', '-r', action='store_true', dest='recursive',
                        help='Enable recursive search of current directory.')

    parser.add_argument('--sep-files', '-s', action='store_true', dest='sepfiles',
                        help='Each input FCS file generates one csv file.')

    # parser.add_argument('--merge', '-m', action='store_true', dest='merge',
    #                     help='Merge all input files into one output file.')

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

    parser.add_argument('--version', action='version', version=VERSION)

    return parser.parse_args()


# ------------------------------ KEYWORD PREFS ---------------------------------
def read_kw_prefs(kw_filter_file):
    prefs = None
    with open(kw_filter_file.name, 'r') as kw_file:
        prefs = tuple(line.strip() for line in kw_file if line.strip() != '')
    return prefs


def write_kw_prefs(meta_keys):
    kw_prefs_filename = 'FCS_USER_KW.txt'
    with open(kw_prefs_filename, 'w') as kw_file:
        for keyword in meta_keys:
            kw_file.write('{}\n'.format(keyword))

    return kw_prefs_filename


# ------------------------------- GET METADATA ---------------------------------
def load_metadata(paths, to_csv=True):
    """
        --> makes hashtable -> filepath : fcs file class instance
        meta_keys == all_keys w any new keys extended
        replaced -> meta_keys = ['FILEPATH'] with 'SRC_FILE'
    """

    fcs_objs = []
    meta_keys = ['SRC_FILE', 'CSV_CREATED']

    for fp in paths:
        fcs = FCSFile()
        fcs.load(open(fp, 'rb'))
        if to_csv:
            fcs.set_param('SRC_FILE', os.path.abspath(fp))
            fcs.set_param('CSV_CREATED', time.strftime('%m/%d/%y %H:%M:%S'))

        # TODO: make key check more efficient
        meta_keys.extend((mk for mk in fcs.all_keys if mk not in meta_keys))
        fcs_objs.append(fcs)

    return fcs_objs, meta_keys


# ------------------------------- ADD $PX MEAN ---------------------------------
def find_mean_spx(user_meta_keys):
    spx = re.compile(r'\$P\d+V_MEAN')
    spx_range = re.compile(r'\$P\d+V_MEAN_\d+$')
    user_spx_mean = []

    for kw in user_meta_keys:
        kw_match = spx.match(kw)

        if kw_match:
            if spx_range.match(kw):
                mean_range = int(kw.rsplit('_', 1)[1])
            else:
                mean_range = 10

            user_spx_mean.append((kw, mean_range))

    return user_spx_mean


def add_mean(fcs_objs, user_meta_keys):
    user_spx_mean = find_mean_spx(user_meta_keys)
    if not user_spx_mean:
        return None

    missing_spx_keys = []
    for spx_param, mean_range in user_spx_mean:
        spx_key = spx_param.split('_', 1)[0]
        if not any(fcs.has_param(spx_key) for fcs in fcs_objs):
            missing_spx_keys.extend((spx_key, spx_param))
            continue

        volt_mean = []
        v_queue = deque(maxlen=mean_range)
        spx_data = (x.numeric_param(spx_key) for x in fcs_objs)

        for volt in spx_data:
            v_queue.append(volt)
            volt_mean.append(mean(v_queue))

        for x, volt in zip(fcs_objs, volt_mean):
            x.set_param(spx_param, round(volt, 2))

    return missing_spx_keys


def write_tidy_csv(writer, fcs_objs, meta_keys):
    writer.writerow(meta_keys)
    for fcs in fcs_objs:
        writer.writerow((fcs.param(key) for key in meta_keys))


def write_wide_csv(writer, fcs_objs, meta_keys):
    for key in meta_keys:
        key_row = [key]
        vals = (fcs.param(key) for fcs in fcs_objs)
        key_row.extend(vals)
        writer.writerow(key_row)


def write_metadata(fcs_objs, meta_keys, csv_fn, tidy):
    write_csv_file = write_tidy_csv if tidy else write_wide_csv
    with open(csv_fn, 'w') as csv_file:
        writer = csv.writer(csv_file, dialect='excel')
        write_csv_file(writer, fcs_objs, meta_keys)


def merge_metadata(fcs_objs, meta_keys, tidy):
    curdir_name = os.path.basename(os.getcwd())
    csv_fn = '{}_FCS_metadata.csv'.format(curdir_name)
    write_metadata(fcs_objs, meta_keys, csv_fn, tidy)
    return csv_fn


def fcs_to_csv_path(fcs_path, tidy=False):
    # >>> for testing, disable writing csv files in place
    desc = '-t' if tidy else ''
    filename = os.path.basename(fcs_path).split('.')[0]
    csv_fn = '{}_metadata{}.csv'.format(filename, desc)
    # par_dir = os.path.dirname(fcs_path)
    # name = '{}_metadata{}'.format(filename, desc)
    # return os.path.join(par_dir, csv_fn)
    return csv_fn


def batch_separate_metadata(fcs_objs, meta_keys, tidy):
    src_keys = ('SRC_FILE', 'CSV_CREATED')
    csv_paths = []
    for fcs in fcs_objs:
        sep_keys = tuple(key for key in meta_keys if (fcs.has_param(key) or key in src_keys))
        csv_fn = fcs_to_csv_path(fcs.param('SRC_FILE'), tidy=tidy)
        write_metadata((fcs,), sep_keys, csv_fn, tidy)
        csv_paths.append(csv_fn)
    return csv_paths


# ------------------------------------------------------------------------------
def apply_keyword_filter(kw_filter_file, fcs_objs):
    user_meta_keys = read_kw_prefs(kw_filter_file)
    missing_spx_keys = add_mean(fcs_objs, user_meta_keys)
    if missing_spx_keys:
        drop_keys = (k not in missing_spx_keys for k in user_meta_keys)
        return tuple(compress(user_meta_keys, drop_keys))
    else:
        return user_meta_keys


def collect_filepaths(in_paths, recursive, limit=0):
    if in_paths:
        fcs_paths = [infile.name for infile in in_paths if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(recursive)

    if limit:
        # TODO: safe ctime -> or use $DATE in metadata
        fcs_paths.sort(key=lambda fn: os.path.getctime(fn))
        fcs_paths = fcs_paths[-limit:]

    return fcs_paths


def main():
    """Main control for CLI metadata extraction.

        fcs_objs: iterable of metadata dicts
        meta_keys: all_keys in order + any new (calculated) keys at end
    """

    args = parse_arguments()
    paths = collect_filepaths(args.input, args.recursive, args.limit)
    print('>>> fcs files located:', len(paths))

    to_csv = not args.get_kw
    fcs_objs, meta_keys = load_metadata(paths, to_csv)

    if args.get_kw:
        kw_prefs_filename = write_kw_prefs(meta_keys)
        print('>>> FCS Keyword file generated:', kw_prefs_filename)
    else:
        if args.kw_filter:
            meta_keys = apply_keyword_filter(args.kw_filter, fcs_objs)

        if args.sepfiles:
            csv_paths = batch_separate_metadata(fcs_objs, meta_keys, args.tidy)
            print('>>> csv files written: {}'.format(len(csv_paths)))
        else:
            csv_out_path = merge_metadata(fcs_objs, meta_keys, args.tidy)
            print('>>> csv file written to: {}'.format(csv_out_path))


# ------------------------------------------------------------------------------
# if __name__ == '__main__':
#     print()
#     # start = time.time()
#     main()
#     # end = time.time()
#     # print('Total time {:.5f} sec for {} files'.format(end-start, total_found))
#     # print('Ave time per file: {:.5f} sec'.format((end-start)/total_found))
#     # print()
