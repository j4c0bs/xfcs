#!/usr/bin/env python3

import argparse
from collections import deque
import csv
# import glob
import os
import re
from statistics import mean
import sys
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.utils.locator import locate_fcs_files


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

    return fp

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


def add_mean(fcs_objs, user_kw_prefs):
    user_spx_mean = find_mean_spx(user_kw_prefs)

    if not user_spx_mean:
        return None

    for spx, mean_range in user_spx_mean:

        spx_key = spx.split('_', 1)[0]
        spx_data = [x.numeric_param(spx_key) for x in fcs_objs]

        volt_mean = []
        v_queue = deque(maxlen=mean_range)

        for volt in spx_data:
            v_queue.append(volt)
            volt_mean.append(mean(v_queue))

        for x, volt in zip(fcs_objs, volt_mean):
            x.set_param(spx, round(volt, 2))

    # return [voltkw[0] for voltkw in user_spx_mean]


# ------------------------------------------------------------------------------
def write_tidy_csv(fcs_objs, meta_keys, csv_file):
    writer = csv.writer(csv_file, dialect='excel')
    writer.writerow(meta_keys)

    for fcs in fcs_objs:
        writer.writerow([fcs.param(key) for key in meta_keys])


def write_wide_csv(fcs_objs, meta_keys, csv_file):
    writer = csv.writer(csv_file, dialect='excel')

    for key in meta_keys:
        key_row = [key]
        vals = (fcs.param(key) for fcs in fcs_objs)
        key_row.extend(vals)
        writer.writerow(key_row)


# ------------------------------------------------------------------------------
# (kw_filter, tidy, output, output.name)

# fcs_objs, meta_keys, tidy, csv_out_path
def write_metadata(fcs_objs, meta_keys, tidy):

    if tidy:
        write_csv = write_tidy_csv
    else:
        write_csv = write_wide_csv

    curdir_name = os.path.basename(os.getcwd())
    csv_out_path = '{}_FCS_metadata.csv'.format(curdir_name)

    with open(csv_out_path, 'w') as csv_file:
        write_csv(fcs_objs, meta_keys, csv_file)

    # write_csv(fcs_objs, meta_keys, args.output)
    # if args.tidy:
    #     write_tidy_csv(fcs_objs, meta_keys, args.output)
    # else:
    #     write_wide_csv(fcs_objs, meta_keys, args.output)

    # print('csv generated: {}'.format(args.output.name))


def fcs_to_csv_path(fcs_path):
    filename = os.path.basename(fcs_path).split('.')[0]
    par_dir = os.path.dirname(fcs_path)
    csv_name = '{}_metadata.csv'.format(filename)
    return os.path.join(par_dir, csv_name)


def batch_separate_metadata(fcs_objs, meta_keys, tidy):
    write_csv = write_tidy_csv if tidy else write_wide_csv

    for fcs in fcs_objs:
        sep_keys = [key for key in meta_keys if key in fcs.text]
        csv_out_path = fcs_to_csv_path(fcs.param('SRC_FILE'))
        with open(csv_out_path, 'w') as csv_file:
            write_csv((fcs,), sep_keys, csv_file)


# ------------------------------------------------------------------------------
def apply_keyword_filter(user_kw_path, fcs_objs):
    user_meta_keys = read_kw_prefs(user_kw_path)
    add_mean(fcs_objs, user_meta_keys)
    return user_meta_keys


def collect_filepaths(in_paths, recursive, limit=0):
    if in_paths:
        fcs_paths = [infile.name for infile in in_paths if infile.name.lower().endswith('.fcs')]
    else:
        fcs_paths = locate_fcs_files(recursive)

    if limit:
        fcs_paths.sort(key=lambda fn: os.path.getctime(fn))
        fcs_paths = fcs_paths[-limit:]

    return fcs_paths


def main():
    """
        fcs_objs --> iterable of metadata dicts
        spx_keys --> all_keys in order + any new keys at end
            ---> FILEPATH / SRC_FILE as first key
    """

    args = parse_arguments()
    paths = collect_filepaths(args.input, args.recursive, args.limit)
    print('>>> fcs files located:', len(paths))

    # >>> needs to_csv=False if get_kw
    to_csv = not args.get_kw
    fcs_objs, meta_keys = load_metadata(paths, to_csv)

    if args.get_kw:
        kw_filepath = write_kw_prefs(paths, meta_keys)
        print('>>> FCS Keyword file generated:', kw_filepath)

    else:
        if args.kw_filter:
            # user_kw_path = args.kw_filter.name
            meta_keys = apply_keyword_filter(args.kw_filter, fcs_objs)

        if args.sepfiles:
            batch_separate_metadata(fcs_objs, meta_keys, args.tidy)
        else:
            write_metadata(fcs_objs, meta_keys, args.tidy)


    # elif args.output.name != '<stdout>':
    # else:
    #     print('>>> # meta_keys:', len(meta_keys))


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
