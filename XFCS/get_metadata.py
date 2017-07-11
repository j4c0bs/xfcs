#!/usr/bin/env python3

import argparse
from collections import deque
import csv
from itertools import compress
import os
import re
from statistics import mean
# import sys
import time

from XFCS.FCSFile.FCSFile import FCSFile
from XFCS.utils.locator import locate_fcs_files
# from XFCS.utils.check_filename import valid_filename
from XFCS.version import VERSION

# ------------------------------------------------------------------------------
def parse_arguments():
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(prog='xfcs', description='Parse FCS Metadata')

    csv_in = parser.add_argument_group('Input Options')
    csv_in.add_argument('--input', '-i', metavar='<file.fcs>', nargs='+',
    type=argparse.FileType('rb'), help='Optional select input file(s) instead of default directory search.')

    csv_in.add_argument('--recursive', '-r', action='store_true', dest='recursive',
    help='Enable recursive search of current directory.')

    csv_in.add_argument('--limit', '-l', type=int, default=0, metavar='n',
    help='Number of most recent files to parse.')

    csvout = parser.add_argument_group('Output Options - select 1')
    outgrp = csvout.add_mutually_exclusive_group()

    outgrp.add_argument('--sep-files', '-s', action='store_true', dest='sepfiles',
                        help='Each input FCS file generates one csv file.')

    outgrp.add_argument('--output', '-o', type=argparse.FileType('w'), metavar='<file.csv>',
                        help='Output .csv filepath for merged metadata file.')

    procopt = parser.add_argument_group('Metadata Option - select 1')
    kw_merge = procopt.add_mutually_exclusive_group()

    kw_merge.add_argument('--append-to', '-a', type=argparse.FileType('r'), dest='merge', metavar='<metadata.csv>',
                        help='Append fcs metadata to existing fcs metadata csv file.')

    kw_merge.add_argument('--kw-filter', '-k', type=argparse.FileType('r'), dest='kw_filter', metavar='<user_kw.csv>',
    help='Filter output with USER KeyWord preferences file.')

    kw_merge.add_argument('--get-kw', '-g', action='store_true', dest='get_kw',
                        help='Generate user keyword text file.')

    parser.add_argument('--tidy', '-t', action='store_true',
                        help='Outputs CSV in tidy (long) format.')

    parser.add_argument('-v', '--version', action='version', version=VERSION)

    return parser.parse_args()


# ------------------------------ KEYWORD PREFS ---------------------------------
def read_kw_prefs(kw_filter_file):
    user_meta_keys = None
    with open(kw_filter_file.name, 'r') as kw_file:
        user_meta_keys = [line.strip() for line in kw_file if line.strip() != '']
    return user_meta_keys


def write_kw_prefs(meta_keys):
    kw_prefs_filename = 'FCS_USER_KW.txt'
    with open(kw_prefs_filename, 'w') as kw_file:
        for keyword in meta_keys:
            kw_file.write('{}\n'.format(keyword))

    return kw_prefs_filename


# ------------------------------------------------------------------------------
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
        meta_keys.extend((mk for mk in fcs.param_keys if mk not in meta_keys))
        fcs_objs.append(fcs)

    return fcs_objs, meta_keys


# ------------------------------- $Px STATS ------------------------------------
def find_mean_spx_param_keys(user_meta_keys):
    """
        example input: $P10V_MEAN or $P10V_MEAN_5
    """

    spx_key_range = re.compile(r'^(\$P\d+V)_MEAN(_\d+)?$')
    param_key_ranges = []
    for param_mean_key in user_meta_keys:
        kw_match = spx_key_range.match(param_mean_key)

        if kw_match:
            param_key, mean_range = kw_match.groups()
            if mean_range:
                mean_range = int(mean_range.strip('_'))

            if not mean_range:
                mean_range = 10

            param_key_ranges.append((param_key, param_mean_key, mean_range))

    return param_key_ranges


def add_param_mean(fcs_objs, user_meta_keys):
    param_key_ranges = find_mean_spx_param_keys(user_meta_keys)
    if not param_key_ranges:
        return user_meta_keys

    missing_spx_keys = []
    volt_keys = []

    for param_key, param_mean_key, mean_range in param_key_ranges:
        if not any(fcs.has_param(param_key) for fcs in fcs_objs):
            missing_spx_keys.extend((param_key, param_mean_key))
            continue

        volt_keys.append((param_key, param_mean_key))

        volt_mean = []
        v_queue = deque(maxlen=mean_range)
        spx_data = (x.numeric_param(param_key) for x in fcs_objs)

        for volt in spx_data:
            v_queue.append(volt)
            volt_mean.append(mean(v_queue))

        for x, volt in zip(fcs_objs, volt_mean):
            x.set_param(param_mean_key, round(volt, 2))

    # force parameter keys included if only $Px_MEAN in user kw file
    for (param_key, param_mean_key) in volt_keys:
        if param_key not in user_meta_keys:
            ix = user_meta_keys.find(param_mean_key)
            user_meta_keys.insert(ix, param_key)

    if missing_spx_keys:
        drop_keys = (k not in missing_spx_keys for k in user_meta_keys)
        user_meta_keys = tuple(compress(user_meta_keys, drop_keys))

    return user_meta_keys


# ------------------------------------------------------------------------------
def apply_keyword_filter(fcs_objs, kw_filter_file):
    user_meta_keys = read_kw_prefs(kw_filter_file)
    valid_keys = add_param_mean(fcs_objs, user_meta_keys)
    return valid_keys


# ------------------------------------------------------------------------------
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


def merge_metadata(fcs_objs, meta_keys, tidy, fn_out=''):

    if fn_out:
        csv_fn = fn_out
    else:
        desc = '-t' if tidy else '-w'
        curdir_name = os.path.basename(os.getcwd())
        csv_fn = '{}_FCS_metadata{}.csv'.format(curdir_name, desc)

    write_metadata(fcs_objs, meta_keys, csv_fn, tidy)
    return csv_fn


def fcs_to_csv_path(fcs_path, tidy=False):
    # >>> for testing, disable writing csv files in place
    desc = '-t' if tidy else '-w'
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


# ------------------------------------------------------------------------------
def load_metadata_csv_file(fp, meta_keys):
    merge_keys = []
    merge_data = []
    is_tidy = False

    with open(fp, 'r') as metadata_csv:
        meta_reader = csv.reader(metadata_csv)
        rows = [row for row in meta_reader]

    # determine if tidy format
    if len(set(rows[0]) & set(meta_keys)) > 1:
        is_tidy = True
        merge_keys = tuple(rows[0])
        for row in rows[1:]:
            merge_data.append({key: value for key, value in zip(merge_keys, row)})

    else:
        merge_keys = tuple(row[0] for row in rows)
        if len(set(merge_keys) & set(meta_keys)) > 1:
            entries = len(rows[0])
            for ix in range(1, entries):
                col = (row[ix] for row in rows)
                merge_data.append({key: value for key, value in zip(merge_keys, col)})

    return merge_keys, merge_data, is_tidy


def batch_load_fcs_from_csv(merge_keys, merge_data):
    merge_objs = []
    for param_vals in merge_data:
        fcs = FCSFile()
        fcs.load_from_csv(merge_keys, param_vals)
        merge_objs.append(fcs)
    return merge_objs


def append_metadata(fcs_objs, meta_keys, master_csv, fn_out):
    merge_keys, merge_data, is_tidy = load_metadata_csv_file(master_csv, meta_keys)

    if not all((merge_keys, merge_data)):
        print('>>> No metadata keys match / data located')
        return

    csv_fcs_objs = batch_load_fcs_from_csv(merge_keys, merge_data)

    # >>> check duplicate fcs metadata entries
    comparison_keys = [key for key in merge_keys if key in meta_keys]

    csv_fcs_hashes = set(fcs.meta_hash(comparison_keys) for fcs in csv_fcs_objs)
    incoming_hashes = [fcs.meta_hash(comparison_keys) for fcs in fcs_objs]
    hash_filter = [md_hash not in csv_fcs_hashes for md_hash in incoming_hashes]

    all_fcs_objs = []
    all_fcs_objs.extend(csv_fcs_objs)

    if not all(hash_filter):
        unique_fcs = tuple(compress(fcs_objs, hash_filter))
        if not unique_fcs:
            print('>>> No unique fcs files to append to master csv')
            return
        else:
            all_fcs_objs.extend(unique_fcs)
    else:
        all_fcs_objs.extend(fcs_objs)

    merge_keys = add_param_mean(all_fcs_objs, merge_keys)
    csv_out_path = merge_metadata(all_fcs_objs, merge_keys, is_tidy, fn_out)
    print('>>> fcs metadata appended to: {}'.format(csv_out_path))


# def append_metadata(fcs_objs, meta_keys, master_csv, fn_out):
#     merge_keys, merge_data, is_tidy = load_metadata_csv_file(master_csv, meta_keys)
#
#     if not all((merge_keys, merge_data)):
#         print('>>> No metadata keys match / data located')
#         return
#
#     all_fcs_objs = batch_load_fcs_from_csv(merge_keys, merge_data)
#     # >>> check dup entries
#
#     all_fcs_objs.extend(fcs_objs)
#     merge_keys = add_param_mean(all_fcs_objs, merge_keys)
#
#
#     csv_out_path = merge_metadata(all_fcs_objs, merge_keys, is_tidy, fn_out)
#     print('>>> fcs metadata appended to: {}'.format(csv_out_path))
#


# ------------------------------------------------------------------------------
def main():
    """Main control for CLI metadata extraction.

        fcs_objs: iterable of metadata dicts
        meta_keys: all_keys in order + any new (calculated) keys at end
    """

    args = parse_arguments()
    paths = collect_filepaths(args.input, args.recursive, args.limit)
    print('>>> fcs files located:', len(paths))
    if not paths:
        return

    to_csv = not args.get_kw
    fcs_objs, meta_keys = load_metadata(paths, to_csv)

    if args.get_kw:
        kw_prefs_filename = write_kw_prefs(meta_keys)
        print('>>> FCS Keyword file generated:', kw_prefs_filename)

    elif args.merge:
        master_csv = args.merge.name
        fn_out = master_csv if not args.output else args.output.name
        append_metadata(fcs_objs, meta_keys, master_csv, fn_out)

    else:
        if args.kw_filter:
            meta_keys = apply_keyword_filter(fcs_objs, args.kw_filter)

        if args.sepfiles:
            csv_paths = batch_separate_metadata(fcs_objs, meta_keys, args.tidy)
            print('>>> csv files written: {}'.format(len(csv_paths)))
        else:
            fn_out = '' if not args.output else args.output.name
            csv_out_path = merge_metadata(fcs_objs, meta_keys, args.tidy, fn_out)
            print('>>> csv file written to: {}'.format(csv_out_path))






# ------------------------------------------------------------------------------
